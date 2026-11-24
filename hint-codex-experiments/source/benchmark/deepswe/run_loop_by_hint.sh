#!/bin/bash
# ============================================================
# Hint 反馈闭环一键启动脚本 (run_loop_by_hint.py 的封装)
#
# 用法:
#   bash run_loop_by_hint.sh \
#     --instance_id go-genai-streamed-function-args \
#     --run_name lisen_full_loop \
#     --max_rounds 5
#
# 可选:
#   --skip_hint_gen      复用已有 hint_output.md,跳过容器探索生成
#   --skip_docker_login  跳过 docker login(内部子脚本同样跳过)
#   --continue           续跑模式:扫描已有完整轮次(trajs+eval 且未解决),
#                        从下一轮继续;自动复用已有 hint、补做缺失 review
#   --no_hint_run        无 hint 基线模式:只解题+评测,不生成 hint/不压缩/不 review,
#                        用于对比 hint 效果(每 task 仅跑 1 轮)
#   --dry_run            只打印各步骤命令,不实际执行
#
# 流程: 生成 hint → 压缩 → 解题+评测 → (未解决) review →
#       累计压缩 → 再解题 → ... 最多 MAX_ROUNDS 轮,解决即提前终止。
# ============================================================

set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# SCRIPT_DIR = <repo>/benchmark/deepswe, CC_RUN_DIR = 仓库根目录
CC_RUN_DIR="$(dirname "$(dirname "${SCRIPT_DIR}")")"

# ==================== 默认值(与 run_one_loop.sh / run_one_hint.sh 对齐) ====================
INSTANCE_ID="${INSTANCE_ID:-go-genai-streamed-function-args}"
RUN_NAME="${RUN_NAME:-lisen_hint_loop}"
MAX_ROUNDS="${MAX_ROUNDS:-5}"
# MODEL_NAME="${MODEL_NAME:-Qwen3.6-35B-A3B}"
MODEL_NAME="${MODEL_NAME:-deepseek-v4.1-flash-1017-a}"
API_BASE="${API_BASE:-http://hubrouter.jd.com}"
API_KEY="${API_KEY:-${HUBROUTER_API_KEY:-}}"
PARQUET_FILE="${PARQUET_FILE:-${CC_RUN_DIR}/deep_swe_tasks.parquet}"
TASKS_DIR="${TASKS_DIR:-/tmp/deep-swe-tasks/tasks}"
TASKS_URL="${TASKS_URL:-https://joyai-1433141768.cos.ap-beijing.myqcloud.com/huangliang45/tasks.zip}"
OUTPUT_BASE="${OUTPUT_BASE:-${CC_RUN_DIR}/deepswe-output}"
TASK_TIMEOUT="${TASK_TIMEOUT:-7200}"
HINT_TASK_TIMEOUT="${HINT_TASK_TIMEOUT:-3600}"
MONITOR_INTERVAL="${MONITOR_INTERVAL:-30}"
MEM_LIMIT="${MEM_LIMIT:-128g}"
PROXY_MAX_TOKENS="${PROXY_MAX_TOKENS:-65536}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
GOLDEN_DIFF_FILE="${GOLDEN_DIFF_FILE:-}"
SKIP_HINT_GEN="${SKIP_HINT_GEN:-false}"
SKIP_DOCKER_LOGIN="${SKIP_DOCKER_LOGIN:-false}"
CONTINUE_RUN="${CONTINUE_RUN:-false}"
NO_HINT_RUN="${NO_HINT_RUN:-false}"
DRY_RUN="${DRY_RUN:-false}"

# ==================== 参数解析 ====================
while [[ $# -gt 0 ]]; do
    case $1 in
        --instance_id)       INSTANCE_ID="$2";       shift 2 ;;
        --run_name)          RUN_NAME="$2";          shift 2 ;;
        --max_rounds)        MAX_ROUNDS="$2";        shift 2 ;;
        --model_name)        MODEL_NAME="$2";        shift 2 ;;
        --api_base)          API_BASE="$2";          shift 2 ;;
        --api_key)           API_KEY="$2";           shift 2 ;;
        --parquet_file)      PARQUET_FILE="$2";      shift 2 ;;
        --tasks_dir)         TASKS_DIR="$2";         shift 2 ;;
        --tasks_url)         TASKS_URL="$2";         shift 2 ;;
        --output_base)       OUTPUT_BASE="$2";       shift 2 ;;
        --task_timeout)      TASK_TIMEOUT="$2";      shift 2 ;;
        --hint_task_timeout) HINT_TASK_TIMEOUT="$2"; shift 2 ;;
        --monitor_interval)  MONITOR_INTERVAL="$2";  shift 2 ;;
        --mem_limit)         MEM_LIMIT="$2";         shift 2 ;;
        --proxy_max_tokens)  PROXY_MAX_TOKENS="$2";  shift 2 ;;
        --python_bin)        PYTHON_BIN="$2";        shift 2 ;;
        --golden_diff_file)  GOLDEN_DIFF_FILE="$2";  shift 2 ;;
        --skip_hint_gen)     SKIP_HINT_GEN="true";   shift ;;
        --skip_docker_login) SKIP_DOCKER_LOGIN="true"; shift ;;
        --continue)          CONTINUE_RUN="true";    shift ;;
        --no_hint_run)       NO_HINT_RUN="true";     shift ;;
        --dry_run)           DRY_RUN="true";         shift ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

