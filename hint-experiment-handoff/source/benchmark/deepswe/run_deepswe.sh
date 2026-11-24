#!/bin/bash
# ============================================================
# DeepSWE 多机分片评测脚本 (基于 cc-run)
#
# 用法:
#   bash run_deepswe.sh \
#     --model_name joycode \
#     --api_base http://11.137.96.250:30333/v1 \
#     --world_size 1 \
#     --node_rank 0 \
#     --run_name 0714_joycode \
#     --cc_run_dir /mnt/joyai/huangliang45/cc-run \
#     --output_base /mnt/joyai/huangliang45/deepswe-output
#
# 必选参数:
#   --model_name     模型名称 (如 joycode, glm5.1)
#   --api_base       模型服务地址 (如 http://11.137.96.250:30333/v1)
#   --world_size     总机器数
#   --run_name       本次实验名称，用于输出目录命名
#   --cc_run_dir     cc-run 项目路径
#   --output_base    输出根目录 (轨迹和评测结果保存位置)
#
# 可选参数:
#   --node_rank      当前机器编号 (默认: 从 hostname 尾缀自动获取)
#   --parquet_file   数据文件路径或 URL (默认: COS 上的 deep_swe_tasks.parquet)
#   --tasks_dir      DeepSWE tasks 目录 (默认: 从 --tasks_url 下载解压)
#   --tasks_url      DeepSWE tasks 打包 zip 的 URL (默认: COS 上的 tasks.zip)
#   --api_key        API Key
#   --max_workers    每节点并发数 (默认: 12)
#   --prefetch_workers 镜像预拉取并发数 (默认: 3)
#   --task_timeout   Agent 超时秒数 (默认: 14400，即 4 小时)
#   --mem_limit      容器内存限制 (默认: 32g)
#   --prompt_file    User Prompt 文件路径 (默认: benchmark/deepswe/prompts/deep_swe_user_prompt.md)
#   --http_proxy     HTTP 代理 (默认: http://221.194.188.92:3128)
#   --no_proxy       不走代理的地址 (默认: 已预设)
#   --first_init     是否先执行 /init (默认: false)
#   --eval_workers   评测阶段并发数 (默认: 10)
#   --skip_rollout   跳过 rollout 阶段，只做评测
#   --skip_eval      跳过评测阶段，只做 rollout
# ============================================================

set -euo pipefail
umask 077

# ==================== 启动 Docker Daemon (DinD) ====================
if ! docker info >/dev/null 2>&1; then
    echo "启动 Docker daemon..."
    dockerd &>/var/log/dockerd.log &
    echo "等待 Docker daemon 就绪..."
    for i in $(seq 1 60); do
        if docker info >/dev/null 2>&1; then
            echo "Docker daemon 就绪 (${i}s)"
            break
        fi
        if [ "$i" = "60" ]; then
            echo "Docker daemon 启动超时"
            exit 1
        fi
        sleep 1
    done
fi

# ==================== 默认值（支持环境变量覆盖） ====================
MODEL_NAME="${MODEL_NAME:-}"
API_BASE="${API_BASE:-}"
WORLD_SIZE="${WORLD_SIZE:-}"
NODE_RANK="${NODE_RANK:-${HOSTNAME##*-}}"
RUN_NAME="${RUN_NAME:-}"

