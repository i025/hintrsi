#!/usr/bin/env python3
"""Copy the existing private Python runtime into the disposable VM."""

import importlib.metadata
import io
import json
import subprocess
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT.parent / "hint-baseline-run"
ARCHIVE = ROOT / "vm/python-runtime.tar.gz"
VM_RUNTIME = "/opt/hint-codex-runtime"


def source_filter(info):
    if "__pycache__" in Path(info.name).parts:
        return None
    return info


def main():
    started = time.monotonic()
    with tarfile.open(ARCHIVE, "w:gz", compresslevel=1) as archive:
        archive.add(OLD / "python/cpython-3.12.16-linux-x86_64-gnu",
                    arcname="python", filter=source_filter)
        archive.add(OLD / "env/lib/python3.12/site-packages",
                    arcname="python/lib/python3.12/site-packages", filter=source_filter)
        scripts = {
            "litellm": "from litellm import run_server\nrun_server()\n",
            "pip3": "from pip._internal.cli.main import main\nraise SystemExit(main())\n",
        }
        for name, body in scripts.items():
            content = ("#!/opt/python3.12-tmp/bin/python3\n" + body).encode()
            info = tarfile.TarInfo("python/bin/" + name)
            info.mode = 0o755
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))

    ssh = [
        "ssh", "-F", "/dev/null", "-S", str(ROOT / "vm/ssh-control.sock"),
        "-p", "22230", "-i", str(OLD / "vm/ssh_key"),
        "-o", "UserKnownHostsFile=" + str(ROOT / "vm/known_hosts"),
        "-o", "StrictHostKeyChecking=yes", "-o", "BatchMode=yes",
        "experiment@127.0.0.1",
    ]
    subprocess.run(ssh + ["sudo mkdir -p " + VM_RUNTIME], check=True)
    with ARCHIVE.open("rb") as content:
        subprocess.run(ssh + ["sudo tar -xzf - -C " + VM_RUNTIME],
                       stdin=content, check=True)
    record = {
        "archive": str(ARCHIVE), "archive_bytes": ARCHIVE.stat().st_size,
        "vm_directory": VM_RUNTIME + "/python",
        "container_mount": "/opt/python3.12-tmp", "mount_mode": "ro",
        "python": "3.12.16",
        "packages": {name: importlib.metadata.version(name) for name in (
            "claude-agent-sdk", "litellm", "anyio", "tiktoken", "httpx")},
        "elapsed_seconds": time.monotonic() - started,
    }
    (ROOT / "preflight/runtime_bundle.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