echo "============================================================"
echo " Hint 反馈闭环 (生成→压缩→解题→review→累计压缩→...)"
echo "   任务:       ${INSTANCE_ID}"
echo "   实验名称:   ${RUN_NAME}"
echo "   最大轮次:   ${MAX_ROUNDS}"
echo "   模型:       ${MODEL_NAME}"
echo "   API:        ${API_BASE}"
echo "   输出目录:   ${OUTPUT_BASE}/${RUN_NAME}"
echo "   解题超时:   ${TASK_TIMEOUT}s / hint 生成超时: ${HINT_TASK_TIMEOUT}s"
echo "   实时监控:   ${MONITOR_INTERVAL}s 间隔(0=禁用)"
echo "   跳过 hint 生成: ${SKIP_HINT_GEN}  续跑: ${CONTINUE_RUN}  无hint基线: ${NO_HINT_RUN}  dry_run: ${DRY_RUN}"
echo "============================================================"

# ==================== 准备 Tasks 目录 ====================
# tasks 目录缺失时自动从 COS 下载解压(参考 run_deepswe.sh; /tmp 易失,重启后可自动恢复)
if [ ! -d "${TASKS_DIR}" ]; then
    if [ "${DRY_RUN}" = "true" ]; then
        echo "[WARN] tasks 目录不存在: ${TASKS_DIR} (dry_run 跳过下载,实际运行将自动从 ${TASKS_URL} 下载)"
    else
        LOCAL_TASKS_ZIP="/tmp/$(basename "${TASKS_URL}")"
        if [ ! -f "${LOCAL_TASKS_ZIP}" ]; then
            echo "下载 tasks 包: ${TASKS_URL}"
            wget -q --show-progress -O "${LOCAL_TASKS_ZIP}" "${TASKS_URL}"
        else
            echo "tasks 包已存在: ${LOCAL_TASKS_ZIP}"
        fi
        TASKS_CACHE_DIR="$(dirname "${TASKS_DIR}")"
        echo "解压 tasks 到: ${TASKS_CACHE_DIR}"
        mkdir -p "${TASKS_CACHE_DIR}"
        unzip -q -o "${LOCAL_TASKS_ZIP}" -x "__MACOSX/*" -d "${TASKS_CACHE_DIR}"
        # 兼容: 解压包顶层可能没有多套一层 tasks/
        if [ ! -d "${TASKS_DIR}" ]; then
            TASKS_DIR="${TASKS_CACHE_DIR}"
        fi
        echo "使用 tasks 目录: ${TASKS_DIR}"
    fi
fi

# ==================== Docker 登录 ====================
# 启动脚本登录一次,内部子脚本通过 SKIP_DOCKER_LOGIN=true 跳过,避免每轮重复登录
if [ "$SKIP_DOCKER_LOGIN" != "true" ] && [ "$DRY_RUN" != "true" ]; then
    : # Handoff: use existing Docker authentication; login manually before running.
    : # Handoff: use existing Docker authentication; login manually before running.
    SKIP_DOCKER_LOGIN="true"  # 内部子脚本不再重复登录
fi

# ==================== 组装参数 ====================
EXTRA_ARGS=""
if [ -n "${GOLDEN_DIFF_FILE}" ]; then
    EXTRA_ARGS="${EXTRA_ARGS} --golden_diff_file ${GOLDEN_DIFF_FILE}"
fi
if [ "${SKIP_HINT_GEN}" = "true" ]; then
    EXTRA_ARGS="${EXTRA_ARGS} --skip_hint_gen"
fi
if [ "${SKIP_DOCKER_LOGIN}" = "true" ]; then
    EXTRA_ARGS="${EXTRA_ARGS} --skip_docker_login"
fi
if [ "${CONTINUE_RUN}" = "true" ]; then
    EXTRA_ARGS="${EXTRA_ARGS} --continue"
fi
if [ "${NO_HINT_RUN}" = "true" ]; then
    EXTRA_ARGS="${EXTRA_ARGS} --no_hint_run"
fi
if [ "${DRY_RUN}" = "true" ]; then
    EXTRA_ARGS="${EXTRA_ARGS} --dry_run"
fi

# ==================== 执行闭环 ====================
# exit 0 = solved, 1 = 达到最大轮次未解决(正常), 2 = 步骤异常中断
set +e
"${PYTHON_BIN}" "${SCRIPT_DIR}/run_loop_by_hint.py" \
    --instance_id "${INSTANCE_ID}" \
    --run_name "${RUN_NAME}" \
    --max_rounds "${MAX_ROUNDS}" \
    --parquet_file "${PARQUET_FILE}" \
    --tasks_dir "${TASKS_DIR}" \
    --output_base "${OUTPUT_BASE}" \
    --model_name "${MODEL_NAME}" \
    --api_base "${API_BASE}" \
    --api_key "${API_KEY}" \
    --python_bin "${PYTHON_BIN}" \
    --task_timeout "${TASK_TIMEOUT}" \
    --hint_task_timeout "${HINT_TASK_TIMEOUT}" \
    --monitor_interval "${MONITOR_INTERVAL}" \
    --mem_limit "${MEM_LIMIT}" \
    --proxy_max_tokens "${PROXY_MAX_TOKENS}" \
    ${EXTRA_ARGS}
LOOP_EXIT=$?
set -e

echo "Done. (exit=${LOOP_EXIT})"
exit ${LOOP_EXIT}