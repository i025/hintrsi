"""Check the real SDK no-knowledge request after the observed identity-line repair."""
import importlib.util
import json
import shutil
import sys
from pathlib import Path

SERVER=Path('/srv/lab-disks/disk2/users/xymo')
OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
ORIGINAL=SERVER/'hint-codex-experiments/preflight/exec_action_probe/transport/complete_sdk'
HERE=OUT/'evidence/empty_append_preflight';HERE.mkdir()
for name in ['fixture','problem.txt','guest.py']:
    p=ORIGINAL/name
    if p.is_dir():shutil.copytree(p,HERE/name)
    else:shutil.copy2(p,HERE/name)
spec=importlib.util.spec_from_file_location('fixture_driver',ORIGINAL/'driver.py')
driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
driver.HERE=HERE;driver.SOURCE=OUT/'source'
create=driver.create_container
driver.create_container=lambda client,image,name,experiment:create(client,image,'trajectory-capability-empty-append-preflight','trajectory_capability_preflight')
collect=driver.collect_output
def copy_output(container,source,destination):
    collect(container,source,destination)
    for name in ['system_prompt_actual.json','system_prompt_config.json']:
        code,data=container.exec_run(['cat','/tmp/'+name])
        if code==0:(destination/name).write_bytes(data)
driver.collect_output=copy_output
sys.argv=[sys.argv[0],'--session','capability-empty-append-preflight','--backend','http://172.17.0.1:8765']
raise SystemExit(driver.main())
