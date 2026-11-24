"""Anti-cheat toolkit for cc-run.

Central module for everything that prevents the agent from reaching upstream
fix commits. Three logical layers, exposed here so runner code can import
from one place instead of hunting through utils.py + constant_zhy.py:

  1. Runtime blocking — PreToolUse hook / DNS blackhole / iptables rules.
     Currently installed by INSTALL_SCRIPT in constant_zhy.py, since it needs
     to run inside the container as part of image bootstrap. Only the log
     paths that side writes to are exported here (BLOCKS_LOG / FIREWALL_LOG).

  2. Git tree scrubbing — build bash commands from Python for the runner to
     run via `container.exec_run`. `git_scrub_command` removes refs/reflog
     and prunes unreachable objects; `git_rebuild_command` goes further and
     rewrites `.git` entirely, leaving a single-commit history.

  3. Policy — env-var toggles that the runner reads:
       REBUILD_GIT=1  → nuke .git and rebuild (strongest, changes base SHA)
       STRICT_SCRUB=1 → treat scrub-assertion failure as fatal, skip task

Assertions and log paths follow a single convention: everything anti-cheat
writes lives under /tmp/anticheat_*.log inside the container. Runner's
_collect_artifacts copies these back to the host output dir.
"""
import os
import shlex as _shlex


# ---------------------------------------------------------------------------
# Log paths (all container-side, all under /tmp).
# ---------------------------------------------------------------------------
ANTICHEAT_SCRUB_LOG_PATH = "/tmp/anticheat_scrub.log"
ANTICHEAT_REBUILD_LOG_PATH = "/tmp/anticheat_rebuild.log"
# The PreToolUse hook (installed by constant_zhy.INSTALL_SCRIPT) writes here
# when it blocks a Bash command; the iptables OUTPUT rules append their own
# reject log to the second one.
ANTICHEAT_BLOCKS_LOG_PATH = "/tmp/anticheat_blocks.log"
ANTICHEAT_FIREWALL_LOG_PATH = "/tmp/anticheat_firewall.log"


# ---------------------------------------------------------------------------
# Policy: env-var driven toggles. Read once at import time so behavior is
# consistent across a run.
# ---------------------------------------------------------------------------
# REBUILD_GIT=1 nukes the container's .git after scrub and rebuilds a single-
# commit history from the working tree. Blocks the "model recalls upstream SHA
# from pretraining and looks it up via git" leak channel, at the cost of
# breaking any code path that relied on the original base_commit SHA existing
# in the local repo. See git_rebuild_command for details.
REBUILD_GIT = os.getenv("REBUILD_GIT", "0") == "1"

# STRICT_SCRUB=1 makes anti-cheat scrub assertion failures fatal: the task is
# aborted with status "scrub_failed" instead of continuing with weakened
# guarantees. Only meaningful when REBUILD_GIT=0 (REBUILD_GIT=1 replaces .git
# entirely so scrub residue is irrelevant).
STRICT_SCRUB = os.getenv("STRICT_SCRUB", "0") == "1"


# ---------------------------------------------------------------------------
# Layer 2: git scrubbing / rebuild bash commands.
# ---------------------------------------------------------------------------
#
# Anti-cheat git scrub: strip every ref/reflog/object that could reveal the
# upstream fix commit AFTER `git reset --hard base_commit`. Keep base_commit
# and its ancestors intact so builds still work.
#
# Prior implementation had two bugs found in production:
#   1. `set -e` at the top -- if any early step failed (e.g. `git checkout`
#      when base_commit isn't in the local pack), the whole scrub aborted
#      silently. Result: `git branch -a` still showed origin/HEAD, tags
#      still existed, `git show <upstream-sha>` worked.
#   2. No verification. We write to /tmp/anticheat_scrub.log now so the
#      runner can copy it out and audit whether scrub actually landed.
#
# Design: each step runs independently with `|| true`, log every step's
# exit code, then run assertions at the end and log whether they held.
# Caller checks scrub_res.exit_code (0 means all assertions passed).


