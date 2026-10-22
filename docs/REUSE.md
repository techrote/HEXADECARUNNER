# Reusing the workflow

## External repository caller

Commit a task list and adapter to the consuming repository, using the examples as a starting point. Select a reviewed HEXADECARUNNER commit. Replace both `FULL_FRAMEWORK_COMMIT_SHA` occurrences below with that same 40-character SHA; the workflow reference cannot be an expression.

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

Do not add `secrets: inherit`. The caller source is checked out in `workload`; the pinned framework is checked out separately in `framework`. Adapter paths and task-file paths are relative to `workload` and cannot escape it. The adapter's current working directory is the workload checkout. External callers must explicitly supply `framework_ref`; internal repository workflows use their own event SHA by default.

The caller controls the workflow reference and the framework checkout reference. GitHub does not automatically make those two strings equal: review them together and keep them identical. Pinning avoids accidentally mixing workflow code from one release with runner code from another.

## Inputs

| Input | Default | Contract |
|---|---|---|
| `workers` | 4 | 1, 4, 8, 16, or 32 |
| `processes` | 4 | 1..4; bounded by CPU allocation and assigned tasks |
| `tasks` | 128 | Reference workload only; 1..4096 total, at least worker count |
| `cells` | 48 | Reference periodic grid width/height, 4..128 |
| `steps` | 4000 | Reference diffusion iterations, 1..100000 |
| `baseline` | true | Same total task set on one runner before the worker phase |
| `name` | hex | Unique artifact namespace within the caller run; letters/digits/underscore/hyphen, 1..32 chars |
| `framework_ref` | empty | Full framework commit SHA; required outside this repository |
| `task_file` | empty | Optional checked-in JSON list replacing generated tasks |
| `adapter` | empty | Optional checked-in Python task adapter; empty selects the reference kernel |
| `resume_run_id` | 0 | Compatible published checkpoint run in the same caller repository |
| `retries` | 1 | Additional per-task attempts, 0..3 |
| `task_timeout` | 300 | Adapter invocation timeout in seconds, 1..18000; reference kernel uses job timeout |
| `timeout_minutes` | 30 | Per baseline/worker job timeout, 1..360 |

Two workflow calls in one parent run must use different `name` values. Do not use a caller matrix to multiply a 32-worker pool accidentally. This prototype does not stage large external datasets or build native projects automatically; adapters must use available dependencies or manage their own reviewed setup without concurrent build races.

## Task protocol

Input task list:

```json
[
  {"id":"seed-000","payload":{"seed":0,"scenario":"settling"}},
  {"id":"seed-001","payload":{"seed":1,"scenario":"settling"}},
  {"id":"seed-002","payload":{"seed":2,"scenario":"settling"}},
  {"id":"seed-003","payload":{"seed":3,"scenario":"settling"}}
]
```

The adapter receives one entire object on stdin. Return one deterministic JSON result (at most 1 MiB) on stdout. Durations and host metadata should not be part of that result, because exact baseline equality would then fail. The runner records execution durations separately. Log to stderr. A nonzero exit, timeout, invalid JSON or non-finite output is a failed attempt.

For numeric workloads with unavoidable floating-point variation, implement a documented canonicalization or tolerance-aware summary in the adapter. Do not simply discard failures or precision differences until the reducer passes. This first reducer intentionally uses exact result equality.

For compiler/test workloads, return a compact receipt such as passed test IDs, stable output hashes and operation counts. Keep large binary outputs outside the JSON receipt; the current prototype does not provide a general binary-output publication protocol. Native tools may launch their own thread pools: bound their thread count or choose `processes: 1` to avoid oversubscription.

## Recovery and outputs

Re-run failed jobs to reuse compatible published results from prior attempts in the same workflow run. For a different run, use the same source/configuration/namespace with `resume_run_id`. No credentials beyond the caller's read-only GitHub token are needed for same-repository recovery. Artifact expiry, removed artifacts, foreign sources or missing checkpoint publication can make recovery impossible; the workflow must not claim those tasks were preserved.

The workflow returns `report_artifact` and, on successful reduction, `result_sha256`. Download the named artifact for JSON/Markdown reports. Check the Actions job conclusion too: output presence alone is not proof of success. A failed reducer still publishes diagnostic evidence where possible.
