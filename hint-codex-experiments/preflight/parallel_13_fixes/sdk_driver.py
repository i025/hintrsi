"""Exercise actual SDK writes and teacher read-only mounts using existing fixtures."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
B = ROOT / "preflight/exec_action_probe/transport/complete_sdk"
M = ROOT / "preflight/exec_action_probe/full_chain/continuation"
sys.path.insert(0, str(B))
import driver
from driver import restrict_network


def student():
    target = OUT / "sdk_student"
    driver.HERE = target
    driver.SOURCE = ROOT / "source_parallel_13"
    original = driver.create_container
    driver.create_container = lambda client, image, name, experiment: original(client, image, "codex-fixes13-student", "preflight_fixes13_student")
    driver.restrict_network = lambda container: restrict_network(container, lane=5, ports=(8785,))
    sys.argv = [sys.argv[0], "--session", "fixes13-student", "--backend", "http://172.17.0.1:8785"]
    return driver.main()


def teacher():
    import docker
    import pyarrow.parquet as pq
    out = OUT / "sdk_teacher"
    out.mkdir()
    driver.SOURCE = ROOT / "source_parallel_13"
    client = docker.DockerClient(base_url="unix://" + str(ROOT / "vm-lane5/docker.sock"), timeout=1500)
    row = next(row for row in pq.read_table(ROOT.parent / "hint-baseline-run/data/deep_swe_tasks.parquet").to_pylist() if "sqlfmt" in row["instance_id"].lower())
    container = driver.create_container(client, client.images.get(row["image_name"]), "codex-fixes13-teacher", "preflight_fixes13")
    record = {"started_at_unix": time.time(), "passed": False, "container": container.id, "ofox_calls": 0}
    def command(args):
        code, data = container.exec_run(args, workdir="/app")
        assert code == 0, (args, code, data[-2000:])
        return data
    try:
        command(["bash", "-c", "rm -rf /app /root/.claude; mkdir -p /app/data"])
        (out / "network.json").write_text(json.dumps(driver.restrict_network(container, lane=5, ports=(8785,)), indent=2))
        for path in (B / "fixture").rglob("*"):
            if path.is_file():
                driver.put(container, "/app/" + str(path.relative_to(B / "fixture")), path.read_bytes())
        driver.install_sdk_files(container)
        materials = M / "attempt_01/materials"
        for name in ("teacher_system.md", "golden_diff.diff", "teacher_initial.md"):
            driver.put(container, "/tmp/" + name, (materials / name).read_bytes())
        permission_prompt = "For this permission preflight, read /app/window_report.py and /tmp/golden_diff.diff with the available Read tool. Write one conceptual hint of at most 80 English words to /tmp/hint_output.md. Do not change the repository or reference patch, reveal the exact edit, or run tests."
        (out / "permission_prompt.txt").write_text(permission_prompt)
        driver.put(container, "/tmp/teacher_initial.md", permission_prompt)
        driver.put(container, "/tmp/teacher_guest.py", (M / "m_i_guest.py").read_bytes())
        driver.put(container, "/tmp/config.yaml", driver.proxy_config("http://172.17.0.1:8785/sessions/fixes13-teacher/teacher/generate/v1"))
        command(["bash", "-c", "set -e; git init -q /app; git config user.email fixture@example.invalid; git config user.name Fixture; git add .; git commit -qm Initial; mount --bind /app /app; mount -o remount,bind,ro /app; mount --bind /tmp/golden_diff.diff /tmp/golden_diff.diff; mount -o remount,bind,ro /tmp/golden_diff.diff"])
        base = command(["git", "rev-parse", "HEAD"]).decode().strip()
        command(["bash", "-c", "nohup env PYTHONPATH=/tmp PYTHONUNBUFFERED=1 LITELLM_LOCAL_MODEL_COST_MAP=True /opt/python3.12-tmp/bin/litellm --config /tmp/config.yaml --host 127.0.0.1 --port 8768 >/tmp/proxy.log 2>&1 </dev/null &"])
        wait = "import time,urllib.request\nfor i in range(600):\n try:\n  urllib.request.urlopen('http://127.0.0.1:8768/health/liveliness',timeout=1).read();break\n except OSError: time.sleep(1)\nelse: raise RuntimeError('Proxy startup exceeded 600 seconds')"
        command([driver.PYTHON, "-c", wait])
        code, stdout = container.exec_run(["timeout", "--signal=INT", "--kill-after=20", "1000", driver.PYTHON, "/tmp/teacher_guest.py", "teacher-initial", "--base-commit", base, "--prompt", "/tmp/teacher_initial.md", "--output", "/tmp/teacher_out"], workdir="/app")
        (out / "stdout.log").write_bytes(stdout)
        driver.collect_output(container, "/tmp/teacher_out", out)
        (out / "proxy.log").write_bytes(command(["cat", "/tmp/proxy.log"]))
        result = json.loads((out / "stage_result.json").read_text())
        patch = command(["git", "diff", base]).decode()
        (out / "repository.diff").write_text(patch)
        golden = command(["cat", "/tmp/golden_diff.diff"])
        record.update(exit_code=code, repository_unchanged=not patch, golden_unchanged=golden == (materials / "golden_diff.diff").read_bytes(), hint_artifact_written=(out / "hint_output.md").exists())
        record["passed"] = code == 0 and result["passed"] and record["repository_unchanged"] and record["golden_unchanged"] and record["hint_artifact_written"]
    finally:
        container.remove(force=True)
        client.close()
        record.update(container_removed=True, finished_at_unix=time.time())
        (out / "host_result.json").write_text(json.dumps(record, indent=2))
    print(json.dumps(record), flush=True)
    return int(not record["passed"])


if __name__ == "__main__":
    mode = sys.argv.pop(1)
    raise SystemExit(student() if mode == "student" else teacher())