PARQUET_FILE="${PARQUET_FILE:-https://joyai-1433141768.cos.ap-beijing.myqcloud.com/huangliang45/deep_swe_tasks.parquet}"
TASKS_DIR="${TASKS_DIR:-}"
TASKS_URL="${TASKS_URL:-https://joyai-1433141768.cos.ap-beijing.myqcloud.com/huangliang45/tasks.zip}"
API_KEY="${API_KEY:-nFPUmIQ7L9WN08hiskt0RKpwHlrXTpwM}"
MAX_WORKERS="${MAX_WORKERS:-12}"
PREFETCH_WORKERS="${PREFETCH_WORKERS:-3}"
TASK_TIMEOUT="${TASK_TIMEOUT:-14400}"
MEM_LIMIT="${MEM_LIMIT:-32g}"
PROMPT_FILE="${PROMPT_FILE:-}"
HTTP_PROXY="${HTTP_PROXY:-}"
NO_PROXY="${NO_PROXY:-localhost,127.0.0.1,ai-api.jdcloud.com,11.137.96.250,6.202.148.102,180.184.148.148,6.178.132.119}"
FIRST_INIT="${FIRST_INIT:-false}"
EVAL_WORKERS="${EVAL_WORKERS:-10}"
SKIP_ROLLOUT="${SKIP_ROLLOUT:-false}"
SKIP_EVAL="${SKIP_EVAL:-false}"
CC_RUN_DIR="${CC_RUN_DIR:-}"
OUTPUT_BASE="${OUTPUT_BASE:-}"

# ==================== 参数解析 ====================
while [[ $# -gt 0 ]]; do
    case $1 in
        --model_name)     MODEL_NAME="$2";     shift 2 ;;
        --api_base)       API_BASE="$2";       shift 2 ;;
        --world_size)     WORLD_SIZE="$2";     shift 2 ;;
        --node_rank)      NODE_RANK="$2";      shift 2 ;;
        --run_name)       RUN_NAME="$2";       shift 2 ;;
        --parquet_file)   PARQUET_FILE="$2";   shift 2 ;;
        --tasks_dir)      TASKS_DIR="$2";      shift 2 ;;
        --tasks_url)      TASKS_URL="$2";      shift 2 ;;
        --api_key)        API_KEY="$2";        shift 2 ;;
        --max_workers)    MAX_WORKERS="$2";    shift 2 ;;
        --prefetch_workers) PREFETCH_WORKERS="$2"; shift 2 ;;
        --task_timeout)   TASK_TIMEOUT="$2";   shift 2 ;;
        --mem_limit)      MEM_LIMIT="$2";      shift 2 ;;
        --prompt_file)    PROMPT_FILE="$2";    shift 2 ;;
        --http_proxy)     HTTP_PROXY="$2";     shift 2 ;;
        --no_proxy)       NO_PROXY="$2";       shift 2 ;;
        --first_init)     FIRST_INIT="true";   shift ;;
        --eval_workers)   EVAL_WORKERS="$2";   shift 2 ;;
        --skip_rollout)   SKIP_ROLLOUT=true;   shift ;;
        --skip_eval)      SKIP_EVAL=true;      shift ;;
        --cc_run_dir)     CC_RUN_DIR="$2";     shift 2 ;;
        --output_base)    OUTPUT_BASE="$2";    shift 2 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

# ==================== 参数校验 ====================
missing=""
[ -z "$MODEL_NAME" ]    && missing="$missing --model_name"
[ -z "$API_BASE" ]      && missing="$missing --api_base"
[ -z "$WORLD_SIZE" ]    && missing="$missing --world_size"
[ -z "$NODE_RANK" ]     && missing="$missing --node_rank"
[ -z "$RUN_NAME" ]      && missing="$missing --run_name"
[ -z "$CC_RUN_DIR" ]    && missing="$missing --cc_run_dir"
[ -z "$OUTPUT_BASE" ]   && missing="$missing --output_base"

if [ -n "$missing" ]; then
    echo "缺少必选参数:$missing"
    echo "用法: bash run_deepswe.sh --model_name MODEL --api_base URL --world_size N --run_name NAME --cc_run_dir PATH --output_base PATH [--node_rank R]"
    exit 1
fi

# tasks_dir 默认走 tasks_url 自动下载解压
[ -z "$PROMPT_FILE" ]  && PROMPT_FILE="${CC_RUN_DIR}/benchmark/deepswe/prompts/deep_swe_user_prompt.md"

