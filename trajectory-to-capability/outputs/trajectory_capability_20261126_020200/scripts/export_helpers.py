"""Save only experiment scripts and commands; never copy CLI credentials/cache."""
import json
import shlex
import shutil
import sys
from pathlib import Path

WORK=Path.cwd();OUT=WORK/'outputs/trajectory_capability_20261126_020200'
PYTHON='/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'
scripts=OUT/'scripts';scripts.mkdir(exist_ok=True)
names=['prepare_inventory.py','historical_metrics.py','enrich_historical_inventory.py','prepare_audits.py',
    'run_audits.py','scene_inventory.py','prepare_scene_audits.py','run_scene_audits.py',
    'visual_scene_audits.py','prepare_scene_geometry_audit.py','write_audit_reports.py','prepare_extraction.py','model_job.py',
    'pull_new_images.py','start_services.py','run_injection_preflight.py','run_empty_append_preflight.py','monitor_experiment.py',
    'collect_attempt_metrics.py','index_current_trajectories.py','cost_breakdown.py','resource_summary.py','analyze_completed_attempts.py','prepare_pooled_analysis.py',
    'freeze_knowledge.py','validate_model_conditions.py','diagnose_selection_evaluation.py','prepare_baseline_addendum.py','update_audit_coverage.py',
    'prepare_final_report.py','finalize_report.py','start_optional_hint.py','collect_hint_metrics.py','analyze_hint_attempts.py','prepare_hint_summary.py','bound_first_hint_evaluation.py','audit_historical_comparisons.py','integrate_historical_addendum.py','finish_experiment.py','export_helpers.py']
for name in names:shutil.copy2(WORK/'work'/name,scripts/name)
sys.path.insert(0,str(OUT/'source'))
from codex_cli_bridge import default_command

commands=[]
for path in [OUT/'logs/services_before_optional.json',OUT/'config/services.json']:
    if path.exists():
        for item in json.loads(path.read_text()):
            command=shlex.join(item['command'])
            if command not in commands:commands.append(command)
commands += [shlex.join([PYTHON,'-u','-B',str(OUT/'source/run_capability_experiments.py'),
    '--stage',stage,'--task',task,'--run_tag','capability_v1'])
    for stage,task in [('selection','superjson-error-stack-serialization'),('test','tomlkit-toml-table-converters'),('test','httpx-deterministic-cookie-store')]]
if (OUT/'runs/capability_v1_matched_prompt_selection_superjson-error-stack-serialization_state.json').exists():
    commands.append(shlex.join([PYTHON,'-u','-B',str(OUT/'source/run_capability_experiments.py'),
        '--stage','selection','--task','superjson-error-stack-serialization','--run_tag','capability_v1_matched_prompt']))
text='''# 实际命令与复查入口

下面记录本次实际使用的服务与主队列命令。重跑会消耗模型与计算资源；现有同名状态不可覆盖。原目录未改写，结果目录源码是增量副本。所有命令的工作目录为：

'''+str(WORK)+'\n\n```bash\n'+'\n'.join(commands)+'\n```\n\n'
text+='原Bridge实际构造的Codex CLI基础命令如下；每次另加独立的输出schema、输出文件及输入，逐请求文件位于 `logs/bridge/`。其工具是原SDK序列化工具；CLI原生工具关闭，不能把它描述为原生API角色/采样配置完全等价。\n\n```bash\n'+shlex.join(default_command())+'\n```\n\n'
text+='分析与统计实际通过以下脚本运行；`scripts/` 是对应 `work/` 源码副本。原始模型调用日志而非SDK美元估算是Token统计依据。\n\n```bash\n'
text+='\n'.join(shlex.join([PYTHON,'-B',str(WORK/'work'/name)]) for name in ['collect_attempt_metrics.py','historical_metrics.py','enrich_historical_inventory.py','validate_model_conditions.py'])+'\n```\n\n'
text+='''模型提取、逐案审计、汇总审计及最终中文报告均由 `work/model_job.py` 向原Bridge发送请求，实际完整提示保存在 `config/*_prompt.txt`，响应及耗时在各产物的 `.job.json`。K1/K2字段投影修复前后的两轮提取均计费并保留，没有用Test成绩改写知识。图像审计通过同一CLI原生图像输入，账本独立保存在 `logs/visual_SV*/`。

容器与评价的具体命令保存在每轮原项目 `runs/*/logs/`、SDK日志与monitor日志中。主实验每次1800秒学生预算、8CPU、128GiB；两道Test使用各自空闲VM，组内顺序执行。现有VM、运行时和任务数据的路径保存在配置中，不复制GB级镜像或认证信息。

接入夹具不属于独立终测。修复前旧B0、模型前中止K0与完整统一重跑均保留，见 `extra_attempt_metrics.csv` 和 `logs/engineering_fixes.json`。可选Hint是否执行，以 `config/optional_hint_plan.json` 与真实结果文件为准，不把准备脚本当作已经运行。

随后实际请求对比发现SDK默认preset与非空append的身份句不同。`run_cc_sdk.py`仅增加公共空reminder路径，使B0与知识组使用相同身份句；非空知识路径代码不变。旧capability_v1 Selection四组完整保留并单列，新的统一复核标签是capability_v1_matched_prompt。最早Test K1/K2使用未改动的非空路径继续保留，后续B0使用修复路径；实际组间请求核验见 `results/model_condition_validation.json`。所有知识文本和原冻结记录保持不变，后续复核/Test结果不更新知识。
'''
if (OUT/'runs/hint_exploration_state.json').exists():
    text+='\n可选Hint实际入口：\n\n```bash\n'+shlex.join([PYTHON,'-u','-B',str(OUT/'source/run_hint_exploration.py'),'run'])+'\n```\n'
if (OUT/'logs/optional_evaluation_timeout_NoHint.json').exists():
    text+='\n首个可选评价已启动后，实际通过以下命令执行同一名义600秒上限；后续可选运行由原shell入口设置HINT_VERIFIER_TIMEOUT_SEC=600，评价命令外包timeout --kill-after=10 600。核心已完成评价未改动，首次手动计时与后续包装差别见日志。\n\n```bash\n'+shlex.join([PYTHON,'-u','-B',str(WORK/'work/bound_first_hint_evaluation.py')])+'\n```\n'
geometry=OUT/'evidence/scene_geometry/execution_records.json'
if geometry.exists():
    text+='\n历史Scene只读几何核对实际命令（无新渲染/重建/学习，不保存原文件）：\n\n```bash\n'
    text+='\n'.join(shlex.join(r['command']) for r in json.loads(geometry.read_text()))+'\n```\n'
(OUT/'commands_used.md').write_text(text)
print(json.dumps({'exported_scripts':len(names),'command_record':str(OUT/'commands_used.md')}))
