import json,sys,os
from pathlib import Path
p=json.loads(sys.stdin.read());Path("stdin.json").write_text(json.dumps(p));text=json.dumps(p["messages"])
calls=[{"name":"Monitor","arguments":"{\"command\":\"echo offline\"}"}] if "REQUEST_MONITOR" in text else []
Path(sys.argv[sys.argv.index("--output-last-message")+1]).write_text(json.dumps({"content":"OFFLINE_DYNAMIC_COMPLETE","tool_calls":calls}))
print(json.dumps({"type":"thread.started","thread_id":"offline-"+str(os.getpid())}))
print(json.dumps({"type":"turn.completed","usage":{"input_tokens":100,"output_tokens":20}}))