# 从 api_base 提取 host 加入 no_proxy
# 之前用 `cut -d: -f1` 只去 port，不去路径 — 结果类似
# `hubrouter.jd.com/v1` 会作为 no_proxy 条目，而 no_proxy 只识别
# 主机名/域名，带 `/path` 的条目永远不匹配，请求就走 https_proxy 挂掉。
# 用 sed 一步去掉 scheme、path、port,只留 host。
API_HOST=$(echo "$API_BASE" | sed -E 's|^https?://||; s|/.*$||; s|:.*$||')
NO_PROXY="${NO_PROXY},${API_HOST}"

OUTPUT_DIR="${OUTPUT_BASE}/${RUN_NAME}"
YAML_PATH="/tmp/run_config_deepswe_${RUN_NAME}_node${NODE_RANK}.yaml"

echo "============================================================"
echo " DeepSWE 评测"
echo "   实验名称:   ${RUN_NAME}"
echo "   模型:       ${MODEL_NAME}"
echo "   API:        ${API_BASE}"
echo "   分片:       ${NODE_RANK}/${WORLD_SIZE}"
echo "   Parquet:    ${PARQUET_FILE}"
echo "   Tasks 目录: ${TASKS_DIR}"
echo "   输出目录:   ${OUTPUT_DIR}"
echo "   并发数:     ${MAX_WORKERS}"
echo "============================================================"

# ==================== Docker 登录 ====================
echo "使用当前 Docker 登录配置（请先手动登录所需镜像仓库）"
: # Handoff: use existing Docker authentication; login manually before running.
: # Handoff: use existing Docker authentication; login manually before running.
: # Handoff: use existing Docker authentication; login manually before running.
# Handoff: runner cleans its own containers; no global cleanup.

# ==================== 下载 Parquet 数据 (如果是 URL) ====================
if [[ "$PARQUET_FILE" == http* ]]; then
    LOCAL_PARQUET="/tmp/$(basename "${PARQUET_FILE}")"
    if [ ! -f "${LOCAL_PARQUET}" ]; then
        echo "下载数据文件: ${PARQUET_FILE}"
        wget -q --show-progress -O "${LOCAL_PARQUET}" "${PARQUET_FILE}"
    else
        echo "数据文件已存在: ${LOCAL_PARQUET}"
    fi
    PARQUET_FILE="${LOCAL_PARQUET}"
fi

# ==================== 准备 Tasks 目录 ====================
# 优先级: --tasks_dir 显式指定 > 自动从 --tasks_url 下载解压
if [ -z "$TASKS_DIR" ]; then
    TASKS_CACHE_DIR="/tmp/deep-swe-tasks"
    LOCAL_TASKS_ZIP="/tmp/$(basename "${TASKS_URL}")"

    if [ ! -d "${TASKS_CACHE_DIR}/tasks" ]; then
        if [ ! -f "${LOCAL_TASKS_ZIP}" ]; then
            echo "下载 tasks 包: ${TASKS_URL}"
            wget -q --show-progress -O "${LOCAL_TASKS_ZIP}" "${TASKS_URL}"
        else
            echo "tasks 包已存在: ${LOCAL_TASKS_ZIP}"
        fi
        echo "解压 tasks 到: ${TASKS_CACHE_DIR}"
        mkdir -p "${TASKS_CACHE_DIR}"
        unzip -q -o "${LOCAL_TASKS_ZIP}" -d "${TASKS_CACHE_DIR}"
    else
        echo "tasks 缓存已存在: ${TASKS_CACHE_DIR}/tasks"
    fi

    if [ -d "${TASKS_CACHE_DIR}/tasks" ]; then
        TASKS_DIR="${TASKS_CACHE_DIR}/tasks"
    else
        # 兼容：解压包在顶层就是任务目录（没有多套一层 tasks/）
        TASKS_DIR="${TASKS_CACHE_DIR}"
    fi
    echo "使用 tasks 目录: ${TASKS_DIR}"
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

