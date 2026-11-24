
import os

INSTANCE_ID = os.getenv("INSTANCE_ID_COL_NAME", "instance_id")
IMAGE_NAME = os.getenv("IMAGE_NAME_COL_NAME", "image_name")
PROBLEM_STATEMENT = os.getenv("PROBLEM_STATEMENT_COL_NAME", "problem_statement")
INTERFACE = os.getenv("INTERFACE_COL_NAME", "interface")
INSTALLATION_COMMAND = os.getenv("INSTALLATION_COMMAND_COL_NAME", "installation_command")
BASE_COMMIT = os.getenv("BASE_COMMIT_COL_NAME", "base_commit")
TEST_PATCH = os.getenv("TEST_PATCH_COL_NAME", "pre_patch")
FAIL_TO_PASS = os.getenv("FAIL_TO_PASS_COL_NAME", "FAIL_TO_PASS")
PASS_TO_PASS = os.getenv("PASS_TO_PASS_COL_NAME", "PASS_TO_PASS")

# --- LLM summary-check retry parameters (is_text_a_summary, utils.py) ---
# Max attempts (including the first call) for the LLM summary check.
LLM_SUMMARY_CHECK_MAX_RETRIES = max(1, int(os.getenv("LLM_SUMMARY_CHECK_MAX_RETRIES", "3")))
# Initial backoff between retries, in seconds (exponential: base * 2^(attempt-1)).
LLM_SUMMARY_CHECK_BACKOFF_BASE_SEC = float(os.getenv("LLM_SUMMARY_CHECK_BACKOFF_BASE_SEC", "5"))
# Upper bound for a single backoff sleep, in seconds.
LLM_SUMMARY_CHECK_BACKOFF_MAX_SEC = float(os.getenv("LLM_SUMMARY_CHECK_BACKOFF_MAX_SEC", "60"))


def render_proxy_config(
    provider: str,
    model: str,
    api_key: str,
    api_base: str,
    callbacks_path: str = "/tmp/litellm_call_backs.proxy_handler_instance",
    reasoning_effort: str = "",
    thinking_budget: str = "",
    max_tokens: int = 131072,
) -> str:
    # Anthropic-native path: use `thinking={type:enabled, budget_tokens:N}`.
    # `reasoning_effort` and `chat_template_kwargs` are ignored by Anthropic
    # (they belong to vLLM/sglang chat templates). Response comes back as
    # content=[{type:thinking, thinking, signature}, {type:text,...}] and the
    # signature MUST be preserved across turns — see claude_code_proxy.py's
    # _is_anthropic_route branch which skips the reasoning_content downgrade.
    if provider == "anthropic":
        try:
            budget = int(thinking_budget) if thinking_budget else 32000
        except ValueError:
            budget = 32000
        # Anthropic requires max_tokens > budget_tokens; give ample headroom.
        max_tok = max(64000, budget * 2)
        template = """model_list:
  - model_name: "*"
    litellm_params:
      model: {provider}/{model}
      api_key: {api_key}
      api_base: {api_base}
      max_tokens: {max_tok}
      timeout: 6000
      stream_timeout: 600
      thinking:
        type: enabled
        budget_tokens: {budget}
      allow_external: true
  - model_name: "claude-haiku-4-5-20251001"
    litellm_params:
      model: {provider}/{model}
      api_key: {api_key}
      api_base: {api_base}
      max_tokens: {max_tok}
      timeout: 6000
      stream_timeout: 600
      thinking:
        type: enabled
        budget_tokens: {budget}
      allow_external: true

litellm_settings:
  set_verbose: true
  drop_params: true
  callbacks:
    - {callbacks_path}"""
        return template.format(
            provider=provider, model=model, api_key=api_key, api_base=api_base,
            max_tok=max_tok, budget=budget, callbacks_path=callbacks_path,
        )

    # NOTE: chat_template_kwargs MUST be indented under extra_body — it's not
    # a top-level litellm_params field. Prior versions had a YAML indent bug
    # that put chat_template_kwargs at the same level as extra_body (rendering
    # `extra_body: null` and orphaning chat_template_kwargs at litellm_params
    # level), which litellm silently drops via drop_params=true. Result:
    # enable_thinking/drop_thinking/reasoning_effort never reached the backend.
    re_line = f"\n          reasoning_effort: {reasoning_effort}" if reasoning_effort else ""
    return f"""model_list:
  - model_name: "*"
    litellm_params:
      model: {provider}/{model}
      api_key: {api_key}
      api_base: {api_base}
      max_tokens: {max_tokens}
      temperature: 1.0
      top_p: 0.95
      timeout: 6000
      stream_timeout: 600
      extra_body:
        chat_template_kwargs:
          thinking: true
          drop_thinking: false
          enable_thinking: true
          clear_thinking: false
          preserve_thinking: true{re_line}
        allow_external: true
        thinking:
          type: "enabled"
          keep: "all"
  - model_name: "claude-haiku-4-5-20251001"
    litellm_params:
      model: {provider}/{model}
      api_key: {api_key}
      api_base: {api_base}
      max_tokens: {max_tokens}
      temperature: 1.0
      top_p: 0.95
      timeout: 6000
      stream_timeout: 600
      extra_body:
        chat_template_kwargs:
          thinking: true
          drop_thinking: false
          enable_thinking: true
          clear_thinking: false
          preserve_thinking: true{re_line}
        allow_external: true
        thinking:
          type: "enabled"
          keep: "all"

litellm_settings:
  set_verbose: true
  drop_params: true
  callbacks:
    - {callbacks_path}"""


