# Reuse contract — other repositories

**Navigation:** [Documentation index](INDEX.md) · [Agent playbook](AGENT_PLAYBOOK.md) · [Operations](OPERATIONS.md) · [Architecture](ARCHITECTURE.md) · [Examples](../examples/)

This document is the **canonical interface contract** for a consuming repository: the exact reusable-workflow caller, supported inputs and adapter/result protocol. For agent steps and admission gates, see the [playbook](AGENT_PLAYBOOK.md); for recovery and reporting procedures, see [operations](OPERATIONS.md).

## External repository caller

In the **consuming** repository, commit a Python task adapter and task JSON file, then a workflow like the following. Replace **both** `FULL_FRAMEWORK_COMMIT_SHA` occurrences with the **same reviewed 40-character hexadecimal framework commit SHA**. GitHub requires the reusable workflow `uses` reference to be a literal, not a runtime expression.

```yaml
name: Distributed simulation CI
on:
  workflow_dispatch:
permissions:
  contents: read
  actions: read
jobs:
  simulations:
    uses: techrote/HEXADECARUNNER/.github/workflows/distributed.yml@FULL_FRAMEWORK_COMMIT_SHA
    with:
      framework_ref: FULL_FRAMEWORK_COMMIT_SHA
      name: simulation
      workers: 4
      processes: 4
      task_file: ci/distributed-tasks.json
      adapter: ci/distributed-adapter.py
      baseline: true
      retries: 1
      task_timeout: 300
      timeout_minutes: 30
```

The caller source is checked out into `workload/` at the caller's GitHub event SHA; the HEXADECARUNNER code is independently checked out into `framework/` at `framework_ref`. Task and adapter paths are relative to the **workload root** and may not escape it. The adapter runs with the caller checkout as its working directory.

**Do not** omit `framework_ref` in an external repository, use a moving tag/branch for either reference, or add `secrets: inherit`. GitHub does not enforce equality between the two framework references automatically: inspect them together. Two calls in one parent workflow run require **different** `name` values to avoid artifact collisions. Avoid wrapping a 32-worker call in another fan-out matrix.

## Input reference

These values are defined by [`distributed.yml`](../.github/workflows/distributed.yml); the workflow schema and `hexrunner.py` are decisive if an implementation changes.

| Input | Default | Accepted behavior / bounds |
|---|---|---|
| `workers` | 4 | 1, 4, 8, 16, 32 (1 is mainly for internal/local scenarios; manual Benchmark offers 4/8/16/32) |
| `processes` | 4 | 1–4 per compute runner; actual use capped by observed CPUs and assigned tasks |
| `tasks` | 128 | Total tasks for *generated reference workload* only; 1–4096, must be at least worker count |
| `cells` | 48 | Reference diffusion grid side, 4–128 |
| `steps` | 4000 | Reference diffusion iterations per task, 1–100000 |
| `baseline` | true | Execute **the entire identical task set** on one runner before workers |
| `name` | hex | Unique artifact namespace within parent run; 1–32 ASCII letters/digits/_/- |
| `framework_ref` | empty | Full 40-character framework SHA; **mandatory for cross-repo callers** |
| `task_file` | empty | Checked-in JSON task list relative to `workload`; if empty, generate reference tasks |
| `adapter` | empty | Checked-in Python adapter relative to `workload`; if empty, run reference kernel |
| `resume_run_id` | 0 | Nonzero: published compatible checkpoints from another run **in the same caller repository** |
| `retries` | 1 | Additional per-task attempts, 0–3; retries invalidate fresh speedup comparison |
| `task_timeout` | 300 | Adapter task deadline in seconds, 1–18000; reference kernel uses the job timeout |
| `timeout_minutes` | 30 | Baseline/worker job timeout, 1–360 minutes |

When supplying a custom `task_file`, the JSON determines the total task count; `tasks`/`cells`/`steps` only generate the reference set when `task_file` is empty. A custom task list with the built-in reference kernel must still contain the reference payload keys (`seed`, `cells`, `steps`). Do not assume arbitrary JSON works without an adapter.

## Task and adapter contract

A checked-in task list is a JSON **array** of 1–4096 entries; each entry has **exactly** `id` and `payload`. `id` must be unique and valid under the current source's ID validation. `payload` must be a JSON object. Non-finite numbers, duplicate object keys, duplicate IDs and malformed data are rejected. The manifest sorts tasks by ID and assigns positions modulo the worker count; this is deterministic/count-balanced, not runtime-balanced. See the [sample task list](../examples/tasks.json).

For every task, the checked-in Python adapter:

