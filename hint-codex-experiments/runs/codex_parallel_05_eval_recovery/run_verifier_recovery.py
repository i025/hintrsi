from datetime import datetime,timezone
from pathlib import Path
import json,os,sys,time,traceback
import docker
N=Path("/srv/lab-disks/disk2/users/xymo/hint-codex-experiments")
W=Path("/srv/lab-disks/disk2/users/xymo/hint-baseline-run")
lane=int(sys.argv[1]);task=sys.argv[2];group=sys.argv[3]
directory=N/"runs/codex_parallel_05_eval_recovery"/f"lane{lane}"
original_run=N/"runs/codex_parallel_05/lanes"/f"codex_parallel_05_lane{lane}"/f"codex_parallel_05_lane{lane}_{group}_r1"
patch=original_run/"infer_logs"/task/"patch.diff"
original=patch.read_bytes();copy=directory/"original_patch.diff";copy.write_bytes(original)
sys.path.insert(0,str(N/"source_parallel/benchmark/deepswe"))
from eval_deep_swe import evaluate_task
parameters={"task_dir":W/"data/tasks"/task,"task_id":task,"patches_dir":original_run/"infer_logs","output_dir":directory/"eval_output","delete_image":True}
start=time.monotonic()
record={"lane":lane,"task":task,"group":group,"round":1,"origin_experiment":f"codex_parallel_05_lane{lane}","started_at_utc":datetime.now(timezone.utc).isoformat(),"source_patch":str(patch),"source_patch_bytes":len(original),"source_patch_copy":str(copy),"source_trajectory":str(original_run/"infer_logs"/task/"trajs.json"),"original_formal_result_existed":(original_run/"eval_output"/task/"eval_result.json").exists(),"parameters":{key:str(value) if isinstance(value,Path) else value for key,value in parameters.items()},"docker_host":os.environ["DOCKER_HOST"],"label":os.environ["HINT_EXPERIMENT_NAME"],"verifier_memory":"8g","network_mode":"none","guest_vcpus":8,"real_model_calls":0,"student_rerun":False,"prior_attempt_status":"student_completed_grading_interrupted","status":"running"}
meta=directory/"metadata.json";meta.write_text(json.dumps(record,indent=2)+"\n")
print(json.dumps({"event":"verifier_recovery_started","lane":lane,"task":task,"parameters":record["parameters"]}),flush=True)
try:
 record["result"]=evaluate_task(**parameters)
 record["status"]="completed"
except BaseException as error:
 record["status"]="incomplete";record["error"]=repr(error);traceback.print_exc()
finally:
 record["elapsed_seconds"]=time.monotonic()-start
 record["finished_at_utc"]=datetime.now(timezone.utc).isoformat()
 record["source_patch_bytes_unchanged"]=patch.read_bytes()==original
 record["source_patch_copy_exact_bytes"]=copy.read_bytes()==original
 client=docker.from_env(timeout=30)
 try:record["remaining_labelled_containers"]=[{"name":x.name,"status":x.status} for x in client.containers.list(all=True,filters={"label":"hint.experiment_name="+os.environ["HINT_EXPERIMENT_NAME"]})]
 finally:client.close()
 meta.write_text(json.dumps(record,indent=2)+"\n")
 print(json.dumps({"event":"verifier_recovery_finished","lane":lane,"status":record["status"],"elapsed_seconds":record["elapsed_seconds"],"source_patch_bytes_unchanged":record["source_patch_bytes_unchanged"],"remaining_labelled_containers":record["remaining_labelled_containers"]}),flush=True)
if record["status"]!="completed" or not record["source_patch_bytes_unchanged"] or record["remaining_labelled_containers"]:raise SystemExit(1)