INSTALL_SCRIPT = r"""#!/bin/bash
# Anti-cheat isolation (hosts blackhole, gh removal, PreToolUse hook,
# iptables firewall) is applied at the END of this script -- AFTER apt/pip/
# npm have finished pulling their dependencies. Doing it up front breaks
# package installs on any base image that legitimately reaches github.com
# or pypi.org during bootstrap.

PIP_FLAGS="--break-system-packages --ignore-installed"
PY_DIR=/opt/python3.12-tmp
if command -v apt-get &> /dev/null; then
  echo "Detected apt-get (Debian/Ubuntu)"
  # Handle new DEB822 format (bookworm+): /etc/apt/sources.list.d/debian.sources
  if [ -f /etc/apt/sources.list.d/debian.sources ]; then
    sed -i 's|deb.debian.org|mirrors.cloud.tencent.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true
    sed -i 's|security.debian.org|mirrors.cloud.tencent.com/debian-security|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true
  fi
  # Handle legacy format: /etc/apt/sources.list
  sed -i 's|mirrors.jd.com|mirrors.cloud.tencent.com|g' /etc/apt/sources.list 2>/dev/null || true
  sed -i 's|deb.debian.org|mirrors.cloud.tencent.com|g' /etc/apt/sources.list 2>/dev/null || true
  sed -i 's|security.debian.org/debian-security|mirrors.cloud.tencent.com/debian-security|g' /etc/apt/sources.list 2>/dev/null || true
  sed -i 's|security.debian.org|mirrors.cloud.tencent.com/debian-security|g' /etc/apt/sources.list 2>/dev/null || true
  sed -i 's|archive.ubuntu.com|mirrors.cloud.tencent.com|g' /etc/apt/sources.list 2>/dev/null || true
  sed -i 's|security.ubuntu.com|mirrors.cloud.tencent.com|g' /etc/apt/sources.list 2>/dev/null || true
  # Also handle .list files in sources.list.d
  for f in /etc/apt/sources.list.d/*.list; do
    [ -f "$f" ] && sed -i 's|deb.debian.org|mirrors.cloud.tencent.com|g' "$f" 2>/dev/null || true
  done
  # apt uses the tencent-cloud mirror (internal, directly reachable). Going
  # via the container-injected http_proxy (`221.194.188.92:3128`) is slower
  # and sporadically fails with `Connection failed [IP: <proxy>]`. Clear
  # the proxy env just for this apt invocation.
  # rustc/cargo needed for building tiktoken from sdist when the pypi mirror
  # lacks a py3.12 wheel (seen on bionic + mirrors.cloud.tencent.com). Install
  # only when rustc is missing so newer images pay no extra cost, and don't
  # fail hard if apt can't find it -- the hard check after pip will catch it.
  # ripgrep is best-effort: not in bionic's default repos, safe to skip.
  # Don't hard-fail if a security-mirror package 404s (versions roll and the
  # pinned .deb disappears). --fix-missing installs what it can; the curl
  # fallback in the Python bootstrap and the pip hard-check below catch gaps.
  http_proxy= https_proxy= HTTP_PROXY= HTTPS_PROXY= apt-get update 2>/dev/null || true
  http_proxy= https_proxy= HTTP_PROXY= HTTPS_PROXY= apt-get install -y --fix-missing curl wget tar gzip ca-certificates || true
  (http_proxy= https_proxy= HTTP_PROXY= HTTPS_PROXY= apt-get install -y ripgrep || true)
  (command -v rustc >/dev/null 2>&1 || http_proxy= https_proxy= HTTP_PROXY= HTTPS_PROXY= apt-get install -y rustc cargo || true)
elif command -v yum &> /dev/null; then
  echo "Detected yum (RHEL/CentOS)"
  yum install -y curl wget tar gzip ca-certificates yum-utils
  yum-config-manager --add-repo=https://copr.fedorainfracloud.org/coprs/carlwgeorge/ripgrep/repo/epel-7/carlwgeorge-ripgrep-epel-7.repo
  yum install -y ripgrep
elif command -v dnf &> /dev/null; then
  echo "Detected dnf (Fedora/RHEL 8+)"
  dnf install -y curl wget tar gzip ca-certificates ripgrep
elif command -v apk &> /dev/null; then
  echo "Detected apk (Alpine)"
  sed -i 's|dl-cdn.alpinelinux.org|mirrors.cloud.tencent.com|g' /etc/apk/repositories 2>/dev/null || true
  http_proxy="" https_proxy="" HTTP_PROXY="" HTTPS_PROXY="" apk add --no-cache curl \
    wget \
    tar \
    gzip \
    ca-certificates \
    build-base \
    gcc \
    g++ \
    musl-dev \
    make \
    cmake \
    libffi-dev \
    openssl-dev \
    openssl \
    coreutils \
    ripgrep \
    zlib-dev \
    bzip2-dev \
    readline-dev \
    sqlite-dev \
    xz-dev \
    tk-dev \
    rust \
    cargo \
    nodejs \
    npm
else
  echo "Warning: No known package manager found. Assuming curl/wget are already installed."
fi

PY_DIR=/opt/python3.12-tmp
if command -v apk &> /dev/null; then
  echo "Detected apk (Alpine)"
  mkdir -p /opt/python3.12-tmp/bin
  # 设置安装目录
  INSTALL_DIR="/opt/python3.12-tmp"
  mkdir -p "${INSTALL_DIR}"

  # 下载 Python 3.12
  cd /tmp
  PYTHON_VERSION="3.12.9"  # 使用最新的 3.12 版本
  wget "https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz"
  tar -xzf "Python-${PYTHON_VERSION}.tgz"
  cd "Python-${PYTHON_VERSION}"

  ./configure \
    --prefix="${INSTALL_DIR}" \
    --enable-loadable-sqlite-extensions

  # 编译安装
  make -j$(nproc)
  make install

  echo "Python 安装位置: ${INSTALL_DIR}"
  ${INSTALL_DIR}/bin/python3 --version
  ${INSTALL_DIR}/bin/pip3 --version
elif [ ! -x "$PY_DIR/bin/pip3" ]; then
  echo "Bootstrapping standalone Python 3.12 into $PY_DIR ..."
  mkdir -p /opt
  TARBALL=/tmp/cpython-3.12.tar.gz
  URL="https://joyai-1433141768.cos.ap-beijing.myqcloud.com/huangliang45/cpython-3.12.7%2B20241016-x86_64-unknown-linux-gnu-install_only.tar.gz"
  http_proxy="" https_proxy="" wget --tries=3 -O "$TARBALL" "$URL" || \
    http_proxy="" https_proxy="" curl -fSL --retry 3 -o "$TARBALL" "$URL"
  tar -xzf "$TARBALL" -C /opt
  mv /opt/python "$PY_DIR"
  "$PY_DIR/bin/python3" -m ensurepip --upgrade || true
  "$PY_DIR/bin/pip3" install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn || true
fi

if [ -n "${http_proxy:-}" ]; then
  export http_proxy
  export HTTP_PROXY="$http_proxy"
fi

if [ -n "${https_proxy:-}" ]; then
  export https_proxy
  export HTTPS_PROXY="$https_proxy"
fi

if [ -n "${no_proxy:-}" ]; then
  export no_proxy
  export NO_PROXY="$no_proxy"
fi

# Pre-install tiktoken pinned to <0.12 before litellm resolves its dependency
# tree. litellm 1.81.8 only requires tiktoken>=0.7.0, so pinning to a prebuilt
# wheel avoids the sdist compilation. Necessary because:
#   - tiktoken >=0.13 uses Cargo edition "2024" (needs rustc >= 1.85), which
#     Ubuntu bionic's apt-mirror never gets (stuck at rustc 1.65).
#   - tiktoken 0.11.0 ships a py3.12 manylinux wheel on both tencent and tuna,
#     so no compilation is needed at all.
# Best-effort (|| true): if this fails on some image, the main pip block below
# still runs; the final hard-check will surface any real problem.
(http_proxy="" https_proxy="" /opt/python3.12-tmp/bin/pip3 install "tiktoken>=0.7.0,<0.12" -i https://mirrors.cloud.tencent.com/pypi/simple --trusted-host mirrors.cloud.tencent.com --proxy "" \
 || http_proxy="" https_proxy="" /opt/python3.12-tmp/bin/pip3 install "tiktoken>=0.7.0,<0.12" -i https://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com --proxy "") || true

if http_proxy="" https_proxy="" /opt/python3.12-tmp/bin/pip3 install litellm==1.81.8 "claude-agent-sdk>=0.1.60" -i https://mirrors.cloud.tencent.com/pypi/simple --trusted-host mirrors.cloud.tencent.com --proxy "" && \
   http_proxy="" https_proxy="" /opt/python3.12-tmp/bin/pip3 install "litellm[proxy]" anyio -i https://mirrors.cloud.tencent.com/pypi/simple --trusted-host mirrors.cloud.tencent.com --proxy "" ; then
    echo "Install succeeded (tencent)."
elif http_proxy="" https_proxy="" /opt/python3.12-tmp/bin/pip3 install litellm==1.81.8 "claude-agent-sdk>=0.1.60" -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn --proxy "" && \
     http_proxy="" https_proxy="" /opt/python3.12-tmp/bin/pip3 install "litellm[proxy]" anyio -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn --proxy "" ; then
    echo "Install succeeded (tuna fallback)."
else
    echo "Install failed, trying local wheel fallback..."
    mkdir -p /tmp/wheels

    http_proxy="" https_proxy="" /opt/python3.12-tmp/bin/pip3 download litellm==1.81.8 "litellm[proxy]" "claude-agent-sdk>=0.1.60" anyio \
        --only-binary=:all: \
        --platform manylinux2014_x86_64 \
        --python-version 3.12 \
        --abi cp312 \
        -d /tmp/wheels \
        -i https://mirrors.cloud.tencent.com/pypi/simple --trusted-host mirrors.cloud.tencent.com --proxy ""

    cd /tmp/wheels
    for f in *.whl; do
        [ -e "$f" ] || continue
        if [[ "$f" == *"manylinux"* ]]; then
            mv "$f" "${f/manylinux*/linux_x86_64.whl}"
        fi
    done
    cd /tmp

    http_proxy="" https_proxy="" /opt/python3.12-tmp/bin/pip3 install --no-index --find-links=/tmp/wheels /tmp/wheels/*.whl --proxy ""
fi

# Hard-check that the Python deps actually installed. install.sh has no
# `set -e`, and the pip fallbacks above can all fail (e.g. bionic + missing
# Rust breaks tiktoken wheel build, tuna mirror lacks claude-agent-sdk, empty
# /tmp/wheels glob expands to a literal '*'). Without this check the runner
# would report install_done ok=true and the SDK would blow up on
# `ModuleNotFoundError: No module named 'anyio'` up to `max_validation_retries`
# times per task. Fail fast so the runner's 3-retry loop actually kicks in.
if ! /opt/python3.12-tmp/bin/python3 -c "import anyio, litellm, claude_agent_sdk" 2>/dev/null; then
    echo "FATAL: python deps missing after install.sh pip stage"
    /opt/python3.12-tmp/bin/pip3 list 2>&1 | grep -iE "anyio|litellm|claude-agent-sdk|tiktoken" || echo "(none of anyio/litellm/claude-agent-sdk installed)"
    exit 1
fi

# http_proxy="" https_proxy="" /opt/python3.12-tmp/bin/pip3 install litellm==1.81.8 "claude-agent-sdk>=0.1.60" -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn --proxy ""
# http_proxy="" https_proxy="" /opt/python3.12-tmp/bin/pip3 install "litellm[proxy]" anyio -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn --proxy ""
if command -v apk &> /dev/null; then
  http_proxy="" https_proxy="" /opt/python3.12-tmp/bin/pip3 install $PIP_FLAGS litellm==1.81.8 --no-binary litellm==1.81.8 -i https://pypi.tuna.tsinghua.edu.cn/simple
  http_proxy="" https_proxy="" /opt/python3.12-tmp/bin/pip3 install $PIP_FLAGS --no-binary claude-agent-sdk "claude-agent-sdk>=0.1.60" -i https://pypi.tuna.tsinghua.edu.cn/simple
  # 全局安装 claude-code
  rm -rf /usr/local/lib/node_modules/@anthropic-ai/claude-code
  npm config set registry https://registry.npmmirror.com/
  http_proxy="" https_proxy="" npm install -g @anthropic-ai/claude-code@2.1.177 --unsafe-perm --force
  export PATH="$HOME/node_modules/.bin:$PATH"
fi
PYTHONPATH="/tmp:$PYTHONPATH" LITELLM_LOG=DEBUG nohup /opt/python3.12-tmp/bin/litellm --config /tmp/config.yaml > /tmp/proxy.log 2>&1 &
echo "Waiting for litellm proxy to be ready..."
for i in $(seq 1 60); do
  if curl -s -o /dev/null -w '%{http_code}' http://localhost:4000/health 2>/dev/null | grep -q '200'; then
    echo "litellm proxy ready after ${i}s"
    break
  fi
  sleep 1
done

mkdir -p /app/.claude/skills
if [ -f /tmp/skills.tar.gz ]; then
  tar -xzvf /tmp/skills.tar.gz -C /app/.claude/skills --strip-components=1
fi

mkdir -p ~/.claude/skills
if [ -f /tmp/skills.tar.gz ]; then
  tar -xzvf /tmp/skills.tar.gz -C ~/.claude/skills --strip-components=1
fi

# ---------------------------------------------------------------------------
# Anti-cheat network isolation (applied AFTER apt/pip/npm/skills so package
# managers can still reach github/pypi/npmjs during install).
#
# Trajectory analysis of a prior batch showed 100% of runs reached for the
# upstream fix via github.com / raw.githubusercontent.com / gh CLI / Google /
# web.archive.org / jsdelivr, etc. Point every known source-lookup host at
# localhost so curl/wget/git/gh all fail closed once the Agent starts.
# Package mirrors (pypi.tuna, goproxy.cn, mirrors.cloud.tencent.com) are NOT
# in this list.
# ---------------------------------------------------------------------------
_BLOCK_HOSTS=(
  # GitHub surface (WebFetch/curl/wget/gh/git-clone all funnel through these)
  github.com www.github.com api.github.com codeload.github.com
  raw.githubusercontent.com objects.githubusercontent.com
  gist.github.com gist.githubusercontent.com
  patch-diff.githubusercontent.com uploads.github.com media.githubusercontent.com
  # GitHub-backed CDNs
  cdn.jsdelivr.net jsdelivr.net fastly.jsdelivr.net gcore.jsdelivr.net
  unpkg.com www.unpkg.com
  # Alternative source hosts
  gitlab.com www.gitlab.com bitbucket.org api.bitbucket.org
  git.videolan.org git.ffmpeg.org sourceforge.net
  # Web archive (used to bypass github blocks)
  web.archive.org archive.org
  # Search engines
  www.google.com google.com www.bing.com bing.com
  duckduckgo.com www.duckduckgo.com search.brave.com
  # NOTE: public package registries (pypi.org, registry.npmjs.org,
  # proxy.golang.org, crates.io, rubygems.org, pkg.go.dev, ...) are
  # NOT blocked. They were briefly on this list, but per-task
  # `installation_command`s (`pip install .`, PEP 517 build backends,
  # `go get`, ...) hit them via the default index-url and got Connection
  # refused, breaking installs. Cheating audit showed these hosts are a
  # very low-frequency leak channel (~1% vs github's 100%), so the
  # trade-off isn't worth it.
)
{
  echo ""
  echo "# --- anti-cheat network isolation (install.sh) ---"
  for h in "${_BLOCK_HOSTS[@]}"; do
    echo "127.0.0.1 ${h}"
  done
} >> /etc/hosts

# CRITICAL: append the blocked hosts to NO_PROXY as well. Without this, any
# process that respects http_proxy (curl, git via libcurl, pip, wget, ...)
# will send `CONNECT <host>:443` to the http_proxy, and the *proxy* resolves
# the hostname -- completely bypassing /etc/hosts. With NO_PROXY containing
# the host, the client resolves locally, hits 127.0.0.1, and fails closed.
_block_csv="$(printf '%s,' "${_BLOCK_HOSTS[@]}" | sed 's/,$//')"
# /etc/environment is read by PAM on shell login; ENV vars set here persist
# into every new bash/sh the Agent launches (SDK spawns each Bash tool via
# `/bin/bash -c ...`, which re-reads /etc/environment).
{
  echo ""
  echo "# --- anti-cheat: force curl/git/pip to bypass proxy for blocked hosts ---"
  # Preserve any existing NO_PROXY value the container was launched with.
  existing_no_proxy="${NO_PROXY:-${no_proxy:-}}"
  if [ -n "$existing_no_proxy" ]; then
    combined="${existing_no_proxy},${_block_csv}"
  else
    combined="${_block_csv}"
  fi
  echo "NO_PROXY=\"${combined}\""
  echo "no_proxy=\"${combined}\""
} >> /etc/environment
# Also drop a /etc/profile.d fragment so *interactive* shells (which bypass
# /etc/environment) still pick it up.
mkdir -p /etc/profile.d
cat > /etc/profile.d/99-anticheat-noproxy.sh <<PROFILE_EOF
# Extend NO_PROXY with anti-cheat blocked hosts so curl/git bypass the
# http_proxy (which would otherwise resolve the hostname remotely and defeat
# /etc/hosts).
_ANTICHEAT_HOSTS="${_block_csv}"
if [ -n "\${NO_PROXY:-}" ]; then
  export NO_PROXY="\${NO_PROXY},\${_ANTICHEAT_HOSTS}"
else
  export NO_PROXY="\${_ANTICHEAT_HOSTS}"
fi
export no_proxy="\${NO_PROXY}"
unset _ANTICHEAT_HOSTS
PROFILE_EOF
chmod +x /etc/profile.d/99-anticheat-noproxy.sh

# Remove `gh` if the base image shipped it -- second-most-used leak channel
# after WebFetch (32.9% of sampled runs).
for gh_path in /usr/bin/gh /usr/local/bin/gh /opt/gh/bin/gh; do
  [ -x "${gh_path}" ] && rm -f "${gh_path}" || true
done
if command -v apt-get &> /dev/null; then apt-get remove -y gh 2>/dev/null || true; fi
if command -v yum     &> /dev/null; then yum remove    -y gh 2>/dev/null || true; fi
if command -v dnf     &> /dev/null; then dnf remove    -y gh 2>/dev/null || true; fi

# ---------------------------------------------------------------------------
# Anti-cheat PreToolUse hook.
#
# Belt-and-braces after the DNS blackhole above: catch Bash commands that
# look like they're reaching for the upstream answer (gh/git-clone/curl
# github/git log --all/git show <sha>/git ls-remote/git fetch upstream, etc.)
# and deny them before they execute. Runs as a Claude Code PreToolUse hook
# via ~/.claude/settings.json.
#
# CRITICAL: install under $HOME/.claude, NOT /app/.claude. `_install_and_reset`
# runs `git clean -fd` in /app after this script, which would wipe untracked
# directories like /app/.claude/ before the Agent even starts. $HOME/.claude
# lives outside the repo and is untouched by git clean.
# ---------------------------------------------------------------------------
_CLAUDE_HOOK_DIR="$HOME/.claude/hooks"
_CLAUDE_HOOK="$_CLAUDE_HOOK_DIR/deny_cheat.sh"
_CLAUDE_SETTINGS="$HOME/.claude/settings.json"
mkdir -p "$_CLAUDE_HOOK_DIR"
cat > "$_CLAUDE_HOOK" <<'HOOK_EOF'
#!/usr/bin/env bash
# stdin: JSON from Claude Code with {tool_name, tool_input:{command,...}}
# stdout (on block): {"decision":"block","reason":"..."} and exit 0
set -u
input="$(cat)"
tool="$(printf '%s' "$input" | /opt/python3.12-tmp/bin/python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get("tool_name",""))' 2>/dev/null || true)"
if [ "$tool" != "Bash" ]; then
  exit 0
fi
cmd="$(printf '%s' "$input" | /opt/python3.12-tmp/bin/python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get("tool_input",{}).get("command",""))' 2>/dev/null || true)"

# Patterns that indicate reaching for the upstream answer instead of solving
# the task from the local codebase. Extend cautiously - too broad breaks
# normal builds (`go get`, `pip install`, `curl localhost:...` are fine).
block_reason=""
case "$cmd" in
  *"gh pr"*|*"gh api"*|*"gh search"*|*"gh issue"*|*"gh repo"*|*"gh browse"*|*"gh commit"*)
    block_reason="gh CLI is disabled for this task (upstream lookup)";;
  *"git clone "*http*|*"git clone "*git@*)
    block_reason="cloning external repositories is disabled (upstream lookup)";;
  *"git ls-remote"*|*"git remote add"*|*"git remote set-url"*)
    block_reason="adding/inspecting remotes is disabled (upstream lookup)";;
  *"git fetch "*origin*|*"git fetch --all"*|*"git fetch "*upstream*)
    block_reason="git fetch is disabled - no remotes are configured";;
esac

if [ -z "$block_reason" ]; then
  # `git log --all/--branches/refs/` clearly walks outside the current
  # branch -> block. Keep plain `git log` (base_commit ancestors only)
  # working so agents can still inspect the local history.
  if printf '%s' "$cmd" | grep -Eq 'git[[:space:]]+log([[:space:]]|$).*(--all|--branches|origin/|upstream/|refs/)'; then
    block_reason="git log across remotes/refs is disabled (upstream lookup)"
  # `git cat-file --batch-all-objects` (any combination with --batch /
  # --batch-check) enumerates every object in .git/objects, including
  # blobs from the pre-scrub tree that gc failed to prune. Observed in
  # production: agents run this to list ~3000 blob SHAs, then `cat-file -p`
  # each one grepping for "In reply to" / "SIZE_RANGES" / feature-string
  # of the F2P test until they find the upstream fix's implementation.
  # No legitimate task needs to enumerate the full object database, so
  # block outright.
  elif printf '%s' "$cmd" | grep -Eq 'git[[:space:]]+cat-file[[:space:]]+([^|;]*[[:space:]])?--batch-all-objects'; then
    block_reason="git cat-file --batch-all-objects is disabled (upstream object enumeration)"
  # `git cat-file --batch` / `--batch-check` reads a SHA list from stdin
  # (typically a heredoc). Same attack shape as --batch-all-objects but
  # sourced from an external list -- e.g. one derived from --batch-all-objects
  # then piped to `cat-file --batch` for the actual content dump. Block
  # unconditionally; single-SHA reads should use `git cat-file -p <sha>`,
  # which is separately gated by the ancestry check further down.
  elif printf '%s' "$cmd" | grep -Eq 'git[[:space:]]+cat-file[[:space:]]+([^|;]*[[:space:]])?--batch(-check)?([[:space:]]|$)'; then
    block_reason="git cat-file --batch / --batch-check is disabled (upstream object enumeration)"
  # `git reflog` exposes SHAs from HEAD's history, including the pre-scrub
  # main branch tip (the "Execution Snapshot" commit that ran before scrub).
  # Once the agent knows that SHA it can `git show <sha>:path` -- the
  # ancestry check below catches SHA-based leaks, but the reflog itself
  # gives them the SHA to try. Block the whole family (reflog, reflog show,
  # reflog expire is only run by scrub itself, not by the agent).
  elif printf '%s' "$cmd" | grep -Eq 'git[[:space:]]+reflog([[:space:]]|$)'; then
    block_reason="git reflog is disabled (leaks pre-scrub commit SHAs)"
  # `git show <sha>` and `git cat-file ... <sha>` are OK when <sha> is a
  # base_commit ancestor (normal historical lookup), and blocked when it
  # points at a "future" commit (the upstream fix, whose object may still
  # be in .git/ if `git gc --prune` failed -- happens ~15% of the time).
  # We look up the SHA against `base_commit` (recorded to
  # /tmp/base_commit.txt by sdk_script before the Agent starts). If the
  # SHA is unresolvable or unreachable from base_commit, we block.
  #
  # `[0-9a-f]{7,40}` alone matches too aggressively (any hex-looking token
  # anywhere in the cmd). We check every candidate SHA that appears after
  # a `git show` / `git cat-file` token in the command -- if ANY of them
  # is out-of-ancestry, block.
  elif printf '%s' "$cmd" | grep -Eq 'git[[:space:]]+(show|cat-file)[[:space:]]'; then
    base="$(cat /tmp/base_commit.txt 2>/dev/null | tr -d '[:space:]')"
    if [ -n "$base" ]; then
      # Extract every 7-40 hex token from the cmd; check each against base.
      # Loop so a single "future" SHA is enough to block, even in complex
      # compound commands like `for obj in a b c; do git cat-file -p $obj ...`
      for sha in $(printf '%s' "$cmd" | grep -oE '\b[0-9a-f]{7,40}\b'); do
        if ( cd /app && git merge-base --is-ancestor "$sha" "$base" 2>/dev/null ); then
          continue  # ancestor of base -> legit
        fi
        if ( cd /app && git cat-file -e "$sha" 2>/dev/null ); then
          block_reason="git show/cat-file for SHA outside base_commit ancestry is disabled (upstream commit)"
          break
        fi
      done
    fi
  # `git fsck --unreachable` / `git fsck --dangling` lists exactly the
  # objects scrub tried to strip but that gc may not have pruned yet.
  # The output is a menu of SHAs for cat-file to read.
  elif printf '%s' "$cmd" | grep -Eq 'git[[:space:]]+fsck[[:space:]]+.*(--unreachable|--dangling|--lost-found)'; then
    block_reason="git fsck --unreachable/--dangling is disabled (upstream object enumeration)"
  # `git rev-list --all` / `git rev-list --branches --remotes` enumerates
  # every reachable commit, including ones scrub missed.
  elif printf '%s' "$cmd" | grep -Eq 'git[[:space:]]+rev-list[[:space:]]+[^"|;]*(--all|--branches|--remotes|--reflog)'; then
    block_reason="git rev-list --all is disabled (upstream commit enumeration)"
  # `git fetch <url>` bypasses named remotes (no need to `remote add`
  # first). Any fetch that references http(s)://, git://, git@host: or a
  # bare host:path syntax is disallowed.
  elif printf '%s' "$cmd" | grep -Eq 'git[[:space:]]+fetch[[:space:]]+([^[:space:]]*://|git@|[A-Za-z0-9.-]+:[A-Za-z0-9])'; then
    block_reason="git fetch from a URL is disabled (upstream lookup)"
  # Same for `git pull <url>` / `git ls-remote <url>` — same shape.
  elif printf '%s' "$cmd" | grep -Eq 'git[[:space:]]+(pull|ls-remote)[[:space:]]+([^[:space:]]*://|git@|[A-Za-z0-9.-]+:[A-Za-z0-9])'; then
    block_reason="git pull/ls-remote from a URL is disabled (upstream lookup)"
  elif printf '%s' "$cmd" | grep -Eq '(curl|wget)[[:space:]].*https?://[^[:space:]]*(github|githubusercontent|gitlab|bitbucket|jsdelivr|unpkg|web\.archive|google\.com/search|bing\.com)'; then
    block_reason="fetching from source-code hosts / search engines is disabled"
  # Numeric-IP HTTP requests bypass the /etc/hosts blackhole. Block any
  # curl/wget/git to a dotted-quad or IPv6 literal.
  elif printf '%s' "$cmd" | grep -Eq '(curl|wget|git[[:space:]]+(clone|fetch|pull|ls-remote))[[:space:]].*(https?://[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}|https?://\[[0-9a-fA-F:]+\])'; then
    block_reason="direct-IP network access is disabled (DNS-blackhole bypass)"
  # Package registry metadata queries reveal the version in which the
  # upstream fix landed -> narrows the search to a specific changelog /
  # release. Block the introspection subcommands only; keep normal
  # `pip install`, `npm install`, `go get` etc. usable for builds.
  elif printf '%s' "$cmd" | grep -Eq 'pip[[:space:]]+(index[[:space:]]+versions|search)([[:space:]]|$)'; then
    block_reason="pip index/search is disabled (reveals upstream fixed version)"
  # `pip download <pkg>==<ver>` fetches the source/wheel of ANY published
  # version from PyPI -- effectively `git clone` for Python. Observed in
  # production: the agent binary-searched versions (1.4.0 -> 1.7.0 -> 1.7.5)
  # to locate the fix commit's release. Block downloads that pin a version
  # or use --no-binary/--no-deps (both signal "I want the source"). Plain
  # `pip download <pkg>` without a pin is rare and still blocked -- if
  # someone needs a wheel for build, they'd `pip install` it.
  elif printf '%s' "$cmd" | grep -Eq 'pip[[:space:]]+download([[:space:]]|$)'; then
    block_reason="pip download is disabled (fetches upstream package sources)"
  # `npm pack <pkg>` fetches a tarball of any registry version -- same
  # attack shape as `pip download`.
  elif printf '%s' "$cmd" | grep -Eq 'npm[[:space:]]+pack([[:space:]]|$)'; then
    block_reason="npm pack is disabled (fetches upstream package tarball)"
  elif printf '%s' "$cmd" | grep -Eq 'npm[[:space:]]+(view|info)([[:space:]]|$)'; then
    block_reason="npm view/info is disabled (reveals upstream fixed version)"
  elif printf '%s' "$cmd" | grep -Eq 'yarn[[:space:]]+info([[:space:]]|$)'; then
    block_reason="yarn info is disabled (reveals upstream fixed version)"
  elif printf '%s' "$cmd" | grep -Eq 'gem[[:space:]]+(list|info|search)[[:space:]]+-r'; then
    block_reason="gem list/info -r is disabled (reveals upstream fixed version)"
  elif printf '%s' "$cmd" | grep -Eq 'cargo[[:space:]]+(search|owner)([[:space:]]|$)'; then
    block_reason="cargo search/owner is disabled (reveals upstream fixed version)"
  elif printf '%s' "$cmd" | grep -Eq 'go[[:space:]]+list[[:space:]]+[^"]{0,60}(-versions|-m[[:space:]]+-versions|@latest)'; then
    block_reason="go list -m -versions is disabled (reveals upstream fixed version)"
  elif printf '%s' "$cmd" | grep -Eq 'composer[[:space:]]+show[[:space:]]+-a'; then
    block_reason="composer show -a is disabled (reveals upstream fixed version)"
  # Python/node one-liner network fetches bypass curl/wget matchers.
  elif printf '%s' "$cmd" | grep -Eq '(python[0-9.]*|node)[[:space:]]+-c[[:space:]]+.*urlopen|(python[0-9.]*|node)[[:space:]]+-c[[:space:]]+.*requests\.get|(python[0-9.]*|node)[[:space:]]+-c[[:space:]]+.*http\.client'; then
    block_reason="python/node one-liner network fetch is disabled (curl/wget bypass)"
  fi
fi

if [ -n "$block_reason" ]; then
  printf '{"decision":"block","reason":"%s. Solve the task from the local codebase; the upstream fix is not available."}\n' "$block_reason"
  # Log the attempt for later analysis
  {
    printf '[%s] BLOCKED: %s\n' "$(date -u +%FT%TZ)" "$block_reason"
    printf '  cmd: %s\n' "$cmd"
  } >> /tmp/anticheat_blocks.log 2>/dev/null || true
fi
exit 0
HOOK_EOF
chmod +x "$_CLAUDE_HOOK"

cat > "$_CLAUDE_SETTINGS" <<'SETTINGS_EOF'
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {"type": "command", "command": "HOOK_PATH_PLACEHOLDER"}
        ]
      }
    ]
  }
}
SETTINGS_EOF
# `matcher: "Bash"` + placeholder path substitution -- avoids a nested heredoc
# so the settings.json above is a plain literal and easy to inspect.
sed -i "s|HOOK_PATH_PLACEHOLDER|${_CLAUDE_HOOK}|g" "$_CLAUDE_SETTINGS"

# ---------------------------------------------------------------------------
# Anti-cheat firewall (belt-and-braces, last).
#
# hosts-blackhole covers DNS lookups but not literal-IP requests, and the
# PreToolUse hook can be worked around by pipes/subshells. iptables OUTPUT
# ACCEPT-only for (a) loopback (litellm proxy on localhost:4000), (b) the
# upstream LLM/http proxy hosts the runner injects into no_proxy, and (c)
# DNS -- everything else is DROP.
#
# Best-effort: if iptables isn't in the base image, we skip. If capabilities
# don't allow adding rules, we skip. In both cases the earlier layers still
# apply, and we log so the runner can see the state after install.
# ---------------------------------------------------------------------------
if command -v iptables >/dev/null 2>&1; then
  # Extract the whitelist from NO_PROXY (the runner sets this to include
  # llm/proxy hosts). Add any bare IP or hostname that resolves, plus DNS.
  _fw_allow_hosts=""
  if [ -n "${NO_PROXY:-}${no_proxy:-}" ]; then
    _fw_allow_hosts="$(printf '%s,%s' "${NO_PROXY:-}" "${no_proxy:-}" | tr ',' '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | grep -v '^$' | grep -v '^localhost$' | grep -v '^127\.' || true)"
  fi
  # Also allow the http(s)_proxy hosts themselves.
  for _proxy_env in "${http_proxy:-}" "${https_proxy:-}" "${HTTP_PROXY:-}" "${HTTPS_PROXY:-}"; do
    [ -z "$_proxy_env" ] && continue
    # http://host:port -> host
    _h="$(printf '%s' "$_proxy_env" | sed -E 's#^https?://##; s#/.*$##; s#:[0-9]+$##')"
    [ -n "$_h" ] && _fw_allow_hosts="$_fw_allow_hosts
$_h"
  done

  echo "===== anti-cheat firewall install =====" >> /tmp/anticheat_firewall.log
  echo "allow-hosts:" >> /tmp/anticheat_firewall.log
  printf '  %s\n' $_fw_allow_hosts >> /tmp/anticheat_firewall.log

  # Try to install rules. Any failure -> log and continue (never break the
  # runner over firewall issues).
  {
    iptables -N ANTICHEAT_OUT 2>/dev/null || iptables -F ANTICHEAT_OUT
    # loopback -> ACCEPT (litellm proxy at 127.0.0.1:4000)
    iptables -A ANTICHEAT_OUT -o lo -j ACCEPT
    iptables -A ANTICHEAT_OUT -d 127.0.0.0/8 -j ACCEPT
    # DNS -> ACCEPT (still needed for the proxy hostnames)
    iptables -A ANTICHEAT_OUT -p udp --dport 53 -j ACCEPT
    iptables -A ANTICHEAT_OUT -p tcp --dport 53 -j ACCEPT
    # Established connections (return path)
    iptables -A ANTICHEAT_OUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
    # Whitelisted proxy/llm hosts
    for _h in $_fw_allow_hosts; do
      [ -z "$_h" ] && continue
      if printf '%s' "$_h" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
        iptables -A ANTICHEAT_OUT -d "$_h" -j ACCEPT
      else
        # Resolve now and whitelist all A records
        for _ip in $(getent ahostsv4 "$_h" 2>/dev/null | awk '{print $1}' | sort -u); do
          iptables -A ANTICHEAT_OUT -d "$_ip" -j ACCEPT
        done
      fi
    done
    # Everything else -> DROP + log the block
    iptables -A ANTICHEAT_OUT -j LOG --log-prefix "ANTICHEAT-DROP: " --log-level 4 || true
    iptables -A ANTICHEAT_OUT -j REJECT --reject-with icmp-net-prohibited || iptables -A ANTICHEAT_OUT -j DROP
    # Hook the chain into OUTPUT (only once)
    iptables -C OUTPUT -j ANTICHEAT_OUT 2>/dev/null || iptables -I OUTPUT 1 -j ANTICHEAT_OUT
    iptables -S ANTICHEAT_OUT >> /tmp/anticheat_firewall.log 2>&1
    echo "OK" >> /tmp/anticheat_firewall.log
  } 2>>/tmp/anticheat_firewall.log || echo "FAILED (probably missing NET_ADMIN cap)" >> /tmp/anticheat_firewall.log
else
  echo "iptables not available, skipping firewall layer" >> /tmp/anticheat_firewall.log
fi
"""