- Reads a **single complete task object** on standard input. The runner invokes it with `sys.executable` directly, not via a shell.
- Emits **one deterministic JSON result**, max 1 MiB, to **stdout** and nothing else there. Diagnostics belong on stderr; exit nonzero on error. Bad JSON, oversized results, timeout or nonzero exit triggers a failed attempt.
- Returns results independent of run time, host identity, paths, timing, process scheduling or nondeterministic iteration order. Baseline and distributed tasks undergo **exact** result equality, not tolerance-based comparison.
- Avoids side effects or makes them independently idempotent: timeout, artifact loss and retry mean *at least once*, not exactly once. Scope temporary/output files by task ID; do not race builds among local processes.
- Explicitly limits native BLAS/compiler/thread pool parallelism or uses `processes: 1` when one task already saturates its worker.

Minimal example, matching [`examples/adapter.py`](../examples/adapter.py) and [`examples/tasks.json`](../examples/tasks.json):

```json
[
  {"id":"case-0","payload":{"samples":[1,2,3]}},
  {"id":"case-1","payload":{"samples":[4,5,6]}},
  {"id":"case-2","payload":{"samples":[7,8,9]}},
  {"id":"case-3","payload":{"samples":[10,11,12]}}
]
```

For floating-point workloads that vary across machines, design a **documented, justified stable representation** inside the adapter (e.g. canonical quantized summaries), prove it is scientifically meaningful and independently test discrepancies. Do not return a constant or suppress genuine numerical failures just to satisfy exact equality. Large binary results need a separately designed publication mechanism; only a compact JSON receipt is supported here.

## Source identity, dependencies and security

The manifest contains the caller source revision, framework revision, adapter path/file SHA-256, task definitions, worker/process configuration, retry/timeout settings and the canonical `experiment_id`. A hash detects mismatched *content*; it does not authenticate untrusted workers or make the adapter a sandbox. Read [architecture — source and manifest identity](ARCHITECTURE.md#source-and-manifest-identity).

Workers use GitHub-hosted `ubuntu-24.04` with Python 3.12, standard actions and no inherited secrets. **The workflow does not build your native project, pip-install arbitrary requirements or stage external data.** If the consumer depends on compiled programs or third-party packages, qualify their presence/setup separately before asserting that this stock caller will succeed. Check [agent applicability](AGENT_PLAYBOOK.md#applicability-gate). Never run unreviewed external pull-request code with privileged tokens.

## Local rehearsal

For agent-operated full local plan → baseline → four workers → reduce commands from a consumer checkout, see [playbook — local rehearsal](AGENT_PLAYBOOK.md#local-rehearsal). To test this repository's bundled adapter directly:

```sh
printf '%s\n' '{"id":"case-0","payload":{"samples":[1,2,3]}}' | python examples/adapter.py
python -m unittest discover -s tests -v
```

Local emulation validates manifest/receipt/reducer protocol, **not** hosted runner overlap or the consumer's dependency environment. A new source commit changes the caller source identity, and a new worker count changes the manifest identity: do not reuse foreign checkpoints across those changes.

## Outputs and recovery

On completion, the reusable workflow exposes:

| Output | Meaning |
|---|---|
| `report_artifact` | Namespace-scoped artifact name `NAME-report-aATTEMPT` containing reducer JSON/Markdown, manifest and scheduling telemetry |
| `result_sha256` | Canonical distributed result digest when reduction passes; **empty on reducer failure** |

Check the Actions **job conclusion** as well as output presence; diagnostic artifacts can be uploaded even on a failing run. Expect `NAME-plan-aATTEMPT`, optional `NAME-baseline-aATTEMPT`, `NAME-worker-INDEX-aATTEMPT`, and `NAME-report-aATTEMPT`. They default to **seven days** retention. See [architecture — reduction and evidence](ARCHITECTURE.md#reduction-and-evidence).

**Automatic rerun:** re-running failed jobs may restore a compatible checkpoint from a previous attempt of the *same workflow run*. A worker with no published checkpoint recomputes its shard. **Explicit `resume_run_id`:** restore from a compatible completed or partial run *within the same repository*; if no published compatible data exists, fail rather than pretend it was restored. Latest attempts and upstream job conclusions are authoritative. An upload after an ordinary task failure is best effort, **not** periodic persistence; killed runners may lose unfinished/unuploaded work. See [operations — recovery](OPERATIONS.md#recover-work-after-failure) and [architecture — worker lifecycle](ARCHITECTURE.md#worker-lifecycle-and-recovery).

Fresh speedup is suppressed after a retry, checkpoint reuse, rerun, no baseline or unequal per-runner process counts. Correctness can still pass. See [operations — performance claim discipline](OPERATIONS.md#performance-claim-discipline).
