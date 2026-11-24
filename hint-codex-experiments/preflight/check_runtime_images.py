#!/usr/bin/env python3
"""Check the shared read-only runtime against existing task base images."""

import json
import time
from pathlib import Path

import docker

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "preflight/runtime_image_compatibility.json"
PYTHON = "/opt/python3.12-tmp/bin/python3"


def main():
    client = docker.DockerClient(base_url="unix://" + str(ROOT / "vm/docker.sock"), timeout=720)
    images = [image for image in client.images.list()
              if any(tag.startswith("is.jd.com/") for tag in image.tags)]
    results = []
    for index, image in enumerate(images, 1):
        started = time.monotonic()
        print(json.dumps({"stage": "start", "image": image.tags, "index": index}), flush=True)
        container = client.containers.run(
            image.id, name=f"codex-runtime-check-{index}", entrypoint="",
            command=["tail", "-f", "/dev/null"], detach=True,
            mem_limit="128g", nano_cpus=8_000_000_000, network_mode="none",
            environment={"PYTHONDONTWRITEBYTECODE": "1"},
            volumes={"/opt/hint-codex-runtime/python": {"bind": "/opt/python3.12-tmp", "mode": "ro"}},
        )
        try:
            program = (
                "import sys,platform,json,importlib.metadata;import claude_agent_sdk,litellm;"
                "from pathlib import Path;"
                "print(json.dumps({'python':sys.version,'libc':platform.libc_ver(),"
                "'os_release':Path('/etc/os-release').read_text(),"
                "'sdk':importlib.metadata.version('claude-agent-sdk'),"
                "'litellm':importlib.metadata.version('litellm')}))"
            )
            code, output = container.exec_run(["timeout", "600", PYTHON, "-c", program])
            results.append({"tags": image.tags, "exit_code": code,
                            "output": output.decode(), "elapsed_seconds": time.monotonic() - started})
            OUTPUT.write_text(json.dumps(results, indent=2) + "\n")
            print(json.dumps({"stage": "finished", "index": index, "exit_code": code,
                              "elapsed_seconds": results[-1]["elapsed_seconds"]}), flush=True)
        finally:
            container.remove(force=True)
    client.close()


if __name__ == "__main__":
    main()
