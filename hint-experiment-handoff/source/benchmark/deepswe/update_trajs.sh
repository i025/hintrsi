#!/bin/bash
# ============================================================
# update_trajs 一键启动脚本
#
# 调用 update_trajs.py 对轨迹(trajs.json)执行后处理动作:
#   to_openai : trajs.json → message.json (标准 OpenAI 格式)
#   dehint    : 检测并改写 hint 泄漏, 输出到 dehint/ 子目录
#
# 默认指向 deepswe-output/{RUN_NAME}/infer_logs/{INSTANCE_ID}/turn_{TURN}/trajs.json
# 也可用 --input 直接指定文件或目录(递归查找所有 trajs.json)。
#
# 用法:
#   bash update_trajs.sh \
#     --instance_id anko-default-function-arguments \
#     --run_name lisen_hard_by_hint_r1 \
#     --turn 1 \
#     --actions dehint --force
#
#   # 直接指定路径
#   bash update_trajs.sh --input deepswe-output/xxx/turn_1/trajs.json --actions dehint
#
#   # 递归处理整个目录下所有 trajs.json
#   bash update_trajs.sh --input deepswe-output/xxx/infer_logs/ --actions dehint
#
#   # 环境变量方式
#   INSTANCE_ID=xxx TURN=2 ACTIONS=dehint FORCE=true bash update_trajs.sh
# ============================================================

set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# SCRIPT_DIR = <repo>/benchmark/deepswe, CC_RUN_DIR = 仓库根目录
CC_RUN_DIR="$(dirname "$(dirname "${SCRIPT_DIR}")")"

# ==================== 默认值 ====================
INSTANCE_ID="${INSTANCE_ID:-anko-default-function-arguments}"
RUN_NAME="${RUN_NAME:-lisen_hard_by_hint_r1}"
TURN="${TURN:-1}"
INPUT_PATH=""          # 为空则按 OUTPUT_BASE/RUN_NAME/infer_logs/INSTANCE_ID/turn_TURN 构造
OUTPUT_BASE="${OUTPUT_BASE:-${CC_RUN_DIR}/deepswe-output}"
ACTIONS="${ACTIONS:-dehint}"
FORCE="${FORCE:-false}"
# dehint LLM 配置(通过环境变量传给 update_trajs.py)
MODEL_NAME="${MODEL_NAME:-deepseek-v4.1-flash-1017-a}"
API_BASE="${API_BASE:-http://hubrouter.jd.com/v1}"
API_KEY="${API_KEY:-${HUBROUTER_API_KEY:-}}"
MAX_RETRIES="${MAX_RETRIES:-3}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

# ==================== 参数解析 ====================
while [[ $# -gt 0 ]]; do
    case $1 in
        --instance_id) INSTANCE_ID="$2"; shift 2 ;;
        --run_name)    RUN_NAME="$2";    shift 2 ;;
        --turn)        TURN="$2";        shift 2 ;;
        --input)       INPUT_PATH="$2";  shift 2 ;;
        --output_base) OUTPUT_BASE="$2"; shift 2 ;;
        --actions)     ACTIONS="$2";     shift 2 ;;
        --force)       FORCE="true";     shift 1 ;;
        --model_name)  MODEL_NAME="$2";  shift 2 ;;
        --api_base)    API_BASE="$2";    shift 2 ;;
        --api_key)     API_KEY="$2";     shift 2 ;;
        --max_retries) MAX_RETRIES="$2"; shift 2 ;;
        --python_bin)  PYTHON_BIN="$2";  shift 2 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

# ==================== 构造输入路径 ====================
if [ -z "${INPUT_PATH}" ]; then
    INPUT_PATH="${OUTPUT_BASE}/${RUN_NAME}/infer_logs/${INSTANCE_ID}/turn_${TURN}/trajs.json"
fi

# 兼容环境变量 FORCE=true
FORCE_ARG=""
if [ "${FORCE}" = "true" ]; then
    FORCE_ARG="--force"
fi

# ==================== 环境变量传递 dehint 配置 ====================
export DEHINT_MODEL="${MODEL_NAME}"
export DEHINT_API_BASE="${API_BASE}"
export DEHINT_API_KEY="${API_KEY}"
export DEHINT_MAX_RETRIES="${MAX_RETRIES}"

echo "============================================================"
echo " update_trajs"
echo "   输入:       ${INPUT_PATH}"
echo "   动作:       ${ACTIONS}"
echo "   覆盖已有:   ${FORCE}"
echo "   dehint 模型: ${MODEL_NAME} @ ${API_BASE}"
echo "============================================================"

# ==================== 文件检查 ====================
if [ ! -e "${INPUT_PATH}" ]; then
    echo "[ERROR] 输入路径不存在: ${INPUT_PATH}" >&2
    echo "请确认 --instance_id / --run_name / --turn, 或用 --input 直接指定。" >&2
    exit 1
fi

# ==================== 执行 ====================
"${PYTHON_BIN}" "${CC_RUN_DIR}/update_trajs.py" \
    --input "${INPUT_PATH}" \
    --actions "${ACTIONS}" \
    ${FORCE_ARG}

echo "============================================================"
echo " Done."
echo "============================================================"