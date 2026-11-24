#!/bin/bash
# ============================================================
# Hint 生成(容器探索模式)单实例一键启动脚本
#
# 用法:
#   bash run_one_hint.sh \
#     --instance_id go-genai-streamed-function-args \
#     --run_name lisen_hint_test
#
# 流程: 启动容器 → 注入 golden diff + hint prompt →
#       agent 探索代码库 → 收集 hint → 清理容器
# ============================================================

set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# SCRIPT_DIR = <repo>/benchmark/deepswe, CC_RUN_DIR = 仓库根目录
CC_RUN_DIR="$(dirname "$(dirname "${SCRIPT_DIR}")")"

# ==================== 默认值(与 get_hint_by_task.py 默认参数一致) ====================
INSTANCE_ID="${INSTANCE_ID:-go-genai-streamed-function-args}"
RUN_NAME="${RUN_NAME:-lisen_hint_test}"
MODEL_NAME="${MODEL_NAME:-Qwen3.6-35B-A3B}"
# MODEL_NAME="${MODEL_NAME:-deepseek-v4.1-flash-1017-a}"
API_BASE="${API_BASE:-http://hubrouter.jd.com}"
API_KEY="${API_KEY:-${HUBROUTER_API_KEY:-}}"
PARQUET_FILE="${PARQUET_FILE:-${CC_RUN_DIR}/deep_swe_tasks.parquet}"
TASKS_DIR="${TASKS_DIR:-/tmp/deep-swe-tasks/tasks}"
OUTPUT_BASE="${OUTPUT_BASE:-${CC_RUN_DIR}/deepswe-output}"
GOLDEN_DIFF_FILE="${GOLDEN_DIFF_FILE:-}"
HINT_TASK_TIMEOUT="${HINT_TASK_TIMEOUT:-3600}"
MONITOR_INTERVAL="${MONITOR_INTERVAL:-30}"
MEM_LIMIT="${MEM_LIMIT:-128g}"
PROXY_MAX_TOKENS="${PROXY_MAX_TOKENS:-65536}"
SKILLS_PATH="${SKILLS_PATH:-}"
HTTP_PROXY="${HTTP_PROXY:-}"
NO_PROXY="${NO_PROXY:-localhost,127.0.0.1,ai-api.jdcloud.com,hubrouter.jd.com}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SKIP_DOCKER_LOGIN="${SKIP_DOCKER_LOGIN:-false}"

# ==================== 参数解析 ====================
while [[ $# -gt 0 ]]; do
    case $1 in
        --instance_id)      INSTANCE_ID="$2";      shift 2 ;;
        --run_name)         RUN_NAME="$2";         shift 2 ;;
        --model_name)       MODEL_NAME="$2";       shift 2 ;;
        --api_base)         API_BASE="$2";         shift 2 ;;
        --api_key)          API_KEY="$2";          shift 2 ;;
        --parquet_file)     PARQUET_FILE="$2";     shift 2 ;;
        --tasks_dir)        TASKS_DIR="$2";        shift 2 ;;
        --output_base)      OUTPUT_BASE="$2";      shift 2 ;;
        --golden_diff_file) GOLDEN_DIFF_FILE="$2"; shift 2 ;;
        --hint_task_timeout) HINT_TASK_TIMEOUT="$2"; shift 2 ;;
        --monitor_interval)  MONITOR_INTERVAL="$2";  shift 2 ;;
        --mem_limit)        MEM_LIMIT="$2";        shift 2 ;;
        --proxy_max_tokens) PROXY_MAX_TOKENS="$2"; shift 2 ;;
        --skills_path)      SKILLS_PATH="$2";      shift 2 ;;
        --python_bin)       PYTHON_BIN="$2";       shift 2 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

# api_base host 加入 no_proxy
API_HOST=$(echo "$API_BASE" | sed -E 's|^https?://||; s|/.*$||; s|:.*$||')
NO_PROXY="${NO_PROXY},${API_HOST}"

YAML_PATH="/tmp/run_config_hint_${RUN_NAME}.yaml"

echo "============================================================"
echo " Hint 生成(容器探索模式)"
echo "   任务:       ${INSTANCE_ID}"
echo "   实验名称:   ${RUN_NAME}"
echo "   模型:       ${MODEL_NAME}"
echo "   API:        ${API_BASE}"
echo "   Parquet:    ${PARQUET_FILE}"
echo "   Tasks 目录: ${TASKS_DIR}"
echo "   输出目录:   ${OUTPUT_BASE}/${RUN_NAME}/hint_gen/${INSTANCE_ID}"
echo "   超时:       ${HINT_TASK_TIMEOUT}s"
echo "   监控间隔:   ${MONITOR_INTERVAL}s (0=禁用)"
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
  first_init: false
YAML_EOF

echo "生成配置文件: ${YAML_PATH}"

# ==================== 执行 Hint 生成 ====================
export HINT_TASK_TIMEOUT_SEC=${HINT_TASK_TIMEOUT}
export HINT_MONITOR_INTERVAL_SEC=${MONITOR_INTERVAL}
export CONTAINER_MEM_LIMIT=${MEM_LIMIT}
export LOG_LEVEL=DEBUG
export CLAUDE_CODE_AUTO_COMPACT_WINDOW=1000000
export CLAUDE_CODE_MAX_OUTPUT_TOKENS=131072

GOLDEN_DIFF_ARG=()
if [ -n "${GOLDEN_DIFF_FILE}" ]; then
    GOLDEN_DIFF_ARG=(--golden_diff_file "${GOLDEN_DIFF_FILE}")
fi

SKILLS_ARG=()
if [ -n "${SKILLS_PATH}" ]; then
    SKILLS_ARG=(--skills_path "${SKILLS_PATH}")
fi

# hint 生成失败 python 返回 1,set -e 会中断,这里临时关闭
set +e
"${PYTHON_BIN}" "${SCRIPT_DIR}/get_hint_by_task.py" \
    --instance_id "${INSTANCE_ID}" \
    --run_name "${RUN_NAME}" \
    --parquet_file "${PARQUET_FILE}" \
    --tasks_dir "${TASKS_DIR}" \
    --config "${YAML_PATH}" \
    --output_base "${OUTPUT_BASE}" \
    --provider openai \
    --model "${MODEL_NAME}" \
    --api_base "${API_BASE}" \
    --api_key "${API_KEY}" \
    --proxy_max_tokens "${PROXY_MAX_TOKENS}" \
    ${GOLDEN_DIFF_ARG[@]+"${GOLDEN_DIFF_ARG[@]}"} \
    ${SKILLS_ARG[@]+"${SKILLS_ARG[@]}"}
HINT_EXIT=$?
set -e

# 清理临时配置
rm -f "${YAML_PATH}"

echo "Done. (exit=${HINT_EXIT})"
exit ${HINT_EXIT}