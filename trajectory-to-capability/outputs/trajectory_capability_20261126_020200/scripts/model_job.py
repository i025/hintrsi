"""Text-only experiment calls through the existing Codex CLI bridge."""
import argparse
import json
import time
import urllib.request
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('name');p.add_argument('prompt');p.add_argument('output')
p.add_argument('--presentation_language',choices=['en','zh'],default='en')
a=p.parse_args()
out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
prompt=Path(a.prompt).read_text()
language='Write all natural-language output in English.' if a.presentation_language=='en' else 'Write this final user-facing presentation report in Simplified Chinese. This is presentation only and must not update the experiments.'
body={'model':'gpt-6.1-terra','messages':[{'role':'system','content':'You are a research analyst/report writer. '+language+' Follow the data access restrictions in the user prompt. Return your completed text in content with an empty tool_calls array.'},{'role':'user','content':prompt}],'tools':[]}
request=urllib.request.Request('http://127.0.0.1:8765/sessions/'+a.name+'/teacher/extract/v1/chat/completions',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
start=time.time()
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
try:
    with opener.open(request,timeout=1000) as r:response=json.load(r)
    content=response['choices'][0]['message']['content']
    out.write_text(content+'\n')
    record={'name':a.name,'completed':True,'started_at':start,'finished_at':time.time(),'characters':len(content),'words':len(content.split()),'response':response}
except Exception as e:
    record={'name':a.name,'completed':False,'started_at':start,'finished_at':time.time(),'error':str(e)}
out.with_suffix(out.suffix+'.job.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k!='response'}),flush=True)
raise SystemExit(0 if record['completed'] else 1)
