"""Evaluate deep-swe patches using the verifier containers from tests/Dockerfile.

Usage:
    python eval_deep_swe.py \
        --tasks_dir ./tasks \
        --patches_dir ./output/infer_logs \
        --output_dir ./eval_output \
        --num_workers 8
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import tarfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

import docker
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def find_patch_file(patches_dir: Path, instance_id: str) -> Optional[Path]:
    candidate = patches_dir / instance_id / "patch.diff"
    if candidate.exists() and candidate.stat().st_size > 0:
        return candidate
    return None


def inject_file_to_container(container, content: bytes, container_path: str):
    dir_path = str(Path(container_path).parent)
    container.exec_run(f"mkdir -p {dir_path}")

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo(name=Path(container_path).name)
        info.size = len(content)
        info.mtime = time.time()
        tar.addfile(info, io.BytesIO(content))
    buf.seek(0)
    container.put_archive(dir_path, buf)


def build_verifier_image(client: docker.DockerClient, task_dir: Path, task_id: str) -> str:
    tests_dir = task_dir / "tests"
    image_tag = f"deepswe-verifier-{task_id}".lower()

    try:
        client.images.get(image_tag)
        return image_tag
    except docker.errors.ImageNotFound:
        pass

    log.info("[%s] Building verifier image from %s", task_id, tests_dir)
    image, build_log = client.images.build(
        path=str(tests_dir),
        tag=image_tag,
        rm=True,
        timeout=1800,
    )
    return image_tag


def run_verifier(
    client: docker.DockerClient,
    task_id: str,
    image_tag: str,
    patch_content: bytes,
) -> dict:
    container = None
    try:
        container = client.containers.run(
            image_tag,
            command="sleep infinity",
            detach=True,
            mem_limit="8g",
            network_mode="none",
        )

        container.exec_run("mkdir -p /logs/artifacts /logs/verifier")
        inject_file_to_container(container, patch_content, "/logs/artifacts/model.patch")

        exec_result = container.exec_run(
            "/bin/bash /tests/test.sh",
            workdir="/app",
            demux=True,
        )
        stdout = (exec_result.output[0] or b"").decode("utf-8", errors="replace")
        stderr = (exec_result.output[1] or b"").decode("utf-8", errors="replace")

        reward = None
        try:
            bits, _ = container.get_archive("/logs/verifier/reward.json")
            reward_tar = io.BytesIO()
            for chunk in bits:
                reward_tar.write(chunk)
            reward_tar.seek(0)
            with tarfile.open(fileobj=reward_tar) as tar:
                member = tar.getmembers()[0]
                f = tar.extractfile(member)
                if f:
                    reward = json.loads(f.read().decode("utf-8"))
        except Exception:
            try:
                bits, _ = container.get_archive("/logs/verifier/reward.txt")
                reward_tar = io.BytesIO()
                for chunk in bits:
                    reward_tar.write(chunk)
                reward_tar.seek(0)
                with tarfile.open(fileobj=reward_tar) as tar:
                    member = tar.getmembers()[0]
                    f = tar.extractfile(member)
                    if f:
                        reward = {"reward": float(f.read().decode("utf-8").strip())}
            except Exception:
                pass

        return {
            "instance_id": task_id,
            "reward": reward,
            "exit_code": exec_result.exit_code,
            "stdout_tail": stdout[-8000:] if len(stdout) > 8000 else stdout,
            "stderr_tail": stderr[-8000:] if len(stderr) > 8000 else stderr,
        }

    except Exception as e:
        log.exception("[%s] Verifier failed: %s", task_id, e)
        return {
            "instance_id": task_id,
            "reward": None,
            "exit_code": -1,
            "error": str(e),
        }
    finally:
        if container:
            try:
                container.remove(force=True)
            except Exception:
                pass


def evaluate_task(
    task_dir: Path,
    task_id: str,
    patches_dir: Path,
    output_dir: Path,
    delete_image: bool = True,
) -> dict:
    client = docker.from_env(timeout=1800)

    patch_path = find_patch_file(patches_dir, task_id)
    if patch_path is None:
        log.warning("[%s] No patch found, skipping", task_id)
        return {"instance_id": task_id, "reward": None, "status": "no_patch"}

    patch_content = patch_path.read_bytes()

    image_tag = build_verifier_image(client, task_dir, task_id)
    result = run_verifier(client, task_id, image_tag, patch_content)

    task_output_dir = output_dir / task_id
    task_output_dir.mkdir(parents=True, exist_ok=True)
    with open(task_output_dir / "eval_result.json", "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    if delete_image:
        try:
            client.images.remove(image_tag, force=True)
        except Exception:
            pass

    return result


def discover_tasks(tasks_dir: Path) -> list[tuple[str, Path]]:
    tasks = []
    for task_dir in sorted(tasks_dir.iterdir()):
        if not task_dir.is_dir():
            continue
        config_path = task_dir / "task.toml"
        tests_dir = task_dir / "tests"
        if not config_path.exists() or not tests_dir.exists():
            continue

        config = tomllib.loads(config_path.read_text())
        task_id = config.get("metadata", {}).get("task_id", task_dir.name)
        tasks.append((task_id, task_dir))
    return tasks


def main():
    parser = argparse.ArgumentParser(description="Evaluate deep-swe patches")
    parser.add_argument("--tasks_dir", type=Path, required=True)
    parser.add_argument("--patches_dir", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--num_workers", type=int, default=4)
    parser.add_argument("--keep_images", action="store_true")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    tasks = discover_tasks(args.tasks_dir)
    log.info("Found %d tasks to evaluate", len(tasks))

    results = []

    with ThreadPoolExecutor(max_workers=args.num_workers) as executor:
        futures = {}
        for task_id, task_dir in tasks:
            future = executor.submit(
                evaluate_task,
                task_dir,
                task_id,
                args.patches_dir,
                args.output_dir,
                delete_image=not args.keep_images,
            )
            futures[future] = task_id

        for future in tqdm(as_completed(futures), total=len(futures), desc="Evaluating"):
            task_id = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                log.exception("[%s] Evaluation failed: %s", task_id, e)
                results.append({"instance_id": task_id, "reward": None, "error": str(e)})

    # Summary
    total = len(results)
    has_reward = [r for r in results if r.get("reward") is not None]
    solved = [r for r in has_reward if r["reward"].get("reward", 0) == 1]
    no_patch = [r for r in results if r.get("status") == "no_patch"]
    errored = [r for r in results if r.get("reward") is None and r.get("status") != "no_patch"]

    summary = {
        "total": total,
        "evaluated": len(has_reward),
        "solved": len(solved),
        "no_patch": len(no_patch),
        "errored": len(errored),
        "accuracy": len(solved) / total if total > 0 else 0,
        "accuracy_evaluated": len(solved) / len(has_reward) if has_reward else 0,
        "results": results,
    }

    summary_path = args.output_dir / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    log.info("=" * 60)
    log.info("Evaluation Summary")
    log.info("  Total tasks:      %d", total)
    log.info("  Evaluated:        %d", len(has_reward))
    log.info("  Solved (reward=1):%d", len(solved))
    log.info("  No patch:         %d", len(no_patch))
    log.info("  Errored:          %d", len(errored))
    log.info("  Accuracy (total): %.1f%%", summary["accuracy"] * 100)
    log.info("  Accuracy (eval):  %.1f%%", summary["accuracy_evaluated"] * 100)
    log.info("Results written to: %s", summary_path)


if __name__ == "__main__":
    main()
