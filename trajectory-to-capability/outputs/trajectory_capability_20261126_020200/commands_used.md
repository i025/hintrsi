# 实际命令与复查入口

下面记录本次实际使用的服务与主队列命令。重跑会消耗模型与计算资源；现有同名状态不可覆盖。原目录未改写，结果目录源码是增量副本。所有命令的工作目录为：

/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi

```bash
/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -u -B /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/source/codex_cli_bridge.py --run_dir /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/logs/bridge --port 8765
/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -u -B /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/source/teacher_progress.py --run_dir /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/logs/progress --port 8766
/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -u -B /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/source/run_hint_exploration.py service
/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -u -B /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/source/run_capability_experiments.py --stage selection --task superjson-error-stack-serialization --run_tag capability_v1
/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -u -B /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/source/run_capability_experiments.py --stage test --task tomlkit-toml-table-converters --run_tag capability_v1
/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -u -B /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/source/run_capability_experiments.py --stage test --task httpx-deterministic-cookie-store --run_tag capability_v1
/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -u -B /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/source/run_capability_experiments.py --stage selection --task superjson-error-stack-serialization --run_tag capability_v1_matched_prompt
```

原Bridge实际构造的Codex CLI基础命令如下；每次另加独立的输出schema、输出文件及输入，逐请求文件位于 `logs/bridge/`。其工具是原SDK序列化工具；CLI原生工具关闭，不能把它描述为原生API角色/采样配置完全等价。

```bash
codex exec --ephemeral --json --skip-git-repo-check --ignore-user-config --ignore-rules --sandbox read-only --model gpt-6.1-terra -c 'model_reasoning_effort="low"' -c features.shell_tool=false -c features.view_image=false -c features.multi_agent=false -c features.plugins=false -c features.apps=false -c features.skill_search=false -c features.skill_mcp_dependency_install=false -c features.remote_plugin=false -c features.code_mode=false -c features.code_mode_only=false -c features.computer_use=false -c features.browser_use=false -c features.in_app_browser=false -c features.image_generation=false -c features.goals=false -c features.sleep_tool=false -c features.workspace_dependencies=false -c features.tool_suggest=false -c features.hooks=false -c 'web_search="disabled"' -c project_doc_max_bytes=0 -c 'mcp_servers={}' -c skills.bundled.enabled=false -c tools.update_plan.enabled=false -c tools.experimental_request_user_input.enabled=false -c include_permissions_instructions=false -c include_environment_context=false -c include_collaboration_mode_instructions=false -c include_apps_instructions=false -c 'model_catalog_json="/srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/source/codex_model_catalog.json"'
```

分析与统计实际通过以下脚本运行；`scripts/` 是对应 `work/` 源码副本。原始模型调用日志而非SDK美元估算是Token统计依据。

```bash
/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -B /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/work/collect_attempt_metrics.py
/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -B /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/work/historical_metrics.py
/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -B /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/work/enrich_historical_inventory.py
/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -B /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/work/validate_model_conditions.py
```

模型提取、逐案审计、汇总审计及最终中文报告均由 `work/model_job.py` 向原Bridge发送请求，实际完整提示保存在 `config/*_prompt.txt`，响应及耗时在各产物的 `.job.json`。K1/K2字段投影修复前后的两轮提取均计费并保留，没有用Test成绩改写知识。图像审计通过同一CLI原生图像输入，账本独立保存在 `logs/visual_SV*/`。

容器与评价的具体命令保存在每轮原项目 `runs/*/logs/`、SDK日志与monitor日志中。主实验每次1800秒学生预算、8CPU、128GiB；两道Test使用各自空闲VM，组内顺序执行。现有VM、运行时和任务数据的路径保存在配置中，不复制GB级镜像或认证信息。

接入夹具不属于独立终测。修复前旧B0、模型前中止K0与完整统一重跑均保留，见 `extra_attempt_metrics.csv` 和 `logs/engineering_fixes.json`。可选Hint是否执行，以 `config/optional_hint_plan.json` 与真实结果文件为准，不把准备脚本当作已经运行。

随后实际请求对比发现SDK默认preset与非空append的身份句不同。`run_cc_sdk.py`仅增加公共空reminder路径，使B0与知识组使用相同身份句；非空知识路径代码不变。旧capability_v1 Selection四组完整保留并单列，新的统一复核标签是capability_v1_matched_prompt。最早Test K1/K2使用未改动的非空路径继续保留，后续B0使用修复路径；实际组间请求核验见 `results/model_condition_validation.json`。所有知识文本和原冻结记录保持不变，后续复核/Test结果不更新知识。

可选Hint实际入口：

```bash
/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -u -B /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/source/run_hint_exploration.py run
```

首个可选评价已启动后，实际通过以下命令执行同一名义600秒上限；后续可选运行由原shell入口设置HINT_VERIFIER_TIMEOUT_SEC=600，评价命令外包timeout --kill-after=10 600。核心已完成评价未改动，首次手动计时与后续包装差别见日志。

```bash
/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python -u -B /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/work/bound_first_hint_evaluation.py
```

历史Scene只读几何核对实际命令（无新渲染/重建/学习，不保存原文件）：

```bash
/usr/bin/time -v -o /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/evidence/scene_geometry/technical_repair_build.time.txt nice -n 10 /srv/lab-disks/disk2/users/xymo/projects/BlenderWorld/runtime/blender-4.2.10-linux-x64/blender --background -noaudio --factory-startup --disable-autoexec --threads 1 /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/stagewise_teaching_student_selfcheck_pilot/tasks/D01/stages/04/technical_repair_build/scene.blend --python-exit-code 1 --python /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/evidence/scene_geometry/probe.py -- /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/evidence/scene_geometry/technical_repair_build.json
/usr/bin/time -v -o /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/evidence/scene_geometry/visual_revision_build.time.txt nice -n 10 /srv/lab-disks/disk2/users/xymo/projects/BlenderWorld/runtime/blender-4.2.10-linux-x64/blender --background -noaudio --factory-startup --disable-autoexec --threads 1 /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs/stagewise_teaching_student_selfcheck_pilot/tasks/D01/stages/04/visual_revision_build/scene.blend --python-exit-code 1 --python /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/evidence/scene_geometry/probe.py -- /srv/lab-disks/disk2/users/xymo/Documents/Codex/2026-11-26/trajectory-to-capability-rsi-hint-rsi/outputs/trajectory_capability_20261126_020200/evidence/scene_geometry/visual_revision_build.json
```
