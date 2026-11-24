#!/bin/bash
# ============================================================
# 多轮反馈 Loop 单实例入口脚本
#
# 用法:
#   bash run_one_loop.sh \
#     --instance_id go-genai-streamed-function-args \
#     --run_name lisen_loop_test \
#     --max_turns 1
#   可选: --hint_path <path>  指定压缩 hint(留空则自动查找
#         ${OUTPUT_BASE}/${RUN_NAME}/hint_gen/${INSTANCE_ID}/hint_compact.md,
#         找到后以 system-reminder 形式 append 到 system prompt)
#
# 流程: Turn1 解题 → eval → 完成。默认单轮(max_turns=1),
#       可通过 --max_turns N 开启多轮反馈 loop。
# ============================================================

set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# SCRIPT_DIR = <repo>/benchmark/deepswe, CC_RUN_DIR = 仓库根目录
CC_RUN_DIR="$(dirname "$(dirname "${SCRIPT_DIR}")")"

# ==================== 默认值 ====================
INSTANCE_ID="${INSTANCE_ID:-go-genai-streamed-function-args}"
RUN_NAME="${RUN_NAME:-lisen_loop_test}"
MAX_TURNS="${MAX_TURNS:-1}"
MODEL_NAME="${MODEL_NAME:-Qwen3.6-35B-A3B}"
API_BASE="${API_BASE:-http://hubrouter.jd.com}"
API_KEY="${API_KEY:-${HUBROUTER_API_KEY:-}}"
PARQUET_FILE="${PARQUET_FILE:-${CC_RUN_DIR}/deep_swe_tasks.parquet}"
TASKS_DIR="${TASKS_DIR:-/tmp/deep-swe-tasks/tasks}"
OUTPUT_BASE="${OUTPUT_BASE:-${CC_RUN_DIR}/deepswe-output}"
TASK_TIMEOUT="${TASK_TIMEOUT:-7200}"
MEM_LIMIT="${MEM_LIMIT:-128g}"
PROMPT_FILE="${PROMPT_FILE:-${SCRIPT_DIR}/prompts/deep_swe_user_prompt.md}"
PROXY_MAX_TOKENS="${PROXY_MAX_TOKENS:-65536}"
HTTP_PROXY="${HTTP_PROXY:-}"
NO_PROXY="${NO_PROXY:-localhost,127.0.0.1,ai-api.jdcloud.com,hubrouter.jd.com}"
FIRST_INIT="${FIRST_INIT:-false}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SKIP_DOCKER_LOGIN="${SKIP_DOCKER_LOGIN:-false}"
# 压缩 hint 路径(留空则自动查找 ${OUTPUT_BASE}/${RUN_NAME}/hint_gen/${INSTANCE_ID}/hint_compact.md)
HINT_PATH="${HINT_PATH:-}"
# 容器内实时监控轮询间隔(秒,0=禁用):agent 执行期间周期打印 sdk_script.log 增量
MONITOR_INTERVAL="${MONITOR_INTERVAL:-30}"
EXPERIMENT_ARGS=()

# ==================== 参数解析 ====================
while [[ $# -gt 0 ]]; do
    case $1 in
        --instance_id)  INSTANCE_ID="$2";  shift 2 ;;
        --run_name)     RUN_NAME="$2";     shift 2 ;;
        --max_turns)    MAX_TURNS="$2";    shift 2 ;;
        --model_name)   MODEL_NAME="$2";   shift 2 ;;
        --api_base)     API_BASE="$2";     shift 2 ;;
        --api_key)      API_KEY="$2";      shift 2 ;;
        --parquet_file) PARQUET_FILE="$2"; shift 2 ;;
        --tasks_dir)    TASKS_DIR="$2";    shift 2 ;;
        --output_base)  OUTPUT_BASE="$2";  shift 2 ;;
        --task_timeout) TASK_TIMEOUT="$2"; shift 2 ;;
        --mem_limit)    MEM_LIMIT="$2";    shift 2 ;;
        --prompt_file)  PROMPT_FILE="$2";  shift 2 ;;
        --proxy_max_tokens) PROXY_MAX_TOKENS="$2"; shift 2 ;;
        --first_init)   FIRST_INIT="true"; shift ;;
        --hint_path)    HINT_PATH="$2";    shift 2 ;;
        --monitor_interval) MONITOR_INTERVAL="$2"; shift 2 ;;
        --experiment_session|--teacher_progress_url|--teacher_status_url|--container_cpus|--container_memory)
                       EXPERIMENT_ARGS+=("$1" "$2"); shift 2 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

