import argparse
from collections import Counter
import sys

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'sdk'))
from codex_cli_bridge import CodexBridge, CodexBridgeError, create_app
import uvicorn


class BudgetBridge(CodexBridge):
    def __init__(self, directory, limit):
        super().__init__(directory)
        self.limit = limit
        self.calls = Counter()

    async def chat(self, body, headers=None, route=None):
        session = (route or {}).get('session', 'unlabelled')
        if self.calls[session] >= self.limit:
            raise CodexBridgeError('Uniform model-call budget reached', 'model_call_budget', 402)
        self.calls[session] += 1
        return await super().chat(body, headers, route)


parser = argparse.ArgumentParser()
parser.add_argument('--directory', required=True)
parser.add_argument('--port', type=int, required=True)
parser.add_argument('--limit', type=int, default=120)
args = parser.parse_args()
bridge = BudgetBridge(args.directory, args.limit)
app = create_app(bridge)


@app.on_event('shutdown')
async def shutdown():
    await bridge.close()


uvicorn.run(app, host='127.0.0.1', port=args.port, log_level='warning')