def git_scrub_command(base_commit: str, work_dir: str = "/app") -> str:
    """Build the bash command that scrubs a git repo of upstream leaks.
    Returns a self-contained string suitable for `bash -c <cmd>`.

    Every step is fault-tolerant (`|| true`). Progress and final assertion
    results are appended to /tmp/anticheat_scrub.log. Exit code:
      0 = all post-conditions hold (no remotes, only main in refs/heads,
          no non-HEAD refs, no unreachable commits, no orphan pack SHAs)
      1 = at least one assertion failed. Callers with STRICT_SCRUB should
          treat this as a hard failure and skip the task.
    """
    bc_q = _shlex.quote(base_commit)
    wd_q = _shlex.quote(work_dir)
    log_q = _shlex.quote(ANTICHEAT_SCRUB_LOG_PATH)
    return f"""cd {wd_q} && {{
  _log() {{ printf '[%s] %s\\n' "$(date -u +%FT%TZ)" "$*" >> {log_q}; }}
  # Capture stderr on failure so we know WHY a step failed (previously ec=128
  # with no clue). Success stays quiet to keep the log short.
  _step() {{
    local desc="$1"; shift
    local out
    out="$("$@" 2>&1)"; local ec=$?
    if [ $ec -eq 0 ]; then
      _log "step ec=0: $desc"
    else
      _log "step ec=$ec: $desc :: $(printf '%s' \"$out\" | tail -c 400 | tr '\\n' '|')"
    fi
    return 0
  }}
  _log "===== scrub start (base_commit={base_commit}) ====="
  _log "env: whoami=$(whoami 2>/dev/null) git=$(git --version 2>&1 | head -1)"
  # 0. Ownership / safe.directory: some base images clone /app as a non-root
  #    UID, then root's git refuses to touch it. Fix ownership best-effort and
  #    whitelist the directory before any git command that might write refs.
  _step "chown .git" bash -c 'if [ -d .git ] && [ "$(stat -c %U .git 2>/dev/null)" != "$(whoami)" ]; then chown -R "$(id -u):$(id -g)" .git 2>/dev/null || true; fi'
  _step "safe.directory workdir"  git config --global --add safe.directory {wd_q}
  _step "safe.directory wildcard" git config --global --add safe.directory '*'
  # 1. Detach HEAD onto base_commit so we can delete branches. If this
  #    fails (SHA not present locally) subsequent steps still run.
  _step "checkout --detach" git checkout --detach {bc_q}
  # 2a. Fast batch delete via update-ref --stdin, but SKIP symbolic-refs
  #     (`update-ref -d` refuses them, aborts the whole batch on old git).
  _step "delete non-symbolic refs (batch)" bash -c "git for-each-ref --format='%(refname) %(symref)' | awk '\\$2 == \\"\\" {{print \\"delete \\"\\$1}}' | git update-ref --stdin"
  # 2b. Symbolic-refs (e.g. refs/remotes/origin/HEAD) need `symbolic-ref -d`,
  #     not `update-ref -d`. Handle them separately. Avoid `xargs -r` (GNU-only)
  #     since some images ship BusyBox — loop in shell instead.
  _step "delete symbolic refs" bash -c "git for-each-ref --format='%(refname) %(symref)' | awk '\\$2 != \\"\\" {{print \\$1}}' | while read r; do [ -n \\"\\$r\\" ] && git symbolic-ref -d \\"\\$r\\" 2>/dev/null || true; done"
  # 2c. One-at-a-time fallback: any refs the batch/symbolic passes missed
  #     (permission errors, weird packed-refs layout, ref-name edge cases).
  _step "delete refs (per-ref fallback)" bash -c "git for-each-ref --format='%(refname)' | while read r; do git update-ref -d \\"\\$r\\" 2>/dev/null || git symbolic-ref -d \\"\\$r\\" 2>/dev/null || true; done"
  # 2d. Nuclear: if refs still exist, remove them at the filesystem level.
  #     Rebuilds happen in step 7 via `checkout -B main` which recreates
  #     refs/heads/main from HEAD.
  _step "rm .git/refs subtrees (nuclear)" bash -c 'rm -rf .git/refs/heads/* .git/refs/tags .git/refs/remotes .git/refs/pull .git/refs/notes .git/refs/stash .git/refs/replace .git/refs/original 2>/dev/null; :'
  # 3. Nuke the packed-refs file (leftover refs that survive update-ref -d
  #    if packed-refs wasn't consulted).
  _step "rm packed-refs" rm -f .git/packed-refs
  # 4. Remove every configured remote (origin, upstream, fork, ...).
  _step "remove remotes" bash -c 'for r in $(git remote 2>/dev/null); do git remote remove "$r" || true; done'
  # 5. Drop stash entries.
  _step "stash clear" git stash clear
  # 6. Remove pseudo-refs that may point at future commits.
  _step "rm pseudo-refs" rm -f .git/ORIG_HEAD .git/FETCH_HEAD .git/MERGE_HEAD .git/CHERRY_PICK_HEAD .git/REVERT_HEAD .git/BISECT_LOG .git/BISECT_START
  # 7. Rebuild a single `main` branch at base_commit so subsequent
  #    `git status`/`git commit` work normally for the Agent.
  _step "checkout -B main" git checkout -B main {bc_q}
  # 8. Expire reflog + delete .git/logs (reflog remembers HEAD@{{N}} = future SHA).
  _step "reflog expire"       git reflog expire --expire=now --all
  _step "rm .git/logs"        rm -rf .git/logs
  # 9. GC to drop unreachable objects. Try aggressive first, fall back to plain.
  _step "gc --aggressive"     bash -c 'git gc --prune=now --aggressive >/dev/null 2>&1 || git gc --prune=now >/dev/null 2>&1'
  # ---------------- assertions ----------------
  _log "----- assertions -----"
  fail=0
  n_remotes="$(git remote 2>/dev/null | wc -l)"
  n_extra_refs="$(git for-each-ref refs/remotes refs/tags refs/pull refs/notes refs/stash refs/replace refs/original 2>/dev/null | wc -l)"
  # refs/heads should contain exactly one entry: refs/heads/main. Anything else
  # (dev, master, feature/*, ...) means step 2's delete didn't finish -- agent
  # could still `git log refs/heads/dev` or grep pack SHAs from there.
  n_extra_heads="$(git for-each-ref refs/heads --format '%(refname)' 2>/dev/null | grep -vx 'refs/heads/main' | wc -l)"
  # Any commit object not reachable from HEAD is a leak -- these are the
  # "future" commits (upstream fix, dev branch tips) that gc failed to prune.
  # `git fsck --unreachable` prints one line per unreachable object; count
  # only commit entries.
  n_unreachable_commits="$(git fsck --unreachable --no-progress 2>/dev/null | grep -c '^unreachable commit')"
  # Pack-level check: enumerate every commit SHA in every pack, subtract the
  # SHAs reachable from HEAD. Anything left is a "future" commit still readable
  # via `git ls-tree`/`git archive`/`git diff a..b` (hook doesn't cover those).
  reachable_shas_file="$(mktemp)"
  pack_shas_file="$(mktemp)"
  git rev-list HEAD 2>/dev/null | sort -u > "$reachable_shas_file"
  for idx in .git/objects/pack/*.idx; do
    [ -e "$idx" ] || continue
    git verify-pack -v "$idx" 2>/dev/null | awk '$2 == "commit" {{print $1}}'
  done | sort -u > "$pack_shas_file"
  n_orphan_pack_shas="$(comm -23 "$pack_shas_file" "$reachable_shas_file" | wc -l)"
  # Sample the first 3 orphan SHAs into the log for diagnostics.
  orphan_sample="$(comm -23 "$pack_shas_file" "$reachable_shas_file" | head -3 | tr '\\n' ' ')"
  rm -f "$reachable_shas_file" "$pack_shas_file"

  _log "assert n_remotes=0            -> got $n_remotes"
  _log "assert n_extra_refs=0         -> got $n_extra_refs"
  _log "assert n_extra_heads=0        -> got $n_extra_heads"
  _log "assert n_unreachable_commits=0-> got $n_unreachable_commits"
  _log "assert n_orphan_pack_shas=0   -> got $n_orphan_pack_shas${{orphan_sample:+  (sample: $orphan_sample)}}"
  [ "$n_remotes" -eq 0 ]             2>/dev/null || fail=1
  [ "$n_extra_refs" -eq 0 ]          2>/dev/null || fail=1
  [ "$n_extra_heads" -eq 0 ]         2>/dev/null || fail=1
  [ "$n_unreachable_commits" -eq 0 ] 2>/dev/null || fail=1
  [ "$n_orphan_pack_shas" -eq 0 ]    2>/dev/null || fail=1
  _log "===== scrub end (fail=$fail) ====="
  exit $fail
}} 2>&1"""


