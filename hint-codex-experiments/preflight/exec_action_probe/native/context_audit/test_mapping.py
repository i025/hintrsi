"""Check exact context-error mapping without a model or API key."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
import httpx

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
sys.path.insert(0,str(ROOT/'source_parallel_09_checked'))
spec=importlib.util.spec_from_file_location('context_candidate',OUT/'candidate/codex_exec_bridge.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
FIXTURE='''import json,sys
sys.stdin.read()
print(json.dumps({"type":"thread.started","thread_id":"fixture"}),flush=True)
print(json.dumps(json.loads(sys.argv[1])),flush=True)
raise SystemExit(1)
'''

def provider_event(code,message='Original provider context detail.'):
    return {'type':'turn.failed','error':{'message':json.dumps({'error':{'code':code,'message':message,'type':'invalid_request_error'}})}}

class MappingTests(unittest.IsolatedAsyncioTestCase):
    async def mapped(self,event):
        with tempfile.TemporaryDirectory(dir=OUT) as directory:
            path=Path(directory); program=path/'event.py';program.write_text(FIXTURE)
            bridge=module.CodexExecBridge(path/'runtime',[sys.executable,str(program),json.dumps(event)])
            try:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=module.create_app(bridge)),base_url='http://fixture') as client:
                    response=await client.post('/v1/chat/completions',json={'model':'fixture','messages':[{'role':'user','content':'fixture'}],'tools':[]})
                self.assertEqual(len(bridge.processes),0)
                return response
            finally:
                await bridge.close()

    async def test_length_code_preserved_and_400(self):
        response=await self.mapped(provider_event('context_length_exceeded'))
        self.assertEqual(response.status_code,400)
        self.assertEqual(response.json()['error']['code'],'context_length_exceeded')
        self.assertIn('prompt is too long:',response.text)
        self.assertIn('Original provider context detail.',response.text)

    async def test_window_code_400(self):
        self.assertEqual((await self.mapped(provider_event('context_window_exceeded'))).status_code,400)

    async def test_explicit_codex_info_400(self):
        event={'type':'turn.failed','error':{'message':'Explicit context failure','codexErrorInfo':'contextWindowExceeded'}}
        self.assertEqual((await self.mapped(event)).status_code,400)

    async def test_generic_too_long_keeps_503(self):
        event={'type':'turn.failed','error':{'message':'The tool filename is too long'}}
        self.assertEqual((await self.mapped(event)).status_code,503)

    async def test_other_structured_error_keeps_503(self):
        self.assertEqual((await self.mapped(provider_event('server_error','prompt is too long'))).status_code,503)

    async def test_malformed_json_keeps_503(self):
        event={'type':'turn.failed','error':{'message':'{not JSON context_length_exceeded'}}
        self.assertEqual((await self.mapped(event)).status_code,503)

if __name__=='__main__':unittest.main()
