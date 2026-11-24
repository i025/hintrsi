"""Check the nine fixed images in disposable containers without model calls."""
import concurrent.futures
import json
import time
from pathlib import Path

import docker
import pyarrow.parquet as pq

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]


def lane_check(lane, rows):
    client = docker.DockerClient(base_url=lane["docker_host"], timeout=240)
    results = []
    try:
        for task in lane["tasks"]:
            row = rows[task]
            container = client.containers.run(
                row["image_name"], name="fixes13-workspace-" + task,
                entrypoint="", command=["tail", "-f", "/dev/null"], detach=True,
                nano_cpus=8_000_000_000, mem_limit="128g", network_mode="none",
                labels={"hint.experiment_name": "preflight_fixes13_images"},
            )
            result = {"task": task, "lane": lane["lane"], "passed": False,
                      "started_at_unix": time.time(), "real_model_calls": 0}
            try:
                def git(*args):
                    code, data = container.exec_run(["git", *args], workdir="/app")
                    if code != 0:
                        raise RuntimeError(data.decode(errors="replace"))
                    return data.decode().strip()
                git("checkout", "-B", "main", row["base_commit"])
                result["branch"] = git("branch", "--show-current")
                result["source_diff"] = git("diff", row["base_commit"])
                git("checkout", "-b", "preflight-implementation", "main")
                git("config", "user.email", "fixture@example.invalid")
                git("config", "user.name", "Fixture")
                git("commit", "--allow-empty", "--no-verify", "-m", "Workspace preflight")
                result["new_branch_and_commit"] = git("branch", "--show-current") == "preflight-implementation"
                result["passed"] = result["branch"] == "main" and not result["source_diff"] and result["new_branch_and_commit"]
            except Exception as exc:
                result["error"] = str(exc)
            finally:
                container.remove(force=True)
                result["container_removed"] = True
                result["finished_at_unix"] = time.time()
            results.append(result)
            print(json.dumps(result), flush=True)
    finally:
        client.close()
    return results


def main():
    manifest = json.loads((ROOT / "preflight/parallel_runtime/runtime_manifest.json").read_text())
    rows = {row["instance_id"]: row for row in pq.read_table(
        ROOT.parent / "hint-baseline-run/data/deep_swe_tasks.parquet").to_pylist()}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(lane_check, lane, rows) for lane in manifest["lanes"]]
        results = [result for future in futures for result in future.result()]
    report = {"passed": len(results) == 9 and all(r["passed"] for r in results),
              "real_model_calls": 0, "cases": results}
    (OUT / "image_workspaces.json").write_text(json.dumps(report, indent=2))
    return int(not report["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
