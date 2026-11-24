"""Run the independent full-chain preflight with a finite model-request allowance."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from codex_exec_bridge import CodexBridgeError, CodexExecBridge, create_app


class PreflightBridge(CodexExecBridge):
    def __init__(self, run_dir, max_requests):
        super().__init__(run_dir)
        self.max_requests = max_requests
        self.requests_started = 0

    async def chat(self, body, headers=None, route=None):
        if self.stopped:
            raise CodexBridgeError(self.stop_reason, "experiment_stopped")
        if self.requests_started >= self.max_requests:
            self.stop("The independent preflight reached its model-request allowance")
            raise CodexBridgeError(self.stop_reason, "preflight_limit")
        self.requests_started += 1
        return await super().chat(body, headers, route)

    def status(self):
        value = super().status()
        value["preflight"] = {"max_requests": self.max_requests,
                              "requests_started": self.requests_started}
        return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--max_requests", type=int, default=20)
    args = parser.parse_args()
    import uvicorn
    bridge = PreflightBridge(args.run_dir, args.max_requests)
    app = create_app(bridge)

    @app.on_event("shutdown")
    async def shutdown():
        await bridge.close()

    uvicorn.run(app, host="127.0.0.1", port=8765)


if __name__ == "__main__":
    main()
