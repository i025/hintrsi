#!/usr/bin/env python3
"""Exercise original SDK tools and resume through the local Codex bridge."""

import io
import argparse
import json
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

import docker

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source"
OUT = ROOT / "preflight/sdk_fixture"
sys.path.insert(0, str(SOURCE))
from constant_zhy import render_proxy_config

PYTHON = "/opt/python3.12-tmp/bin/python3"
SESSION = "preflight-sdk-fixture"
NAME = "codex-sdk-preflight"


def put_file(container, path, content):
    content = content.encode() if isinstance(content, str) else content
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w") as output:
        item = tarfile.TarInfo(Path(path).name)
        item.size = len(content)
        output.addfile(item, io.BytesIO(content))
    container.put_archive(str(Path(path).parent), archive.getvalue())


def copy_file(container, path, target):
    chunks, _ = container.get_archive(path)
    with tarfile.open(fileobj=io.BytesIO(b"".join(chunks))) as archive:
        target.write_bytes(archive.extractfile(Path(path).name).read())


def status():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open("http://127.0.0.1:8765/status", timeout=10) as response:
        return json.load(response)


def main():
    global OUT, SESSION
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="sdk_fixture")
    parser.add_argument("--session", default="preflight-sdk-fixture")
    args = parser.parse_args()
    OUT = ROOT / "preflight" / args.label
    SESSION = args.session
    OUT.mkdir(parents=True, exist_ok=True)
    result = {"session": SESSION, "started_at_unix": time.time(), "turns": []}
    initial = status()
    if initial["stopped"]:
        raise RuntimeError(initial["stop_reason"])
    client = docker.DockerClient(base_url="unix://" + str(ROOT / "vm/docker.sock"), timeout=1200)
    old = client.containers.get(NAME)
    image = old.image
    old.remove(force=True)
    env = {item.split("=", 1)[0]: "experiment-local"
           for item in image.attrs["Config"]["Env"]
           if any(word in item.split("=", 1)[0].upper() for word in (
               "KEY", "TOKEN", "SECRET", "PASSWORD", "ANTHROPIC", "OPENAI", "OFOX", "HUBROUTER"))}
    env.update({
        "ANTHROPIC_BASE_URL": "http://127.0.0.1:4000",
        "ANTHROPIC_AUTH_TOKEN": "experiment-local",
        "ANTHROPIC_MODEL": "gpt-6.1-terra",
        "ANTHROPIC_SMALL_FAST_MODEL": "gpt-6.1-terra",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "IS_SANDBOX": "1",
        "API_TIMEOUT_MS": "600000", "PYTHONDONTWRITEBYTECODE": "1",
        "PROXY_MAX_TOKENS_CLAMP": "65536", "EXPERIMENT_SESSION": SESSION,
        "HTTP_PROXY": "", "HTTPS_PROXY": "", "ALL_PROXY": "",
        "http_proxy": "", "https_proxy": "", "all_proxy": "", "NO_PROXY": "*",
    })
    container = client.containers.run(
        image.id, name=NAME, entrypoint="", command=["tail", "-f", "/dev/null"],
        detach=True, mem_limit="128g", nano_cpus=8_000_000_000, privileged=True,
        environment=env,
        volumes={"/opt/hint-codex-runtime/python": {"bind": "/opt/python3.12-tmp", "mode": "ro"}},
    )
    (ROOT / "preflight/sdk_fixture_container.json").write_text(json.dumps({
        "container_id": container.id, "name": NAME, "image": image.id,
        "cpu": 8, "memory": "128g", "runtime_mount": "/opt/hint-codex-runtime/python",
        "purpose": "tiny fixture only, no benchmark task",
    }, indent=2) + "\n")
    try:
        setup = "rm -rf /app /root/.claude; mkdir -p /app /tmp/fixture_turn_1 /tmp/fixture_turn_2"
        code, output = container.exec_run(["/bin/bash", "-c", setup])
        if code:
            raise RuntimeError(output.decode())
        for local, remote in [
            (SOURCE / "run_cc_sdk.py", "/tmp/sdk_script.py"),
            (SOURCE / "logging_utils.py", "/tmp/logging_utils.py"),
            (SOURCE / "litellm_proxy/claude_code_proxy.py", "/tmp/litellm_call_backs.py"),
            (SOURCE / "litellm_proxy/streaming_fix.py", "/tmp/streaming_fix.py"),
        ]:
            put_file(container, remote, local.read_bytes())
        put_file(container, "/tmp/config.yaml", render_proxy_config(
            "openai", "gpt-6.1-terra", "experiment-local",
            "http://172.17.0.1:8765/sessions/" + SESSION + "/student/solve/v1",
            reasoning_effort="low", max_tokens=65536,
        ))
        put_file(container, "/app/counter.py", "def add(a, b):\n    return a - b\n")
        put_file(container, "/app/test_counter.py",
                 "import unittest\nfrom counter import add\n\nclass CounterTest(unittest.TestCase):\n"
                 "    def test_add(self):\n        self.assertEqual(add(3, 2), 5)\n")
        bootstrap = (
            "git init -q && git config user.email fixture@example.com && git config user.name Fixture "
            "&& git add counter.py test_counter.py && git commit -qm initial && git rev-parse HEAD"
        )
        code, output = container.exec_run(["/bin/bash", "-c", bootstrap], workdir="/app")
        if code:
            raise RuntimeError(output.decode())
        base = output.decode().strip()
        version_code = (
            "import sys,json,importlib.metadata,subprocess;from pathlib import Path;import claude_agent_sdk;"
            "p=Path(claude_agent_sdk.__file__).parent/'_bundled'/'claude';"
            "print(json.dumps({'python':sys.version,'sdk':importlib.metadata.version('claude-agent-sdk'),"
            "'litellm':importlib.metadata.version('litellm'),'claude_cli':subprocess.check_output([str(p),'--version'],text=True)}))"
        )
        code, output = container.exec_run([PYTHON, "-c", version_code])
        if code:
            raise RuntimeError(output.decode())
        result["runtime"] = json.loads(output)
        if result["runtime"]["sdk"] != "0.2.186":
            raise RuntimeError("Fixture SDK version differs from the frozen runtime")
        container.exec_run(["/bin/bash", "-c",
            "PYTHONPATH=/tmp nohup /opt/python3.12-tmp/bin/litellm --config /tmp/config.yaml "
            "> /tmp/proxy.log 2>&1 &"])
        ready = False
        for _ in range(60):
            code, _ = container.exec_run([PYTHON, "-c", "import urllib.request;urllib.request.urlopen('http://127.0.0.1:4000/health/liveliness',timeout=2).read()"])
            if code == 0:
                ready = True
                break
            time.sleep(1)
        if not ready:
            raise RuntimeError("Fixture LiteLLM proxy did not become ready")

        prompts = [
            "Validate this tiny local fixture. Read counter.py and test_counter.py, fix add(a, b) "
            "so the existing test passes, and run python3 -m unittest -v. Do not change the existing "
            "test. Use at most six tool calls and stop after reporting the test result.",
            "Continue the same session and keep the previous fix. Read counter.py, add multiply(a, b) "
            "returning the product, then run python3 -m unittest -v and verify multiply(3, 4) == 12 "
            "with a Python command. Use at most six tool calls and stop after reporting the result.",
        ]
        sid = None
        for turn, prompt in enumerate(prompts, 1):
            previous_sid = sid
            args = [PYTHON, "/tmp/sdk_script.py", "--cwd", "/app", "--base_commit", base,
                    "--output_dir", f"/tmp/fixture_turn_{turn}", "--log_path", "/tmp/sdk_script.log"]
            args += (["--resume_session_id", sid, "--extra_message", prompt]
                     if sid else ["--problem_statement", prompt])
            started = time.monotonic()
            code, output = container.exec_run(args, workdir="/app", environment=env)
            turn_dir = OUT / f"turn_{turn}"
            turn_dir.mkdir(exist_ok=True)
            (turn_dir / "stdout.log").write_bytes(output)
            for name in ["trajs.json", "patch.diff"]:
                copy_file(container, f"/tmp/fixture_turn_{turn}/{name}", turn_dir / name)
            trajectory = json.loads((turn_dir / "trajs.json").read_text())
            metadata = trajectory["metadata"]
            sid = metadata.get("ResultMessage", {}).get("session_id")
            if turn == 2 and sid != previous_sid:
                raise RuntimeError("SDK resume changed the student session")
            snapshot = status()
            result["turns"].append({
                "turn": turn, "exit_code": code, "wall_seconds": time.monotonic() - started,
                "sdk_session_id": sid, "metadata": metadata, "bridge_status": snapshot,
            })
            if code or metadata["status"] != "completed" or snapshot["stopped"]:
                raise RuntimeError("SDK fixture turn did not complete")
            verification = "python3 -m unittest -v && python3 -c 'from counter import add; assert add(3,2)==5'"
            if turn == 2:
                verification += " && python3 -c 'from counter import multiply; assert multiply(3,4)==12'"
            test_code, test_output = container.exec_run(
                ["/bin/bash", "-c", verification], workdir="/app"
            )
            result["turns"][-1]["verification"] = {
                "exit_code": test_code, "output": test_output.decode(),
            }
            if test_code or b"+++ b/counter.py" not in (turn_dir / "patch.diff").read_bytes():
                raise RuntimeError("Fixture tests failed or expected source patch was not exported")
        code, output = container.exec_run(["/bin/bash", "-c",
            "python3 -m unittest -v && python3 -c 'from counter import add,multiply; assert add(3,2)==5; assert multiply(3,4)==12'"],workdir="/app")
        result["verification"] = {"exit_code": code, "output": output.decode()}
        result["status"] = "passed" if code == 0 else "failed"
    except Exception as exc:
        result["status"] = "incomplete"
        result["error"] = str(exc)
        raise
    finally:
        for name in ["proxy.log", "sdk_script.log", "system_prompt_config.json", "system_prompt_actual.json"]:
            try:
                copy_file(container, "/tmp/" + name, OUT / name)
            except docker.errors.NotFound:
                pass
        result["finished_at_unix"] = time.time()
        (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        container.stop(timeout=10)
        client.close()
        print(json.dumps({"status": result.get("status"), "error": result.get("error"),
                          "turns": len(result["turns"]), "result": str(OUT / "result.json")}))


if __name__ == "__main__":
    main()