# api_base host 加入 no_proxy
API_HOST=$(echo "$API_BASE" | sed -E 's|^https?://||; s|/.*$||; s|:.*$||')
NO_PROXY="${NO_PROXY},${API_HOST}"

YAML_PATH="/tmp/run_config_loop_${RUN_NAME}.yaml"

echo "============================================================"
echo " 多轮反馈 Loop"
echo "   任务:       ${INSTANCE_ID}"
echo "   实验名称:   ${RUN_NAME}"
echo "   最大轮次:   ${MAX_TURNS}"
echo "   模型:       ${MODEL_NAME}"
echo "   API:        ${API_BASE}"
echo "   输出目录:   ${OUTPUT_BASE}/${RUN_NAME}"
echo "   实时监控:   ${MONITOR_INTERVAL}s 间隔(0=禁用)"
echo "============================================================"

# ==================== Docker 登录 ====================
if [ "$SKIP_DOCKER_LOGIN" != "true" ]; then
    : # Handoff: use existing Docker authentication; login manually before running.
    : # Handoff: use existing Docker authentication; login manually before running.
fi

# ==================== 生成 YAML 配置 ====================
cat > "${YAML_PATH}" << YAML_EOF
routing:
  strategy: weighted_random
  endpoints:
    - name: node-1
      api_base: ${API_BASE}
      provider: openai
      model: ${MODEL_NAME}
      api_key: ${API_KEY}
      weight: 100

verification:
  mode: same_as_execution
  backend: null

proxy:
  listen_base_url: http://localhost:4000
  auth_token: ${API_KEY}
  callbacks_path: /tmp/litellm_call_backs.proxy_handler_instance

container_proxy:
  http_proxy: ${HTTP_PROXY}
  https_proxy: ${HTTP_PROXY}
  no_proxy: ${NO_PROXY}
  HTTP_PROXY: ${HTTP_PROXY}
  HTTPS_PROXY: ${HTTP_PROXY}
  NO_PROXY: ${NO_PROXY}

sdk:
  api_timeout_ms: 6000000
  disable_nonessential_traffic: true
  is_sandbox: true
  first_init: ${FIRST_INIT}
YAML_EOF

echo "生成配置文件: ${YAML_PATH}"

# ==================== 执行 Loop ====================
export TASK_TIMEOUT_SEC=${TASK_TIMEOUT}
export CONTAINER_MEM_LIMIT=${MEM_LIMIT}
export USER_PROMPT_FILE_PATH=${PROMPT_FILE}
export DOCKER_CLIENT_TIMEOUT_SEC=1200
export LOG_LEVEL=DEBUG
export CLAUDE_CODE_AUTO_COMPACT_WINDOW=1000000
export CLAUDE_CODE_MAX_OUTPUT_TOKENS=131072

FIRST_INIT_FLAG=""
if [ "$FIRST_INIT" = "true" ]; then
    FIRST_INIT_FLAG="--first_init"
fi

HINT_PATH_FLAG=()
if [ -n "${HINT_PATH}" ]; then
    HINT_PATH_FLAG=(--hint_path "${HINT_PATH}")
fi

# 题目未解决时 python 返回 1,set -e 会中断,这里临时关闭
set +e
"${PYTHON_BIN}" "${CC_RUN_DIR}/run_multi_turn_loop.py" \
    --instance_id "${INSTANCE_ID}" \
    --run_name "${RUN_NAME}" \
    --parquet_file "${PARQUET_FILE}" \
    --tasks_dir "${TASKS_DIR}" \
    --config "${YAML_PATH}" \
    --output_base "${OUTPUT_BASE}" \
    --max_turns "${MAX_TURNS}" \
    --provider openai \
    --model "${MODEL_NAME}" \
    --api_base "${API_BASE}" \
    --api_key "${API_KEY}" \
    --proxy_max_tokens "${PROXY_MAX_TOKENS}" \
    --monitor_interval "${MONITOR_INTERVAL}" \
    ${FIRST_INIT_FLAG} \
    ${HINT_PATH_FLAG[@]+"${HINT_PATH_FLAG[@]}"} \
    ${EXPERIMENT_ARGS[@]+"${EXPERIMENT_ARGS[@]}"}
LOOP_EXIT=$?
set -e

# 清理临时配置
rm -f "${YAML_PATH}"

echo "Done. (exit=${LOOP_EXIT})"
exit ${LOOP_EXIT}
