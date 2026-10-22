#!/usr/bin/env python3
"""HEXADECARUNNER: deterministic, artifact-mediated scatter/gather (Python 3.11+)."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any

SCHEMA = 1
WORKER_COUNTS = (1, 4, 8, 16, 32)
MAX_JSON = 32 * 1024 * 1024
MAX_RESULT = 1024 * 1024
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _pairs(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def loads(text: str) -> Any:
    def invalid(value: str) -> None:
        raise ValueError(f"non-finite JSON value: {value}")
    return json.loads(text, object_pairs_hook=_pairs, parse_constant=invalid)


def read_json(path: Path) -> Any:
    if path.stat().st_size > MAX_JSON:
        raise ValueError(f"JSON file too large: {path}")
    return loads(path.read_text())


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical(value) + b"\n"
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def integer(value: Any, low: int, high: int, label: str) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{label} must be an integer in [{low}, {high}]")
    return value


def within(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError("path must stay inside the workload checkout")
    return path


def validate_tasks(tasks: Any) -> None:
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 4096:
        raise ValueError("task list must contain 1..4096 tasks")
    seen = set()
    for task in tasks:
        if not isinstance(task, dict) or set(task) != {"id", "payload"}:
            raise ValueError("each task must contain exactly id and payload")
        key = task["id"]
        if not isinstance(key, str) or not ID.fullmatch(key) or key in seen:
            raise ValueError(f"invalid or duplicate task id: {key!r}")
        if not isinstance(task["payload"], dict):
            raise ValueError("task payload must be a JSON object")
        canonical(task)
        seen.add(key)


def build_manifest(*, workers: int = 4, processes: int = 4, count: int = 64,
                   cells: int = 48, steps: int = 1000, retries: int = 1,
                   task_timeout: int = 300, source: str = "local",
                   framework_source: str = "local", tasks: list | None = None,
                   adapter: str = "", workdir: Path = Path(".")) -> dict:
    if tasks is None:
        integer(count, 1, 4096, "tasks")
        integer(cells, 4, 128, "cells")
        integer(steps, 1, 100000, "steps")
        tasks = [{"id": f"t{i:06d}", "payload": {"seed": i + 1, "cells": cells, "steps": steps}}
                 for i in range(count)]
    adapter_hash = ""
    if adapter:
        adapter_hash = hashlib.sha256(within(workdir, adapter).read_bytes()).hexdigest()
    manifest = {"schema": SCHEMA, "workers": workers, "processes": processes,
                "retries": retries, "task_timeout": task_timeout,
                "source": source, "framework_source": framework_source,
                "adapter": adapter, "adapter_sha256": adapter_hash, "tasks": tasks}
    manifest["experiment_id"] = digest(manifest)
    validate_manifest(manifest)
    return manifest


def validate_manifest(manifest: dict) -> None:
    expected = {"schema", "workers", "processes", "retries", "task_timeout", "source",
                "framework_source", "adapter", "adapter_sha256", "tasks", "experiment_id"}
    if not isinstance(manifest, dict) or set(manifest) != expected or manifest["schema"] != SCHEMA:
        raise ValueError("unsupported manifest schema or fields")
    unsigned = {k: v for k, v in manifest.items() if k != "experiment_id"}
    if digest(unsigned) != manifest["experiment_id"]:
        raise ValueError("manifest digest mismatch")
    integer(manifest["workers"], 1, 32, "workers")
    if manifest["workers"] not in WORKER_COUNTS:
        raise ValueError("workers must be 1, 4, 8, 16 or 32")
    integer(manifest["processes"], 1, 4, "processes")
    integer(manifest["retries"], 0, 3, "retries")
    integer(manifest["task_timeout"], 1, 18000, "task timeout")
    for field in ("source", "framework_source", "adapter", "adapter_sha256"):
        if not isinstance(manifest[field], str):
            raise ValueError(f"{field} must be a string")
    if not manifest["source"] or not manifest["framework_source"]:
        raise ValueError("source identities cannot be empty")
    validate_tasks(manifest["tasks"])
    if len(manifest["tasks"]) < manifest["workers"]:
        raise ValueError("at least one task per worker is required")
    if not manifest["adapter"]:
        for task in manifest["tasks"]:
            payload = task["payload"]
            if set(payload) != {"seed", "cells", "steps"}:
                raise ValueError("reference workload needs seed, cells and steps")
            integer(payload["seed"], 0, 2**32 - 1, "seed")
            integer(payload["cells"], 4, 128, "cells")
            integer(payload["steps"], 1, 100000, "steps")


def assigned(manifest: dict, index: int, baseline: bool = False) -> list:
    count = 1 if baseline else manifest["workers"]
    integer(index, 0, count - 1, "worker index")
    return sorted(manifest["tasks"], key=lambda task: task["id"])[index::count]


def simulation(payload: dict) -> dict:
    """Portable integer diffusion on a periodic grid; no RNG or float drift."""
    size, steps, seed = payload["cells"], payload["steps"], payload["seed"]
    state = [(seed * 1103515245 + i * 12345) % 65536 for i in range(size * size)]
    neighbors = [((y - 1) % size * size + x, (y + 1) % size * size + x,
                  y * size + (x - 1) % size, y * size + (x + 1) % size)
                 for y in range(size) for x in range(size)]
    for _ in range(steps):
        state = [(4 * state[i] + state[a] + state[b] + state[c] + state[d]) // 8
                 for i, (a, b, c, d) in enumerate(neighbors)]
    return {"state_sha256": digest(state), "sum": sum(state), "maximum": max(state)}


def invoke_adapter(path: str, task: dict, workdir: str, timeout: int) -> Any:
    # No shell interpolation. Each task gets a new process and a JSON-only protocol.
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen([sys.executable, path], cwd=workdir,
                                   stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
                                   start_new_session=(os.name == "posix"))
        try:
            process.communicate(canonical(task), timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            process.wait()
            raise RuntimeError(f"adapter exceeded {timeout}s") from None
        if process.returncode:
            stderr.seek(0)
            detail = stderr.read(2000).decode(errors="replace")
            raise RuntimeError(f"adapter exit {process.returncode}: {detail}")
        if stdout.tell() > MAX_RESULT:
            raise ValueError("adapter result exceeds 1 MiB")
        stdout.seek(0)
        return loads(stdout.read().decode())


def execute_task(task: dict, config: dict) -> dict:
    started = time.perf_counter()
    errors = []
    for attempt in range(1, config["retries"] + 2):
        try:
            if task["id"] == config.get("fail_task") and (not config.get("fail_once") or attempt == 1):
                raise RuntimeError("injected task failure")
            result = (invoke_adapter(config["adapter_path"], task, config["workdir"], config["task_timeout"])
                      if config["adapter_path"] else simulation(task["payload"]))
            if len(canonical(result)) > MAX_RESULT:
                raise ValueError("result exceeds 1 MiB")
            return {"schema": SCHEMA, "experiment_id": config["experiment_id"],
                    "task_id": task["id"], "input_sha256": digest(task),
                    "result": result, "result_sha256": digest(result), "attempts": attempt,
                    "elapsed_seconds": time.perf_counter() - started, "retry_errors": errors}
        except Exception as error:
            errors.append(f"{type(error).__name__}: {str(error)[:2000]}")
    return {"task_id": task["id"], "failure": errors}


def validate_receipt(receipt: dict, task: dict, manifest: dict) -> None:
    if (receipt.get("schema") != SCHEMA or receipt.get("experiment_id") != manifest["experiment_id"]
            or receipt.get("task_id") != task["id"] or receipt.get("input_sha256") != digest(task)):
        raise ValueError(f"checkpoint identity mismatch for {task['id']}")
    if "result" not in receipt or receipt.get("result_sha256") != digest(receipt["result"]):
        raise ValueError(f"checkpoint result digest mismatch for {task['id']}")
    integer(receipt.get("attempts"), 1, manifest["retries"] + 1, "task attempts")
    elapsed = receipt.get("elapsed_seconds")
    if type(elapsed) not in (int, float) or not 0 <= elapsed < 1e9:
        raise ValueError("invalid task duration")


def cpu_count() -> int:
    return len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else (os.cpu_count() or 1)


def run_worker(manifest: dict, *, index: int, output: Path, baseline: bool = False,
               resume: Path | None = None, workdir: Path = Path("."),
               fail_task: str = "", fail_once: bool = False,
               run_id: str = "local", run_attempt: int = 1) -> dict:
    validate_manifest(manifest)
    integer(run_attempt, 1, 1000, "run attempt")
    tasks = assigned(manifest, index, baseline)
    lookup = {task["id"]: task for task in tasks}
    adapter_path = ""
    if manifest["adapter"]:
        adapter_path = str(within(workdir, manifest["adapter"]))
        if hashlib.sha256(Path(adapter_path).read_bytes()).hexdigest() != manifest["adapter_sha256"]:
            raise ValueError("adapter source digest mismatch")
    config = {**manifest, "adapter_path": adapter_path, "workdir": str(workdir.resolve()),
              "fail_task": fail_task, "fail_once": fail_once}
    output.mkdir(parents=True, exist_ok=True)
    if list(output.glob("task-*.json")) or (output / "worker.json").exists():
        raise ValueError("output must be fresh; use --resume with a separate output directory")
    cached = {}
    if resume is not None:
        if not resume.is_dir():
            raise ValueError("resume directory does not exist")
        for path in sorted(resume.rglob("task-*.json")):
            receipt = read_json(path)
            key = receipt.get("task_id")
            if key not in lookup:
                raise ValueError(f"foreign checkpoint task: {key}")
            validate_receipt(receipt, lookup[key], manifest)
            if key in cached and cached[key]["result_sha256"] != receipt["result_sha256"]:
                raise ValueError(f"conflicting checkpoints: {key}")
            cached[key] = receipt
    start_epoch, start_clock = time.time(), time.perf_counter()
    for key, receipt in cached.items():
        atomic_json(output / f"task-{key}.json", receipt)
    todo = [task for task in tasks if task["id"] not in cached]
    processes = min(manifest["processes"], cpu_count(), len(tasks))
    failures, completed = {}, set(cached)
    if todo:
        with ProcessPoolExecutor(max_workers=processes) as pool:
            futures = {pool.submit(execute_task, task, config): task["id"] for task in todo}
            for future in as_completed(futures):
                key = futures[future]
                try:
                    receipt = future.result()
                    if "failure" in receipt:
                        failures[key] = receipt["failure"]
                    else:
                        validate_receipt(receipt, lookup[key], manifest)
                        atomic_json(output / f"task-{key}.json", receipt)
                        completed.add(key)
                except Exception as error:
                    failures[key] = [f"worker exception: {type(error).__name__}: {error}"]
    wall = time.perf_counter() - start_clock
    summary = {"schema": SCHEMA, "experiment_id": manifest["experiment_id"],
               "role": "baseline" if baseline else "worker", "index": index,
               "run_id": run_id, "run_attempt": run_attempt,
               "status": "failed" if failures else "complete", "failures": failures,
               "expected_task_ids": sorted(lookup), "completed_task_ids": sorted(completed),
               "restored_tasks": len(cached), "computed_tasks": len(completed) - len(cached),
               "observed_cpus": cpu_count(), "processes": processes,
               "python": platform.python_version(), "platform": platform.platform(),
               "started_epoch": start_epoch, "finished_epoch": start_epoch + wall,
               "wall_seconds": wall}
    atomic_json(output / "worker.json", summary)
    return summary


def overlap(summaries: list[dict]) -> int:
    events = [(item["started_epoch"], 1) for item in summaries]
    events += [(item["finished_epoch"], -1) for item in summaries]
    active = peak = 0
    for _, change in sorted(events):
        active += change
        peak = max(peak, active)
    return peak


def reduce_results(manifest: dict, inputs: Path, *, require_baseline: bool = True,
                   run_id: str = "local") -> dict:
    validate_manifest(manifest)
    latest = {}
    for path in sorted(inputs.rglob("worker.json")):
        summary = read_json(path)
        if summary.get("experiment_id") != manifest["experiment_id"] or summary.get("run_id") != run_id:
            raise ValueError(f"foreign worker summary: {path}")
        role, index = summary.get("role"), summary.get("index")
        if role not in ("baseline", "worker"):
            raise ValueError("unknown worker role")
        integer(index, 0, 0 if role == "baseline" else manifest["workers"] - 1, "summary index")
        attempt = integer(summary.get("run_attempt"), 1, 1000, "summary attempt")
        key = (role, index)
        if key in latest and attempt == latest[key][0]["run_attempt"]:
            raise ValueError(f"duplicate worker summary for {key}, attempt {attempt}")
        if key not in latest or attempt > latest[key][0]["run_attempt"]:
            latest[key] = (summary, path.parent)
    expected = {("worker", i) for i in range(manifest["workers"])}
    if require_baseline:
        expected.add(("baseline", 0))
    if not expected.issubset(latest):
        raise ValueError(f"missing workers: {sorted(expected - set(latest))}")
    results, baseline_results, worker_summaries, baseline_summary = {}, {}, [], None
    total_attempts = total_receipts = 0
    for (role, index), (summary, directory) in sorted(latest.items()):
        tasks = {task["id"]: task for task in assigned(manifest, index, role == "baseline")}
        ids = sorted(tasks)
        if (summary.get("schema") != SCHEMA or summary.get("status") != "complete"
                or summary.get("failures") or summary.get("expected_task_ids") != ids
                or summary.get("completed_task_ids") != ids):
            raise ValueError(f"incomplete or failed {role} {index}: {summary.get('failures')}")
        files = list(directory.glob("task-*.json"))
        if {path.name for path in files} != {f"task-{key}.json" for key in ids}:
            raise ValueError(f"missing or unexpected checkpoint files for {role} {index}")
        for key in ("restored_tasks", "computed_tasks"):
            integer(summary.get(key), 0, len(tasks), key)
        if summary["restored_tasks"] + summary["computed_tasks"] != len(tasks):
            raise ValueError("invalid checkpoint counts")
        integer(summary.get("processes"), 1, manifest["processes"], "observed processes")
        integer(summary.get("observed_cpus"), summary["processes"], 4096, "observed CPUs")
        for field in ("started_epoch", "finished_epoch", "wall_seconds"):
            if type(summary.get(field)) not in (int, float) or not 0 < summary[field] < 1e12:
                raise ValueError(f"invalid timing field: {field}")
        if abs(summary["finished_epoch"] - summary["started_epoch"] - summary["wall_seconds"]) > 0.001:
            raise ValueError("inconsistent worker timing")
        target = baseline_results if role == "baseline" else results
        for path in files:
            receipt = read_json(path)
            key = receipt.get("task_id")
            if key not in tasks or path.name != f"task-{key}.json" or key in target:
                raise ValueError("duplicate or misassigned task receipt")
            validate_receipt(receipt, tasks[key], manifest)
            target[key] = receipt["result"]
            total_attempts += receipt["attempts"]
            total_receipts += 1
        if role == "baseline":
            baseline_summary = summary
        else:
            worker_summaries.append(summary)
    if baseline_summary is not None and results != baseline_results:
        raise ValueError("distributed results differ from single-runner baseline")
    if len(results) != len(manifest["tasks"]):
        raise ValueError("incomplete task coverage")
    span = max(item["finished_epoch"] for item in worker_summaries) - min(item["started_epoch"] for item in worker_summaries)
    all_summaries = worker_summaries + ([baseline_summary] if baseline_summary else [])
    reasons = []
    if baseline_summary is None:
        reasons.append("baseline not run")
    if any(item["restored_tasks"] for item in all_summaries):
        reasons.append("checkpoint reuse: not a fresh performance trial")
    if total_attempts != total_receipts:
        reasons.append("task retries: not a clean performance trial")
    if len({item["processes"] for item in all_summaries}) != 1:
        reasons.append("unequal per-runner process counts")
    eligible = not reasons
    speedup = baseline_summary["wall_seconds"] / span if eligible else None
    return {"schema": SCHEMA, "status": "passed", "experiment_id": manifest["experiment_id"],
            "source": manifest["source"], "framework_source": manifest["framework_source"],
            "workers": manifest["workers"], "tasks": len(results), "result_sha256": digest(results),
            "baseline_equal": True if baseline_summary else None,
            "performance_eligible": eligible, "performance_exclusions": reasons,
            "execution_span_seconds": span, "execution_span_speedup": speedup,
            "parallel_efficiency": speedup / manifest["workers"] if eligible else None,
            "peak_observed_worker_overlap": overlap(worker_summaries),
            "worker_execution_minutes": sum(item["wall_seconds"] for item in worker_summaries) / 60,
            "all_compute_execution_minutes": sum(item["wall_seconds"] for item in all_summaries) / 60,
            "workers_detail": worker_summaries, "baseline_detail": baseline_summary,
            "measurement_notes": ["Execution span uses runner wall clocks; assumes synchronized clocks.",
                                  "Compute timings exclude checkout/setup/artifact steps; see telemetry.json.",
                                  "Execution minutes are not billed minutes or complete job runtime.",
                                  "One trial, no statistical performance claim; requested workers may queue."]}


def markdown(report: dict) -> str:
    lines = ["# HEXADECARUNNER evidence", "", f"Status: **{report['status']}**", ""]
    if report["status"] != "passed":
        return "\n".join(lines + ["```text", report["error"], "```", ""])
    lines += [f"Tasks: {report['tasks']}; workers: {report['workers']}; peak observed compute overlap: {report['peak_observed_worker_overlap']}.",
              f"Baseline equality: {report['baseline_equal']}. Result SHA-256: `{report['result_sha256']}`.",
              "", "| Measurement | Value |", "|---|---:|",
              f"| Distributed execution span | {report['execution_span_seconds']:.3f} s |",
              f"| Worker execution minutes (not billing) | {report['worker_execution_minutes']:.3f} |",
              f"| Baseline + worker execution minutes | {report['all_compute_execution_minutes']:.3f} |"]
    if report["performance_eligible"]:
        lines += [f"| Execution-span speedup | {report['execution_span_speedup']:.3f}x |",
                  f"| Parallel efficiency | {100 * report['parallel_efficiency']:.1f}% |"]
    else:
        lines += ["", "Performance comparison suppressed: " + "; ".join(report["performance_exclusions"])]
    lines += ["", "| Role/index | CPUs | Processes | Computed | Restored | Execution seconds |",
              "|---|---:|---:|---:|---:|---:|"]
    summaries = ([report["baseline_detail"]] if report["baseline_detail"] else []) + report["workers_detail"]
    for item in summaries:
        lines.append(f"| {item['role']}/{item['index']} | {item['observed_cpus']} | {item['processes']} | {item['computed_tasks']} | {item['restored_tasks']} | {item['wall_seconds']:.3f} |")
    return "\n".join(lines + ["", *report["measurement_notes"], ""])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    for name, default in (("workers", 4), ("processes", 4), ("tasks", 64), ("cells", 48),
                          ("steps", 1000), ("retries", 1), ("task-timeout", 300)):
        plan.add_argument("--" + name, type=int, default=default)
    plan.add_argument("--source", default="local")
    plan.add_argument("--framework-source", default="local")
    plan.add_argument("--task-file", default="")
    plan.add_argument("--adapter", default="")
    plan.add_argument("--workdir", type=Path, default=Path("."))
    plan.add_argument("--output", type=Path, required=True)
    worker = sub.add_parser("worker")
    worker.add_argument("--manifest", type=Path, required=True)
    worker.add_argument("--index", type=int, default=0)
    worker.add_argument("--baseline", action="store_true")
    worker.add_argument("--output", type=Path, required=True)
    worker.add_argument("--resume", type=Path)
    worker.add_argument("--workdir", type=Path, default=Path("."))
    worker.add_argument("--fail-task", default="")
    worker.add_argument("--fail-once", action="store_true")
    aggregate = sub.add_parser("aggregate")
    aggregate.add_argument("--manifest", type=Path, required=True)
    aggregate.add_argument("--inputs", type=Path, required=True)
    aggregate.add_argument("--output", type=Path, required=True)
    aggregate.add_argument("--no-baseline", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "plan":
        tasks = read_json(within(args.workdir, args.task_file)) if args.task_file else None
        manifest = build_manifest(workers=args.workers, processes=args.processes, count=args.tasks,
                                  cells=args.cells, steps=args.steps, retries=args.retries,
                                  task_timeout=args.task_timeout, source=args.source,
                                  framework_source=args.framework_source, tasks=tasks,
                                  adapter=args.adapter, workdir=args.workdir)
        atomic_json(args.output / "manifest.json", manifest)
        print(json.dumps({"worker": list(range(args.workers))}, separators=(",", ":")))
        return 0
    manifest = read_json(args.manifest)
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    if args.command == "worker":
        summary = run_worker(manifest, index=args.index, output=args.output, baseline=args.baseline,
                             resume=args.resume, workdir=args.workdir, fail_task=args.fail_task,
                             fail_once=args.fail_once, run_id=run_id,
                             run_attempt=int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")))
        print(json.dumps(summary, indent=2))
        return 0 if summary["status"] == "complete" else 1
    try:
        report = reduce_results(manifest, args.inputs, require_baseline=not args.no_baseline, run_id=run_id)
    except (ValueError, KeyError, TypeError, OSError) as error:
        report = {"schema": SCHEMA, "status": "failed", "error": str(error)}
    atomic_json(args.output / "report.json", report)
    (args.output / "report.md").write_text(markdown(report))
    print(markdown(report))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f"HEXADECARUNNER: {error}", file=sys.stderr)
        sys.exit(2)
