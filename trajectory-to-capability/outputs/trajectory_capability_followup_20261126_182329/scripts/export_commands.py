"""Export recorded commands and source differences without copying credentials."""
import difflib
import json
import shlex
import sys
from pathlib import Path

WORK=Path.cwd()
OUT=Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
OLD=OUT.parent/'trajectory_capability_20261126_020200'
recorded_path=OUT/'results/recorded_commands.json'
commands=json.loads(recorded_path.read_text()) if recorded_path.exists() else []
def add(label,command,source):
    if not command:return
    values=list(command)
    for i,value in enumerate(values):
        if value in ('--api_key','--api-key') and i+1<len(values):values[i+1]='<REDACTED>'
    entry={'label':label,'command':values,'source':source}
    if entry not in commands:commands.append(entry)
for path in [OUT/'config/services.json',OUT/'config/recovered_processes_20261126_2226.json']:
    for row in json.loads(path.read_text()):add(row['name'],row.get('command'),str(path))
runtime=OUT/'config/runtime_resume.json'
for row in json.loads(runtime.read_text())['lanes']:
    add('lane'+str(row['lane'])+' VM',['nice','-n','10']+row['vm_command'],str(runtime))
    add('lane'+str(row['lane'])+' tunnel',row['tunnel_command'],str(runtime))
recovery=OUT/'runs/capability_followup_selection_same_patch_01_state.json'
selection=OUT/'runs/capability_followup_v2_selection_mashumaro-flattened-dataclass-fields_state.json'
if recovery.exists() and selection.exists() and json.loads(selection.read_text()).get('resumptions'):
    add('Selection resume invoked by executed recovery helper',
        ['/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python','-u','-B',str(OUT/'source/run_capability_experiments.py'),
         '--stage','selection','--task','mashumaro-flattened-dataclass-fields','--run_tag','capability_followup_v2','--resume'],
        str(WORK/'work_followup/recover_selection_evaluation.py'))
final_state=OUT/'config/final_stages_process.json'
if final_state.exists():
    for row in json.loads(final_state.read_text()).get('test_processes',[]):add('Test '+row['task'],row['command'],str(final_state))
deadline=OUT/'runs/capability_followup_v2_test_adaptix-name-mapping-aliases_B0_r1/budget_stop_evaluation.json'
if deadline.exists():
    add('First evaluation of saved Adaptix B0 deadline patch',
        ['/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python','-u','-B','work_followup/recover_student_timeout.py'],str(deadline))
    queue=json.loads((OUT/'runs/capability_followup_v2_test_adaptix-name-mapping-aliases_state.json').read_text())
    if queue.get('resumptions'):
        add('Adaptix remaining queue after deadline evaluation',
            ['/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python','-u','-B',str(OUT/'source/run_capability_experiments.py'),
             '--stage','test','--task','adaptix-name-mapping-aliases','--run_tag','capability_followup_v2','--resume'],str(deadline))
if final_state.exists() and json.loads(final_state.read_text()).get('resumptions'):
    add('Resumed monitoring controller',
        ['/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python','-u','-B','work_followup/resume_final_stages.py'],str(final_state))
deadline=OUT/'runs/capability_followup_hint_transfer_hint_transfer_python-statemachine-state-data-scoping_HT_Strategy_r1/budget_stop_evaluation.json'
if deadline.exists():
    add('First evaluation of saved HT_Strategy deadline patch',
        ['/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python','-u','-B','work_followup/recover_student_timeout.py',
         '--task','python-statemachine-state-data-scoping','--group','HT_Strategy'],str(deadline))
    queue=json.loads((OUT/'runs/capability_followup_v2_test_python-statemachine-state-data-scoping_state.json').read_text())
    if queue.get('resumptions'):
        add('State final queue after deadline evaluation',
            ['/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python','-u','-B',str(OUT/'source/run_capability_experiments.py'),
             '--stage','test','--task','python-statemachine-state-data-scoping','--run_tag','capability_followup_v2',
             '--resume','--interleave_hint_transfer'],str(deadline))
for path in (OUT/'runs').glob('*_state.json'):
    data=json.loads(path.read_text());pid=data.get('pid')
    proc=Path(f'/proc/{pid}/cmdline')
    if not pid or not proc.exists():continue
    raw=proc.read_bytes()
    try:cwd=Path(f'/proc/{pid}/cwd').resolve()
    except OSError:continue
    if str(OUT).encode() in raw or (b'work_followup/' in raw and cwd==WORK):
        add('Observed queue '+path.stem,[x.decode() for x in raw.split(b'\x00') if x],str(path))
sys.path.insert(0,str(OUT/'source'))
from codex_cli_bridge import default_command
add('CLI base constructed by unchanged Bridge',default_command(),str(OUT/'source/codex_cli_bridge.py'))
(OUT/'results/recorded_commands.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2)+'\n')
text='# 实际命令与源码差异\n\n工作目录：'+str(WORK)+'\n\n以下服务、VM和队列命令来自本次保存的启动记录或同目录实际进程；路径展开不改变参数。CLI基础命令由未改动的原Bridge构造，每条请求另外指定自身schema、输出文件和stdin。认证值不导出。学生实际底层求解命令另见后文原日志。\n\n'
for row in commands:
    text+='## '+row['label']+'\n\n记录来源：['+row['source']+']('+row['source']+')\n\n```bash\n'+shlex.join(row['command'])+'\n```\n\n'
text+='## 已执行的底层求解命令\n\n以下逐行取自原编排器STEP日志中的CMD字段，包含各实际启动组；未启动组没有伪造命令。\n\n'
for path in sorted((OUT/'runs').glob('*/logs/*/step_*_solve_*.log')):
    lines=[line for line in path.read_text(errors='replace').splitlines() if line.startswith('CMD: ')]
    if lines:text+='['+str(path.relative_to(OUT))+']('+str(path)+')\n\n```bash\n'+'\n'.join(line[5:] for line in lines)+'\n```\n\n'
text+='研究辅助脚本实际版本见 scripts/；原CLI请求、返回、事件和用量见 logs/bridge/ 与各原生图像调用目录。新组正式评测timeout=3600的真实进程证据见 evidence/engineering_access_recovery/K2_v2_live_verifier_budget.json。学生1800秒/8CPU/128g，原评分器8g，VM8vCPU/144GiB且nice10；未使用共享服务器GPU。未覆盖原实验或复制认证文件。\n'
(OUT/'commands_used.md').write_text(text)
changes=[];patch=[]
for p in sorted((OUT/'source').rglob('*')):
    if not p.is_file() or '__pycache__' in p.parts:continue
    relative=p.relative_to(OUT/'source');previous=OLD/'source'/relative
    if not previous.exists():changes.append({'file':str(relative),'kind':'added'});continue
    if p.read_bytes()==previous.read_bytes():continue
    changes.append({'file':str(relative),'kind':'modified'})
    try:patch.extend(difflib.unified_diff(previous.read_text().splitlines(keepends=True),p.read_text().splitlines(keepends=True),fromfile='six_hour/source/'+str(relative),tofile='followup/source/'+str(relative)))
    except UnicodeDecodeError:continue
(OUT/'results/source_changes_vs_closed_six_hour.json').write_text(json.dumps(changes,indent=2)+'\n')
(OUT/'results/source_changes_vs_closed_six_hour.diff').write_text(''.join(patch))
print(json.dumps({'recorded_commands':len(commands),'source_changes':changes}))
