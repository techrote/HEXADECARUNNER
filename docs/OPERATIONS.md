# Operations runbook — dispatch, recovery and evidence

**Navigation:** [Documentation index](INDEX.md) · [README](../README.md) · [Reuse contract](REUSE.md) · [Architecture](ARCHITECTURE.md) · [Qualification](QUALIFICATION.md)

This is the operator-facing runbook for the **current artifact-mediated workflow**, not a promise of real-time inter-worker compute. The [architecture](ARCHITECTURE.md) defines protocol and metrics; [qualification](QUALIFICATION.md) records which hosted behaviors have actually passed.

## Run the reference benchmark

In `techrote/HEXADECARUNNER`, open **Actions → Benchmark → Run workflow**. Defaults are **4 workers, 128 total tasks, 48×48 grid, 4,000 steps/task, baseline enabled, 30-minute per-compute-job timeout, resume run 0**. The selectable counts are **4, 8, 16, 32**; higher counts must be requested deliberately. The user-facing Benchmark uses the [reusable distributed workflow](../.github/workflows/distributed.yml) and keeps a unique `bench` artifact namespace.

| Knob | Guidance |
|---|---|
| Workers | Start with four. Account-wide concurrency may queue additional requested workers, including 32 in waves. |
| Processes | Bound by requested 1–4, observed CPU affinity and per-worker task count; do not assume four actual CPUs everywhere. |
| Tasks | Fixed **total** workload. Use at least `4 × workers` when expecting four local processes per node, preferably more. |
| Steps | Increase enough for useful compute-to-setup ratio; keep fixed across worker-count comparisons. |
| Baseline | Retain it for exact correctness and fresh speedup eligibility. It precedes fan-out and does not consume a fifth concurrent slot. |
| Timeout | Per baseline/worker job, 1–360 minutes; actual runner/platform limits still apply. |
| Resume run | Leave `0` for fresh measurement; nonzero restores eligible published checkpoints and suppresses fresh speedup. |

**Ordinary CI:** [`ci.yml`](../.github/workflows/ci.yml) runs tests/actionlint plus a **four-worker smoke** with 64 tasks, 48×48, 1,000 steps. The smoke establishes protocol and hosted correctness, not stable large-workload scaling.

## Benchmark protocol

Run only the worker counts explicitly approved for the experiment. Hold framework SHA, caller source SHA, task set, work per task, local process budget and baseline setting constant across configurations. Preserve full raw reports for *every* attempt, including errors, queue skew, retries and checkpoint state. Repeated **fresh** independent trials are required before suggesting a scaling trend; no default workflow loops through 4/8/16/32.

Provisioning/queueing and action-mediated artifact exchange can exceed the compute span for small workloads. A requested 32-worker matrix need not yield 32 simultaneously executing runners. These are **separate Actions jobs**, coordinated by a plan barrier and reducer barrier, not communicating live.

## Read results and final telemetry

Inspect the Actions run's `plan`, `baseline`, every `worker-N` and `aggregate` conclusions. Download `bench-report-aATTEMPT` for the manual benchmark or `smoke-report-aATTEMPT` for CI. Inspect `manifest.json` (source/config identity), `report.json` (validation/eligibility), `report.md` (readable reducer summary), `telemetry.json` and `telemetry.md` (GitHub scheduling, job/step and artifact durations).

| Report field | Interpretation |
|---|---|
| `status` / `baseline_equal` | Reducer correctness and exact identical-workload baseline equality; successful status also requires all worker coverage. |
| `result_sha256` / `experiment_id` | Canonical output digest and content-bound experiment identity; neither is a cryptographic worker attestation. |
| `workers_detail[].observed_cpus / processes` | Observed per-job CPU and process budgets, not assumed machine type. |
| `execution_span_seconds` | Latest worker compute finish minus earliest compute start, including start skew; cross-host wall clocks assumed synchronized. |
| `peak_observed_worker_overlap` | Overlapping compute intervals, **not** simultaneous full CPU saturation. |
| `performance_eligible / performance_exclusions` | Authoritative gate on whether a *fresh compute-only* comparison may be shown. |
| `worker_execution_minutes` | Summed compute wall time / 60; **not** GitHub billed minutes or total pipeline wall time. |

The aggregator's first telemetry snapshot is **incomplete by construction**: its own final duration/upload cannot be included while running. Once the hosted run has fully completed, collect final telemetry with a **read-only** token available in the `GH_TOKEN` environment:

