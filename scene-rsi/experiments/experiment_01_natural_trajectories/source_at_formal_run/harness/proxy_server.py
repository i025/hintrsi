"""Run the existing LiteLLM translation with raw, credential-free wire records."""
import json
import os
from pathlib import Path
import time
import uuid

from litellm.proxy.proxy_server import app
import uvicorn

LOG = Path(os.environ['SCENE_PROXY_LOG_DIR'])


@app.middleware('http')
async def record(request, call_next):
    if request.method != 'POST' or '/messages' not in request.url.path:
        return await call_next(request)
    request_id = uuid.uuid4().hex
    body = await request.body()
    (LOG / (request_id + '.request.json')).write_bytes(body)
    response = await call_next(request)
    original = response.body_iterator

    async def chunks():
        with (LOG / (request_id + '.response.sse')).open('wb') as output:
            async for chunk in original:
                output.write(chunk.encode() if isinstance(chunk, str) else chunk)
                output.flush()
                yield chunk

    response.body_iterator = chunks()
    with (LOG / 'wire_index.jsonl').open('a') as output:
        output.write(json.dumps({'timestamp': time.time(), 'request_id': request_id,
                                 'path': request.url.path, 'status_code': response.status_code}) + '\n')
    return response


if __name__ == '__main__':
    uvicorn.run(app, uds=os.environ['SCENE_PROXY_SOCKET'], log_level='warning')
