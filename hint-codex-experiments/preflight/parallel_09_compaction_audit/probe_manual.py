"""Use the existing isolated runtime to observe SDK compaction without a model."""
import importlib.util,json,time,tarfile,io
from pathlib import Path
import docker
import pyarrow.parquet as pq
ROOT=Path('/srv/lab-disks/disk2/users/xymo/hint-codex-experiments')
OUT=ROOT/'preflight/parallel_09_compaction_audit/attempt_02'
spec=importlib.util.spec_from_file_location('transport_helpers',ROOT/'preflight/parallel_09_transport_audit/probe.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
OUT.mkdir()
client=docker.DockerClient(base_url='unix://'+str(ROOT/'vm-lane5/docker.sock'),timeout=400)
row=next(r for r in pq.read_table(ROOT.parent/'hint-baseline-run/data/deep_swe_tasks.parquet').to_pylist() if r['instance_id']=='sqlfmt-create-table-ddl-formatting')
image=client.images.get(row['image_name'])
env={v.split('=',1)[0]:'offline-fixture' for v in image.attrs['Config'].get('Env',[]) if any(k in v.split('=',1)[0].upper() for k in ('KEY','TOKEN','SECRET','PASSWORD','ANTHROPIC','OPENAI','OFOX','HUBROUTER'))}
env.update(ANTHROPIC_BASE_URL='http://127.0.0.1:8767',ANTHROPIC_AUTH_TOKEN='offline-fixture',ANTHROPIC_MODEL='gpt-6.1-terra[1m]',ANTHROPIC_SMALL_FAST_MODEL='gpt-6.1-terra[1m]',CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',IS_SANDBOX='1',API_TIMEOUT_MS='60000',PYTHONDONTWRITEBYTECODE='1',SYSTEM_PROMPT_FILE='',HTTP_PROXY='',HTTPS_PROXY='',ALL_PROXY='',http_proxy='',https_proxy='',all_proxy='',NO_PROXY='*',BUN_JSC_useJIT='0')
container=client.containers.run(image.id,name='codex-parallel09-compaction-offline',entrypoint='',command=['tail','-f','/dev/null'],detach=True,mem_limit='128g',nano_cpus=8000000000,privileged=True,network_mode='none',environment=env,labels={'hint.experiment_name':'preflight_parallel_09_compaction'},volumes={'/opt/hint-codex-runtime/python':{'bind':'/opt/python3.12-tmp','mode':'ro'}})
record={'real_model_calls':0,'network':'none','container':container.id,'started_at_unix':time.time()}
try:
 code,output=container.exec_run(['bash','-c','rm -rf /app /root/.claude; mkdir -p /app']);assert code==0,output
 for source,target in [(ROOT/'source_parallel_09/run_cc_sdk.py','/tmp/sdk_script.py'),(ROOT/'source_parallel_09/logging_utils.py','/tmp/logging_utils.py'),(ROOT/'preflight/sdk_hook_fixture/probe.py','/tmp/hook_fixture.py'),(ROOT/'preflight/parallel_09_compaction_audit/guest_manual.py','/tmp/probe.py')]:h.put(container,target,source.read_bytes())
 code,output=container.exec_run(['timeout','--signal=INT','--kill-after=10','240','/opt/python3.12-tmp/bin/python3','/tmp/probe.py'],workdir='/app')
 (OUT/'stdout.log').write_bytes(output)
 chunks,_=container.get_archive('/tmp/transport_audit_out')
 with tarfile.open(fileobj=io.BytesIO(b''.join(chunks))) as archive:
  for item in archive.getmembers():
   if item.isfile():
    target=OUT/Path(item.name).relative_to('transport_audit_out');target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.extractfile(item).read())
 record['exit_code']=code
finally:
 container.remove(force=True);client.close();record.update(container_removed=True,finished_at_unix=time.time());(OUT/'host_result.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record),flush=True)
