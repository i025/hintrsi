"""Reuse the verified complete SDK fixture and record an independent capability append."""
import importlib.util
import json
import shutil
import sys
from pathlib import Path

ROOT=Path('/srv/lab-disks/disk2/users/xymo/hint-codex-experiments')
OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
ORIGINAL=ROOT/'preflight/exec_action_probe/transport/complete_sdk'
HERE=OUT/'evidence/injection_preflight'
HERE.mkdir()
for name in ('fixture','problem.txt','guest.py'):
    p=ORIGINAL/name
    if p.is_dir():shutil.copytree(p,HERE/name)
    else:shutil.copy2(p,HERE/name)
capability='''<persistent_capabilities>
Capability preflight marker: CROSS_TASK_CAPABILITY_PREFLIGHT_V1.
Use observed repository behavior and focused executable checks to validate a change.
This is general process knowledge; it supplies no task solution.
</persistent_capabilities>
'''
(HERE/'capability.md').write_text(capability)
p=HERE/'guest.py';s=p.read_text();s=s.replace('import os\n','import os\nos.environ["APPEND_SYSTEM_PROMPT_FILE"] = "/tmp/capability.md"\n',1);p.write_text(s)
spec=importlib.util.spec_from_file_location('fixture_driver',ORIGINAL/'driver.py')
driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
driver.HERE=HERE;driver.SOURCE=OUT/'source'
original_create=driver.create_container
def create(client,image,name,experiment):
    return original_create(client,image,'trajectory-capability-injection-preflight','trajectory_capability_preflight')
driver.create_container=create
original_install=driver.install_sdk_files
def install(container):
    original_install(container);driver.put(container,'/tmp/capability.md',capability)
driver.install_sdk_files=install
original_collect=driver.collect_output
def collect(container,source,destination):
    original_collect(container,source,destination)
    for name in ('system_prompt_actual.json','system_prompt_config.json'):
        code,data=container.exec_run(['cat','/tmp/'+name])
        if code==0:(destination/name).write_bytes(data)
    p=destination/'system_prompt_actual.json'
    actual=json.loads(p.read_text()) if p.exists() else {}
    proof={'requested':True,'actual_prompt_captured':p.exists(),'content_present':capability.strip() in actual.get('system_prompt',''),'source':str(HERE/'capability.md')}
    (destination/'capability_injection.json').write_text(json.dumps(proof,indent=2)+'\n')
driver.collect_output=collect
sys.argv=[sys.argv[0],'--session','capability-injection-preflight','--backend','http://172.17.0.1:8765']
raise SystemExit(driver.main())
