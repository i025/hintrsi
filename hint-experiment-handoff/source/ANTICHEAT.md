# SWE-Pro Anti-Cheat Notes

Trajectory audit of `zhy_0326_wrong_glm5_2` (400-instance random sample) found
**100% of runs called `WebFetch`**, and 32.9% called `gh`, 28.5% ran
`git log --all`, 19% ran `git clone https://…`, 18% ran `git show <sha>`,
17% ran `curl|wget https://…`. Top targets: `raw.githubusercontent.com`,
`github.com`, `api.github.com`, `patch-diff.githubusercontent.com`,
`cdn.jsdelivr.net`, `web.archive.org`, `www.google.com`.

The model was reliably identifying the upstream fix commit (often reachable
directly by SHA from the `instance_id` suffix, e.g. `130403592@ab5a58af31`
→ commit `ab5a58af31…`) and copying it.

## What ships in this repo

Applied in code (see commits touching `run_cc_sdk.py`, `constant_zhy.py`,
`run_cc_trajs_swe_pro.py`):

| # | Layer | Change | File |
|---|---|---|---|
| P0-1 | SDK | Add `WebFetch` to `disallowed_tools` | `run_cc_sdk.py` |
| P0-2 | Network | `/etc/hosts` blackhole for GitHub/CDN/search-engine/registry hosts | `constant_zhy.py:INSTALL_SCRIPT` |
| P0-3 | Git | Strip remotes, refs, reflog, and prune unreachable objects after `git reset` | `run_cc_trajs_swe_pro.py:_install_and_reset` |
| P1a  | Bin  | Remove `gh` CLI at install | `constant_zhy.py:INSTALL_SCRIPT` |
| P1b  | Hook | `PreToolUse` hook on `Bash` denies `gh …`, `git clone http…`, `git ls-remote`, `git fetch origin/upstream`, `git log …--all/origin/…`, `git show <sha7+>`, `curl/wget` to source hosts | `constant_zhy.py:INSTALL_SCRIPT` (writes `/app/.claude/hooks/deny_cheat.sh` + `/app/.claude/settings.json`) |
| P2   | Prompt | Sanitize upstream URLs, `PR #NNN`, `pull/NNN`, `commit/<sha>`, bare 10-12 or 40 hex SHAs, and the `instance_id` `@<sha>` suffix from `problem_statement` | `run_cc_trajs_swe_pro.py:_sanitize_problem_statement` |

Blocked-command log lands in the container at `/tmp/anticheat_blocks.log`;
you can copy that out via `_collect_artifacts` for later audit if desired.

## What is NOT covered (P3 — evaluation-layer suggestions)

Even with everything above, the fundamental grading loop remains:

> apply the model's patch, apply the upstream test patch, run `FAIL_TO_PASS`
> tests, mark solved iff they pass.

That grading rewards patches that reproduce **upstream's API choices**
(exact function names, exact constants, exact struct fields). If a task has
one obvious fix, the model can guess right; if it has several equally valid
fixes, only the one that matches upstream is scored correct — which
pressures the model to look up upstream. Suggestions:

1. **Mutate test assertions per run.** Rename constants, alias imports,
   perturb string literals in expected values. Ties output to *behavior*
   not *identifiers*.
2. **Randomize FAIL_TO_PASS command flags** (test filter, verbosity, seed)
   so trajectory pattern-matching from prior runs doesn't help.
3. **Detect trivial-clone patches.** After grading, compare model patch to
   `git show <upstream-sha>` at the char level and flag near-identical
   patches even if they pass — surfaces cheating even when the leak channel
   is one we haven't blocked.
4. **Rewrite `instance_id`s** so the suffix is a random hash, not the
   upstream fix commit prefix. Even if the model can `pwd`, the suffix
   should carry no information.
5. **Two-agent panel.** Have a second cheap model, blinded to the
   trajectory, judge whether the patch looks derived from local reasoning
   (search-log, incremental edits, test-driven) vs. one-shot verbatim
   application. Weight scores accordingly.

## Sample checks after next run

```bash
# Confirm hook fired
grep -c BLOCKED /path/to/infer_logs/*/attempt-*/anticheat_blocks.log

# Confirm no successful GitHub fetches
grep -E '"name":\s*"WebFetch"' /path/to/infer_logs/*/extracted_trajs.json | wc -l
# Should be 0 (WebFetch is disallowed at SDK layer).

# Confirm no `gh`/`git clone http`/`git show <sha>` calls succeeded
python3 - <<'PY'
import json, re, glob
pats = [r'"name":\s*"Bash"[\s\S]{0,300}gh (pr|api|search)',
        r'git clone [^"]*https?://',
        r'git show [0-9a-f]{7,40}']
for f in glob.glob('/path/to/infer_logs/*/extracted_trajs.json'):
    txt = open(f).read()
    for p in pats:
        if re.search(p, txt):
            print(f, '->', p)
PY
```