```sh
python scripts/telemetry.py \
  --repo techrote/HEXADECARUNNER \
  --run-id RUN_ID \
  --namespace bench \
  --output work/final-telemetry
```

Use `--namespace smoke` for this repository's CI, or the consumer's `name` for cross-repo calls; change `--repo` to the **caller** repository. The collector writes `telemetry.json` and `telemetry.md`. Do not pass tokens on the command line. The collector may explicitly report unavailable telemetry; never fabricate queue or cost numbers. See [architecture — measurement definitions](ARCHITECTURE.md#measurement-definitions).

## Recover work after failure

**Automatic rerun:** Use GitHub Actions' rerun-failed-jobs facility. The workflow attempts to restore matching published checkpoint receipts from earlier attempts of the same run. If there are no published receipts, it computes again. Latest worker attempt wins during reduction, and actual upstream job failure cannot be hidden by older success.

**Explicit restore:** Use `resume_run_id` pointing to a run in the **same repository** and namespace with the same pinned framework revision, caller source SHA, worker count, task set, adapter identity and configuration. This is correctness-oriented continuation, not a fresh-performance experiment. An explicit request with no compatible published data must fail. A corrupt/foreign/conflicting receipt must fail closed.

**Durability boundary:** receipts are atomically written on local disk and normally uploaded at job end, even after ordinary task errors. There is **no periodic upload** and no guarantee that cancelled, timed-out or lost VMs will publish their data. Use more, shorter independent tasks for long runs; preserve important artifacts before the default **7-day** expiry. See [architecture — worker lifecycle and recovery](ARCHITECTURE.md#worker-lifecycle-and-recovery).

## Diagnose a failed run

| Symptom | Inspect | Required response |
|---|---|---|
| Plan rejects task file / adapter | `plan` step logs and [task contract](REUSE.md#task-and-adapter-contract) | Fix malformed JSON, IDs, invalid path or absent adapter; create a new committed revision. |
| Worker error or timeout | `worker-N` compute logs, `worker.json`, receipt/failure list | Correct environment, task code, threads, timeout or input. Do not reduce with missing tasks. |
| Adapter produces different results from baseline | `report.json` rejection, task hashes, stdout protocol | Reproduce determinism violation; establish a reviewed canonicalization, never waive equality. |
| Missing artifacts or incomplete coverage | Uploaded role/index/attempt artifacts, upstream conclusions | Check upload/retention and newest attempt. Failed worker means failed experiment. |
| Explicit resume fails | Prior run ID, namespace, SHA/config/worker count, published receipts | Select compatible source and artifacts; do not force incompatible resume. |
| Fresh speedup not reported | `performance_exclusions` | Document retry, restore, rerun, omitted baseline or process mismatch; report correctness only. |
| Slow total workflow despite a fast compute span | Queue/setup/transfer durations and peak overlap | Report end-to-end overhead; do not promise linear speedup or extra CPU concurrency. |

## Performance claim discipline

Only claim **hosted correctness** after a real hosted run and exact baseline equality. Only claim a **fresh compute-span observation** when `performance_eligible=true`, with its source SHA, task/work parameters, processes, worker count, peak overlap and exclusions. Execution-span speedup excludes checkout/setup/artifact actions; artifact-action timing includes action startup and compression, not just transfer bandwidth. GitHub API job-minutes are observed time, not billing; queue timestamps may be unavailable.

**Do not infer** physical 8/16/32 qualification from the logical topology suite, a single four-worker result, or a short smoke run. Existing accepted physical evidence is enumerated in [qualification](QUALIFICATION.md#accepted-final-head-and-main-qualification). Do not treat an eligible single trial as statistically stable scaling.

## Operating boundaries

Only GitHub-hosted Ubuntu CPU Actions jobs, read-only permissions and commit-pinned actions. There is no external scheduler, GPU, inbound port, VPN, shared filesystem, live network transport or compute service. The workflow is intended for development/test/benchmark work under GitHub's applicable terms and limits, not for always-on compute or quota circumvention. Adapter code is trusted consumer code; dataset provisioning, native dependencies, disk usage and large binary transfer are outside the default workflow.

**Platform references:** [Actions runner limits](https://docs.github.com/en/actions/reference/limits) · [Re-run workflows and jobs](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs) · [Artifacts](https://docs.github.com/en/actions/tutorials/store-and-share-data).