# ==================== 阶段1: Rollout ====================
if [ "$SKIP_ROLLOUT" = false ]; then
    echo ""
    echo "==================== 阶段1: Rollout ===================="

    export TASK_TIMEOUT_SEC=${TASK_TIMEOUT}
    export CONTAINER_MEM_LIMIT=${MEM_LIMIT}
    export USER_PROMPT_FILE_PATH=${PROMPT_FILE}
    export DOCKER_CLIENT_TIMEOUT_SEC=1200
    export LOG_LEVEL=DEBUG

    export INSTANCE_ID="instance_id"
    export IMAGE_NAME="image_name"
    export PROBLEM_STATEMENT="problem_statement"
    export INSTALLATION_COMMAND="installation_command"
    export BASE_COMMIT="base_commit"
    export TEST_PATCH="pre_patch"
    export FAIL_TO_PASS_COL_NAME="FAIL_TO_PASS"
    export PASS_TO_PASS_COL_NAME="PASS_TO_PASS"
    export CLAUDE_CODE_AUTO_COMPACT_WINDOW=1000000
    export CLAUDE_CODE_MAX_OUTPUT_TOKENS=131072
    
    "${PYTHON_BIN:-python3}" "${CC_RUN_DIR}/run_cc_trajs_swe_pro.py" \
        --parquet_file "${PARQUET_FILE}" \
        --output_path "${OUTPUT_DIR}" \
        --res_sdk_script "${CC_RUN_DIR}/run_cc_sdk.py" \
        --res_litellm_callbacks "${CC_RUN_DIR}/litellm_proxy/claude_code_proxy.py" \
        --config "${YAML_PATH}" \
        --world_size "${WORLD_SIZE}" \
        --node_rank "${NODE_RANK}" \
        --max_workers "${MAX_WORKERS}" \
        --prefetch_workers "${PREFETCH_WORKERS}" \
        --max_validation_retries 1 \
        --force_remove_container \
        --remove_finished_images

    echo "Rollout 完成: ${OUTPUT_DIR}"

    # 写入完成标记
    mkdir -p "${OUTPUT_DIR}/sync"
    echo "done" > "${OUTPUT_DIR}/sync/node_${NODE_RANK}.done"
    echo "节点 ${NODE_RANK} rollout 完成，已写入标记: ${OUTPUT_DIR}/sync/node_${NODE_RANK}.done"
fi

# ==================== 阶段2: 评测 ====================
if [ "$SKIP_EVAL" = false ]; then
    # 多机模式：等待所有节点 rollout 完成
    if [ "$WORLD_SIZE" -gt 1 ]; then
        echo ""
        echo "==================== 等待所有节点完成 Rollout ===================="
        while true; do
            done_count=0
            for r in $(seq 0 $((WORLD_SIZE - 1))); do
                if [ -f "${OUTPUT_DIR}/sync/node_${r}.done" ]; then
                    done_count=$((done_count + 1))
                fi
            done
            echo "$(date '+%H:%M:%S') 已完成: ${done_count}/${WORLD_SIZE}"
            if [ "$done_count" -ge "$WORLD_SIZE" ]; then
                echo "所有节点 rollout 完成"
                break
            fi
            sleep 30
        done

        # 只在 rank 0 上执行评测
        if [ "$NODE_RANK" != "0" ]; then
            echo "当前节点 node_rank=${NODE_RANK}，评测由 node_rank=0 执行，退出"
            exit 0
        fi
    fi

    echo ""
    echo "==================== 阶段2: 评测 ===================="

    EVAL_OUTPUT_DIR="${OUTPUT_DIR}/eval_output"

    "${PYTHON_BIN:-python3}" "${CC_RUN_DIR}/benchmark/deepswe/eval_deep_swe.py" \
        --tasks_dir "${TASKS_DIR}" \
        --patches_dir "${OUTPUT_DIR}/infer_logs" \
        --output_dir "${EVAL_OUTPUT_DIR}" \
        --num_workers "${EVAL_WORKERS}"

    echo ""
    echo "==================== 评测完成 ===================="
    echo "结果目录: ${EVAL_OUTPUT_DIR}"
    echo "汇总文件: ${EVAL_OUTPUT_DIR}/summary.json"
fi

# 清理临时配置
rm -f "${YAML_PATH}"

echo "Done."

# 防止容器退出后被 K8s 重启
sleep infinity
