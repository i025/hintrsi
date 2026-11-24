#!/usr/bin/env python3
"""Start the isolated 8-vCPU experiment overlay using the existing VM image."""

import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT.parent / "hint-baseline-run"
VM = ROOT / "vm"
RUNTIME = VM / "runtime"

state = json.loads((OLD / "vm-cpu-probe/vm-state.json").read_text())
args = state["args"][:]
for index, value in enumerate(args):
    if value.startswith(str(OLD / "vm/qemu/")):
        args[index] = value.replace(str(OLD / "vm/qemu"), str(RUNTIME), 1)
    elif value.startswith("file=" + str(OLD / "vm-cpu-probe/guest.qcow2")):
        args[index] = value.replace(str(OLD / "vm-cpu-probe/guest.qcow2"), str(VM / "guest.qcow2"))
    elif value == "user,id=net0,hostfwd=tcp:127.0.0.1:22229-:22":
        args[index] = "user,id=net0,hostfwd=tcp:127.0.0.1:22230-:22"
    elif str(OLD / "vm-cpu-probe/") in value:
        args[index] = value.replace(str(OLD / "vm-cpu-probe"), str(VM))

env = dict(os.environ)
env["LD_LIBRARY_PATH"] = ":".join(str(RUNTIME / part) for part in (
    "lib/x86_64-linux-gnu", "usr/lib/x86_64-linux-gnu"))
with (VM / "qemu.log").open("ab") as log:
    proc = subprocess.Popen(["nice", "-n", "10"] + args, env=env,
                            stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                            start_new_session=True)
record = {"pid": proc.pid, "args": args, "ssh_port": 22230, "vcpus": 8,
          "memory_mb": 147456, "started_at_unix": time.time(),
          "original_disk_opened_readonly": True,
          "overlay": str(VM / "guest.qcow2")}
(VM / "vm-state.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps({"pid": proc.pid, "ssh_port": 22230, "vcpus": 8}))
