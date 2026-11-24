# 来源、下载方式与包内改动

## 版本

- 仓库：`git@coding.jd.com:coding-ai/cc-run.git`
- 分支：`hint`
- 提交：`3606f71e067f121354709864c51123d543f5c515`
- 提交时间：2026-11-03 17:34:07 +08:00
- 打包日期：2026-11-05
- [网页端源码](http://xingyun.jd.com/codingRoot/coding-ai/cc-run/tree/hint/benchmark/deepswe)

`source/` 是上述提交的实验依赖子集，保留相对目录结构。本机下载得到的 checkout 保持原样；为交接所做的修改仅在包内副本。逐文件原始/包内 SHA256 和改动原因见 [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json)。

文档使用此前已经整理好的 [Hint实验 Markdown](docs/Hint实验.md)，保留章节、列表、六个完整代码/Prompt 块、配图与两个 Hint 示例附件。未打包网页 HTML。链接改为包内路径；流程图用独立 SVG 保留。历史报告截图和示例文件用于理解实验，不代替完整运行记录。

## 这次怎样下载代码

这次通过终端的 Git SSH 克隆下载，使用本机已有的 SSH 配置与仓库访问权限；不是把网页代码逐文件复制下来。实际用的命令为：

```bash
git -c core.sshCommand='ssh -o BatchMode=yes -o ConnectTimeout=10' \
  clone --depth 1 --branch hint \
  git@coding.jd.com:coding-ai/cc-run.git work/cc-run
```

`--branch hint` 指定实验分支；`--depth 1` 只取这个分支的最新提交，减少下载量。`BatchMode=yes` 禁止交互询问，用现有密钥；`ConnectTimeout=10` 避免连接长时间等待。

其他开发者可以这样操作：

1. 确认自己的 Coding 账号有仓库权限，电脑已安装 Git。
2. 在仓库页面找到 SSH 克隆地址，确认是上述仓库。
3. 如果还没有 SSH 密钥，用 `ssh-keygen -t ed25519` 创建；将生成的 **`.pub` 公钥**添加到 Coding 账号的 SSH 公钥设置中。私钥保存在自己电脑，不需要交给他人。
4. 在希望存放代码的目录执行克隆命令，随后 `cd cc-run`、`git rev-parse HEAD` 核对版本。

日常下载最新 Hint 分支：

```bash
git clone --depth 1 --branch hint git@coding.jd.com:coding-ai/cc-run.git
cd cc-run
git rev-parse HEAD
```

若要拿到本包的确切版本，使用含历史记录的克隆，再切换到固定提交：

```bash
git clone --branch hint git@coding.jd.com:coding-ai/cc-run.git cc-run-pinned
cd cc-run-pinned
git checkout 3606f71e067f121354709864c51123d543f5c515
```

有网页浏览权限不一定意味着本机 SSH 已配置好。出现 `Permission denied (publickey)` 时，检查公钥绑定、SSH 使用的密钥和账号仓库权限。只有读代码和运行这个子集时，可以直接使用本交接包；下载完整仓库主要用于继续开发、查看历史和提交变更。

## 为交接做的调整

| 文件 | 调整 |
|---|---|
| [benchmark/deepswe/README.md](source/benchmark/deepswe/README.md) | 补充当前 Hint 包入口，并移除历史凭据示例 |
| [benchmark/deepswe/compress_hint.py](source/benchmark/deepswe/compress_hint.py) | 硬编码模型凭据改为环境变量或占位符；个人数据/输出默认路径改为相对 source 根目录 |
| [benchmark/deepswe/gen_comparison_report.py](source/benchmark/deepswe/gen_comparison_report.py) | 硬编码模型凭据改为环境变量或占位符 |
| [benchmark/deepswe/gen_review_hint.py](source/benchmark/deepswe/gen_review_hint.py) | 硬编码模型凭据改为环境变量或占位符；个人数据/输出默认路径改为相对 source 根目录 |
| [benchmark/deepswe/get_hint_by_task.py](source/benchmark/deepswe/get_hint_by_task.py) | 硬编码模型凭据改为环境变量或占位符 |
| [benchmark/deepswe/review_hint_traj.py](source/benchmark/deepswe/review_hint_traj.py) | 硬编码模型凭据改为环境变量或占位符 |
| [benchmark/deepswe/run_deepswe.sh](source/benchmark/deepswe/run_deepswe.sh) | 移除个人镜像仓库登录凭据，使用运行者已有 Docker 登录状态；取消清理其他任务已退出容器的全局操作；个人 Python 绝对路径改为 PYTHON_BIN 或 python3；不再默认使用原作者网络代理；由运行者配置；临时配置默认仅当前用户可读 |
| [benchmark/deepswe/run_loop_by_hint.py](source/benchmark/deepswe/run_loop_by_hint.py) | 硬编码模型凭据改为环境变量或占位符；默认 Python 改为当前解释器；步骤命令打印与日志隐藏 --api_key 值，执行参数保持原值 |
| [benchmark/deepswe/run_loop_by_hint.sh](source/benchmark/deepswe/run_loop_by_hint.sh) | 硬编码模型凭据改为环境变量或占位符；移除个人镜像仓库登录凭据，使用运行者已有 Docker 登录状态；个人 Python 绝对路径改为 PYTHON_BIN 或 python3；临时配置默认仅当前用户可读 |
| [benchmark/deepswe/run_one.sh](source/benchmark/deepswe/run_one.sh) | 硬编码模型凭据改为环境变量或占位符 |
| [benchmark/deepswe/run_one_hint.sh](source/benchmark/deepswe/run_one_hint.sh) | 硬编码模型凭据改为环境变量或占位符；移除个人镜像仓库登录凭据，使用运行者已有 Docker 登录状态；个人 Python 绝对路径改为 PYTHON_BIN 或 python3；不再默认使用原作者网络代理；由运行者配置；临时配置默认仅当前用户可读；可选文件参数改为 Bash 数组，保留含空格路径 |
| [benchmark/deepswe/run_one_loop.sh](source/benchmark/deepswe/run_one_loop.sh) | 硬编码模型凭据改为环境变量或占位符；移除个人镜像仓库登录凭据，使用运行者已有 Docker 登录状态；个人 Python 绝对路径改为 PYTHON_BIN 或 python3；不再默认使用原作者网络代理；由运行者配置；临时配置默认仅当前用户可读；可选 Hint 文件参数改为 Bash 数组，保留含空格路径 |
| [benchmark/deepswe/run_review_hint_traj.sh](source/benchmark/deepswe/run_review_hint_traj.sh) | 硬编码模型凭据改为环境变量或占位符；个人 Python 绝对路径改为 PYTHON_BIN 或 python3；临时配置默认仅当前用户可读 |
| [benchmark/deepswe/update_trajs.sh](source/benchmark/deepswe/update_trajs.sh) | 硬编码模型凭据改为环境变量或占位符；个人 Python 绝对路径改为 PYTHON_BIN 或 python3；临时配置默认仅当前用户可读 |
| [run_multi_turn_loop.py](source/run_multi_turn_loop.py) | 硬编码模型凭据改为环境变量或占位符 |
| [update_trajs.py](source/update_trajs.py) | 硬编码模型凭据改为环境变量或占位符 |
| [utils.py](source/utils.py) | 硬编码模型凭据改为环境变量或占位符 |

新增的 README、开发者指南、结果转录、配置模板、宿主依赖清单和 `scripts/` 都是交接辅助内容。运行入口负责路径解析、参数检查和环境传递，真正的实验仍由原链路执行。没有改提示算法、Golden Diff 选择规则、最多轮次的含义和测试评分规则。

## 包外的东西

`.git` 历史、非 DeepSWE benchmark 数据、RL 代码、外部任务镜像、Parquet、tasks 包、历史完整 rollout/eval 日志以及个人配置未装入交接包。源码和文档沿用项目原有访问权限与许可范围，本包没有新增开源许可证。
