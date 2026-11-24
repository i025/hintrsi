#!/bin/bash
# ============================================================
# Review Hint Trajectory 一键启动脚本
#
# 用指定的轨迹(trajs.json)、hint、golden diff 调用
# review_hint_traj.py,让 LLM 审查 agent 是否有效利用了 hint,
# 并输出结构化 JSON(含 corrective_hint)供 compress_hint.py 融合。
#
# 默认指向 deepswe-output/lisen_loop_test/ 目录:
#   trajs:       {OUTPUT_BASE}/{RUN_NAME}/infer_logs/{INSTANCE_ID}/turn_{TURN}/trajs.json
#   hint:        {OUTPUT_BASE}/{RUN_NAME}/hint_gen/{INSTANCE_ID}/hint_compact.md
#   golden_diff: {OUTPUT_BASE}/{RUN_NAME}/hint_gen/{INSTANCE_ID}/golden_diff.diff
#   output md:   {OUTPUT_BASE}/{RUN_NAME}/infer_logs/{INSTANCE_ID}/turn_{TURN}/review_hint_traj.md
#   output json: {OUTPUT_BASE}/{RUN_NAME}/infer_logs/{INSTANCE_ID}/turn_{TURN}/review_hint_traj.json
#
# 用法:
#   bash run_review_hint_traj.sh \
#     --instance_id go-genai-streamed-function-args \
#     --run_name lisen_loop_test \
#     --turn 1
#
#   # 仅压缩轨迹,不调用 LLM
#   bash run_review_hint_traj.sh --dry_run
#
#   # 环境变量方式
#   INSTANCE_ID=xxx TURN=2 bash run_review_hint_traj.sh
# ============================================================

set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# SCRIPT_DIR = <repo>/benchmark/deepswe, CC_RUN_DIR = 仓库根目录
CC_RUN_DIR="$(dirname "$(dirname "${SCRIPT_DIR}")")"

# ==================== 默认值 ====================
INSTANCE_ID="${INSTANCE_ID:-go-genai-streamed-function-args}"
RUN_NAME="${RUN_NAME:-lisen_loop_test}"
TURN="${TURN:-1}"
OUTPUT_BASE="${OUTPUT_BASE:-${CC_RUN_DIR}/deepswe-output}"
MODEL_NAME="${MODEL_NAME:-Qwen3.6-35B-A3B}"
API_BASE="${API_BASE:-http://hubrouter.jd.com/v1}"
API_KEY="${API_KEY:-${HUBROUTER_API_KEY:-}}"
PROVIDER="${PROVIDER:-openai}"
TOOL_RESULT_KEEP="${TOOL_RESULT_KEEP:-500}"
MAX_TOKENS="${MAX_TOKENS:-32000}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
DRY_RUN="false"
SAVE_COMPRESSED="false"

# ==================== 参数解析 ====================
while [[ $# -gt 0 ]]; do
    case $1 in
        --instance_id)      INSTANCE_ID="$2";      shift 2 ;;
        --run_name)         RUN_NAME="$2";         shift 2 ;;
        --turn)             TURN="$2";             shift 2 ;;
        --output_base)      OUTPUT_BASE="$2";      shift 2 ;;
        --model_name)       MODEL_NAME="$2";       shift 2 ;;
        --api_base)         API_BASE="$2";         shift 2 ;;
        --api_key)          API_KEY="$2";          shift 2 ;;
        --provider)         PROVIDER="$2";         shift 2 ;;
        --tool_result_keep) TOOL_RESULT_KEEP="$2"; shift 2 ;;
        --max_tokens)       MAX_TOKENS="$2";       shift 2 ;;
        --python_bin)       PYTHON_BIN="$2";       shift 2 ;;
        --dry_run)          DRY_RUN="true";        shift 1 ;;
        --save_compressed)  SAVE_COMPRESSED="true"; shift 1 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

# ==================== 构造路径 ====================
TRAJS_PATH="${OUTPUT_BASE}/${RUN_NAME}/infer_logs/${INSTANCE_ID}/turn_${TURN}/trajs.json"
HINT_PATH="${OUTPUT_BASE}/${RUN_NAME}/hint_gen/${INSTANCE_ID}/hint_compact.md"
GOLDEN_DIFF_PATH="${OUTPUT_BASE}/${RUN_NAME}/hint_gen/${INSTANCE_ID}/golden_diff.diff"
OUTPUT_MD="${OUTPUT_BASE}/${RUN_NAME}/infer_logs/${INSTANCE_ID}/turn_${TURN}/review_hint_traj.md"
OUTPUT_JSON="${OUTPUT_BASE}/${RUN_NAME}/infer_logs/${INSTANCE_ID}/turn_${TURN}/review_hint_traj.json"

echo "============================================================"
echo " Review Hint Trajectory"
echo "   实例:       ${INSTANCE_ID}"
echo "   实验名称:   ${RUN_NAME}"
echo "   Turn:       ${TURN}"
echo "   轨迹:       ${TRAJS_PATH}"
echo "   Hint:       ${HINT_PATH}"
echo "   Golden Diff: ${GOLDEN_DIFF_PATH}"
echo "   模型:       ${MODEL_NAME} @ ${API_BASE}"
echo "   dry_run:    ${DRY_RUN}"
echo "============================================================"

# ==================== 文件检查 ====================
MISSING=0
if [ ! -f "${TRAJS_PATH}" ]; then
    echo "[ERROR] trajs 不存在: ${TRAJS_PATH}" >&2
    MISSING=1
fi
if [ ! -f "${HINT_PATH}" ]; then
    echo "[ERROR] hint 不存在: ${HINT_PATH}" >&2
    MISSING=1
fi
if [ ! -f "${GOLDEN_DIFF_PATH}" ]; then
    echo "[ERROR] golden_diff 不存在: ${GOLDEN_DIFF_PATH}" >&2
    MISSING=1
fi
if [ "${MISSING}" -eq 1 ]; then
    echo "请确认 --instance_id / --run_name / --turn 是否正确。" >&2
    exit 1
fi

# ==================== 组装参数 ====================
EXTRA_ARGS=""
if [ "${DRY_RUN}" = "true" ]; then
    EXTRA_ARGS="${EXTRA_ARGS} --dry_run"
fi
if [ "${SAVE_COMPRESSED}" = "true" ]; then
    EXTRA_ARGS="${EXTRA_ARGS} --save_compressed"
fi

# ==================== 执行 ====================
"${PYTHON_BIN}" "${SCRIPT_DIR}/review_hint_traj.py" \
    --trajs "${TRAJS_PATH}" \
    --hint "${HINT_PATH}" \
    --golden_diff "${GOLDEN_DIFF_PATH}" \
    --output "${OUTPUT_MD}" \
    --json_output "${OUTPUT_JSON}" \
    --tool_result_keep "${TOOL_RESULT_KEEP}" \
    --max_tokens "${MAX_TOKENS}" \
    --model "${MODEL_NAME}" \
    --api_base "${API_BASE}" \
    --api_key "${API_KEY}" \
    --provider "${PROVIDER}" \
    ${EXTRA_ARGS}

echo "============================================================"
echo " Done."
echo "   Markdown: ${OUTPUT_MD}"
echo "   JSON:     ${OUTPUT_JSON}"
echo "============================================================"