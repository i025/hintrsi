> 本文件是上游通用 DeepSWE 说明，示例使用其他分支与历史机器路径。Hint 交接包请从 [运行指南](../../../docs/运行指南.md) 开始。

# DeepSWE 评测

使用 cc-run 框架对 [DeepSWE](https://deepswe.datacurve.ai/) 榜单进行多机分片评测。

DeepSWE 是 datacurve 发布的长时程 SWE Agent 评测集，共 113 道题，覆盖 TypeScript / Go / Python / JavaScript / Rust 五种语言。每道题带有一个 Harbor 格式的沙箱环境，评分时会重新拉起 verifier 容器执行内置的 `test.sh`，产出 `reward.json`。

## 前置条件

- 运行镜像：`is.jd.com/jdea-middleware/cc-run-dind:v1.1`
- 容器需开启**特权级模式**（Docker-in-Docker 需要）
- 挂载路径：cc-run 项目目录、deep-swe 评测项目目录需挂载到容器内
- 模型服务已部署（vLLM / sglang）

## 代码准备

```bash
# cc-run（使用 benchmark-dev 分支）
git clone -b benchmark-dev git@coding.jd.com:coding-ai/cc-run.git

# DeepSWE 评测工程（包含 tasks/ 与已构建好的 parquet 数据）
# 官方仓库：https://github.com/datacurve-ai/deep-swe
# 内部整理后的评测目录（含 deep_swe_tasks.parquet、tasks/、pull_and_tag_push_image.py 等）
#   /mnt/joyai/huangliang45/deep-swe
```

### 路径参数设置

假设你把代码放在 `/mnt/joyai/username/`：

```
/mnt/joyai/username/
├── cc-run/                  # --cc_run_dir 指向这里
└── deepswe-output/          # --output_base 指向这里（自动创建）
```

- `--cc_run_dir`：cc-run 项目根目录，脚本从中读取 `run_cc_trajs_swe_pro.py`、`run_cc_sdk.py`、`litellm_proxy/`、`benchmark/deepswe/eval_deep_swe.py` 等
- `--output_base`：轨迹与评测结果的输出根目录，每次实验在其下创建 `{run_name}/`

数据说明：
- **Parquet（rollout 用）**：默认走 COS 上的 [`deep_swe_tasks.parquet`](https://joyai-1433141768.cos.ap-beijing.myqcloud.com/huangliang45/deep_swe_tasks.parquet)，脚本自动下载到 `/tmp`，也可用 `--parquet_file` 覆盖为本地路径或其它 URL。
- **Tasks 目录（评测用）**：默认从 COS 上的 [`tasks.zip`](https://joyai-1433141768.cos.ap-beijing.myqcloud.com/huangliang45/tasks.zip) 下载 + 解压到 `/tmp/deep-swe-tasks/`，也可用 `--tasks_dir` 直接指向本地已解压的 tasks 目录，或用 `--tasks_url` 覆盖下载 URL。

## 快速开始

### 单机运行

```bash
bash run_deepswe.sh \
  --model_name joycode \
  --api_base http://11.137.96.250:30333/v1 \
  --world_size 1 \
  --node_rank 0 \
  --run_name 0714_joycode \
  --cc_run_dir /mnt/joyai/huangliang45/cc-run \
  --output_base /mnt/joyai/huangliang45/deepswe-output
```

### 多机分片

每台机器执行同一条命令，`node_rank` 从 hostname 尾缀自动获取：

```bash
bash run_deepswe.sh \
  --model_name joycode \
  --api_base http://11.137.96.250:30333/v1 \
  --world_size 4 \
  --run_name 0714_joycode \
  --cc_run_dir /mnt/joyai/huangliang45/cc-run \
  --output_base /mnt/joyai/huangliang45/deepswe-output
```

所有分片完成后（rank=0 会自动等待），rank=0 上会自动执行评测。若只想单独跑一次评测，加 `--skip_rollout`：

```bash
bash run_deepswe.sh \
  --model_name joycode \
  --api_base http://11.137.96.250:30333/v1 \
  --world_size 4 \
  --run_name 0714_joycode \
  --cc_run_dir /mnt/joyai/huangliang45/cc-run \
  --output_base /mnt/joyai/huangliang45/deepswe-output \
  --skip_rollout
```

### 腾讯云容器服务

**运行命令：** `/bin/bash`

**运行参数：**（每行一个）
```
-c
```

```
/mnt/joyai/huangliang45/cc-run/benchmark/deepswe/run_deepswe.sh --model_name joycode --api_base http://180.184.148.148:12345/v1 --world_size 2 --run_name 0714_joycode --cc_run_dir /mnt/joyai/huangliang45/cc-run --output_base /mnt/joyai/huangliang45/deepswe-output
```

使用 StatefulSet 部署时，`node_rank` 会自动从 Pod hostname（如 `job-0`、`job-1`）获取。

## 参数说明

### 必选参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--model_name` | 模型名称 | `joycode` |
| `--api_base` | 模型服务地址 | `http://11.137.96.250:30333/v1` |
| `--world_size` | 总机器数 | `4` |
| `--run_name` | 实验名称，用于输出目录 | `0714_joycode` |
| `--cc_run_dir` | cc-run 项目路径 | `/mnt/joyai/huangliang45/cc-run` |
| `--output_base` | 输出根目录（轨迹和评测结果） | `/mnt/joyai/huangliang45/deepswe-output` |

### 可选参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--node_rank` | hostname 尾缀 | 当前机器编号 (0 ~ world_size-1) |
| `--parquet_file` | COS 上的 `deep_swe_tasks.parquet` | rollout 用的 parquet，也可传本地路径或其它 URL |
| `--tasks_dir` | 自动从 `--tasks_url` 下载解压 | 评测阶段读取的 Harbor 任务目录，可直接指向本地已解压路径 |
| `--tasks_url` | COS 上的 `tasks.zip` | tasks 打包 zip 的 URL；`--tasks_dir` 未指定时自动下载解压到 `/tmp/deep-swe-tasks/` |
| `--prompt_file` | `${cc_run_dir}/benchmark/deepswe/prompts/deep_swe_user_prompt.md` | User Prompt 文件 |
| `--api_key` | 空；从环境变量读取 | API Key |
| `--max_workers` | `12` | 每节点并发数（DeepSWE 单题耗时较长，别开太高） |
| `--prefetch_workers` | `3` | 镜像预拉取并发数 |
| `--task_timeout` | `14400` | Agent 超时秒数（默认 4 小时，DeepSWE 部分任务较长） |
| `--mem_limit` | `32g` | 容器内存限制 |
| `--http_proxy` | `http://221.194.188.92:3128` | HTTP 代理 |
| `--no_proxy` | 预设内网地址 | 不走代理的地址 |
| `--first_init` | `false` | 是否先执行 /init |
| `--eval_workers` | `10` | 评测阶段并发数 |
| `--skip_rollout` | `false` | 跳过 rollout，只做评测 |
| `--skip_eval` | `false` | 跳过评测，只做 rollout |

所有参数都支持环境变量覆盖（大写同名），命令行参数优先级更高。

## 执行流程

```
阶段1: Rollout (每台机器并行)
  ├── 启动 Docker daemon（DinD）
  ├── 登录 Docker 仓库
  ├── 下载 parquet 数据（URL 自动下载到 /tmp）
  ├── 下载并解压 tasks（--tasks_dir 未指定时从 --tasks_url 拉到 /tmp/deep-swe-tasks/）
  ├── 生成 YAML 配置（/tmp/run_config_deepswe_xxx.yaml）
  └── 运行 cc-run 产出 patch → {output_base}/{run_name}/infer_logs/<instance_id>/patch.diff

阶段2: 评测 (仅 node_rank=0 执行)
  ├── 等待所有节点在 sync/ 下写入 node_<rank>.done
  ├── 遍历 tasks/，为每个任务构建 verifier 镜像 (deepswe-verifier-<id>)
  ├── 将 patch.diff 注入容器 /logs/artifacts/model.patch
  ├── 执行 /tests/test.sh，读取 /logs/verifier/reward.json
  └── 汇总结果到 {output_base}/{run_name}/eval_output/summary.json
```

## 输出目录结构

```
{output_base}/{run_name}/
├── infer_logs/
│   ├── <instance_id>/
│   │   ├── patch.diff              # Agent 产出的 patch
│   │   ├── litellm_requests.jsonl  # LLM 请求日志
│   │   ├── sdk_script.log          # SDK 运行日志
│   │   ├── proxy.log               # LiteLLM Proxy 日志
│   │   └── result.json             # 运行结果
│   └── ...
├── sync/
│   └── node_<rank>.done            # 多机同步标记
└── eval_output/
    ├── <instance_id>/
    │   └── eval_result.json        # 每题的 reward / stdout / stderr
    └── summary.json                # 全量汇总（total / solved / accuracy）
```

## Parquet 数据格式

评测用的 parquet 需要至少下列列（列名可通过 `INSTANCE_ID` 等环境变量在 `run_deepswe.sh` 中覆盖）：

| 列名 | 含义 |
|------|------|
| `instance_id` | 任务 ID（要与 `tasks/<id>/` 对应） |
| `image_name` | 任务运行镜像 |
| `problem_statement` | 任务描述，会替换到 prompt 的 `{{issue_description}}` |
| `installation_command` | 安装依赖的命令 |
| `base_commit` | 基线 commit |
| `pre_patch` | 预置 patch |
| `FAIL_TO_PASS`, `PASS_TO_PASS` | 测试筛选（DeepSWE 未使用可留空） |

## 与 SWE-Bench Pro 的差异

- **评分器不同**：DeepSWE 用每题自带的 Harbor verifier（`tests/Dockerfile`），本地构建镜像后跑 `/tests/test.sh`，读取 `reward.json`；SWE-Bench Pro 使用 `swe_bench_pro_eval_jd_opt_ver4.py` 拉取远端镜像评分。
- **依赖 tasks 目录**：评测阶段需要 Harbor 格式的 tasks/ 目录，默认会自动从 COS 下载 tasks.zip 解压到 `/tmp/deep-swe-tasks/`；SWE-Bench Pro 只需 parquet。
- **并发保守**：DeepSWE 单题超时默认 4 小时（`--task_timeout 14400`），默认 `--max_workers 12`。