def git_rebuild_command(work_dir: str = "/app") -> str:
    """Nuke .git and rebuild a single-commit history from the current tree.

    Rationale: even after `git_scrub_command`, .git/objects may still contain
    the pre-scrub object database. Aggressive `gc --prune=now` doesn't always
    reclaim reachable-through-reflog objects on some git versions. Rebuilding
    .git from scratch guarantees the container carries exactly one commit
    (equal to the current working tree) — no history, no future, no dangling
    objects to `git fsck --lost-found`.

    Trade-offs are large (base_commit SHA changes; setuptools_scm-style version
    derivation from git tags breaks; any `git blame` inside the agent points
    at the new synthetic commit). Only run this when the caller has decided
    the anti-cheat benefit outweighs those costs.

    Writes the new (synthetic) base commit SHA to /tmp/base_commit.txt and
    prints it on the last line of stdout (`REBUILD_SHA=<sha>`), so the caller
    can capture it and rewire downstream `base_commit` usage.
    """
    wd_q = _shlex.quote(work_dir)
    log_q = _shlex.quote(ANTICHEAT_REBUILD_LOG_PATH)
    return f"""cd {wd_q} && {{
  _log() {{ printf '[%s] %s\\n' "$(date -u +%FT%TZ)" "$*" >> {log_q}; }}
  # _step runs a labelled command, captures stdout+stderr, logs exit code and
  # (on non-zero) the last few output lines. Continues on failure so we
  # accumulate a full trace instead of dying at the first hiccup.
  _step() {{
    local desc="$1"; shift
    local out
    out="$("$@" 2>&1)"; local ec=$?
    if [ $ec -eq 0 ]; then
      _log "step ec=0 [$desc]"
    else
      _log "step ec=$ec [$desc] :: $(printf '%s' \"$out\" | tail -c 500 | tr '\\n' '|')"
    fi
    return $ec
  }}
  _log "===== rebuild start ====="
  _log "env: whoami=$(whoami 2>/dev/null) pwd=$(pwd) uid=$(id -u 2>/dev/null) git=$(git --version 2>&1 | head -1)"
  _log "pre-state: .git exists=$([ -d .git ] && echo yes || echo no), owner=$(stat -c '%U:%G (%u:%g)' .git 2>/dev/null || echo n/a), workdir owner=$(stat -c '%U:%G (%u:%g)' . 2>/dev/null)"
  # Some base images clone /app as a non-root user; running rebuild as root
  # then trips git's dubious-ownership check ("the git repository is to be
  # shared amongst several users..."). Whitelist the workdir before touching
  # .git. Wildcard entry so any subdir also passes.
  _step "config safe.directory workdir" git config --global --add safe.directory {wd_q}
  _step "config safe.directory wildcard" git config --global --add safe.directory '*'
  # Preserve executable bits & symlinks via a tar snapshot (git init/add loses
  # some metadata otherwise; tar-in-tar keeps the tree byte-identical).
  _step "rm -rf .git" rm -rf .git
  # `git init -b <name>` is only in git 2.28+. Older base images (e.g. Ubuntu
  # 18.04 with git 2.17) reject `-b` and fail with "fatal: not in a git
  # directory" -- rebuild silently fails, we fall back to the original SHA,
  # and anti-cheat is weaker than expected. Try modern flag first, fall back
  # to plain init + symbolic-ref rename.
  if git init -q -b main >/dev/null 2>&1; then
    _log "step ec=0 [git init -b main]"
  else
    _step "git init -q (fallback, no -b)" git init -q
    _step "symbolic-ref HEAD -> main" git symbolic-ref HEAD refs/heads/main
  fi
  _log "post-init: .git exists=$([ -d .git ] && echo yes || echo no), branch=$(git symbolic-ref --short HEAD 2>/dev/null)"
  # Silence "cannot spawn hook" from any pre-existing husky/gitleaks etc.
  _step "config core.hooksPath" git config core.hooksPath /dev/null
  # Cheap identity — some git versions refuse to commit without user.email set.
  _step "config user.email" git config user.email "anticheat@local"
  _step "config user.name"  git config user.name  "anticheat"
  _step "git add -A" git add -A
  # allow-empty just in case the working tree is empty for some tasks
  _step "git commit" git commit -q --allow-empty -m "base" --no-verify
  NEW_SHA="$(git rev-parse HEAD 2>/dev/null)"
  RP_EC=$?
  _log "rev-parse HEAD ec=$RP_EC sha=${{NEW_SHA:-<empty>}}"
  echo "$NEW_SHA" > /tmp/base_commit.txt
  # Assertions: exactly one commit, no remotes, no non-HEAD refs.
  fail=0
  n_commits="$(git rev-list --count HEAD 2>/dev/null)"
  n_remotes="$(git remote 2>/dev/null | wc -l)"
  n_extra_refs="$(git for-each-ref refs/remotes refs/tags refs/pull refs/notes refs/stash refs/replace refs/original 2>/dev/null | wc -l)"
  _log "assert n_commits=1    -> got $n_commits"
  _log "assert n_remotes=0    -> got $n_remotes"
  _log "assert n_extra_refs=0 -> got $n_extra_refs"
  [ -n "$NEW_SHA" ] || {{ fail=1; _log "FAIL: empty NEW_SHA (rev-parse failed)"; }}
  [ "$n_commits" = "1" ] || {{ fail=1; _log "FAIL: n_commits != 1"; }}
  [ "$n_remotes" -eq 0 ] 2>/dev/null || {{ fail=1; _log "FAIL: n_remotes != 0 or wc failed"; }}
  [ "$n_extra_refs" -eq 0 ] 2>/dev/null || {{ fail=1; _log "FAIL: n_extra_refs != 0 or wc failed"; }}
  _log "new base_commit=$NEW_SHA"
  _log "===== rebuild end (fail=$fail) ====="
  # Emit on stdout so caller can parse:
  echo "REBUILD_SHA=$NEW_SHA"
  exit $fail
}} 2>&1"""


__all__ = [
    "ANTICHEAT_SCRUB_LOG_PATH",
    "ANTICHEAT_REBUILD_LOG_PATH",
    "ANTICHEAT_BLOCKS_LOG_PATH",
    "ANTICHEAT_FIREWALL_LOG_PATH",
    "REBUILD_GIT",
    "STRICT_SCRUB",
    "git_scrub_command",
    "git_rebuild_command",
]
