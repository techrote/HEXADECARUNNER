# HEXADECARUNNER

**Reusable, artifact-mediated distributed compute for GitHub Actions.** Four compute workers by default, selectable **8, 16 or 32**. Each worker uses up to four Python processes, limited by its observed CPU allocation and task count.

A single-runner baseline executes the **same total workload with the same per-runner process budget** before the worker phase. A strict reducer checks complete coverage and exact baseline equality, then publishes machine-readable and human-readable evidence.

This is **scatter/gather**, not a live MPI/Ray cluster, shared memory, or a concurrency-limit bypass. Independent tests, simulation seeds, render fixtures and parameter sweeps fit the model. One simulation requiring frequent cross-node synchronization does not.

## Run it

Open **Actions → Benchmark → Run workflow**. Start with four workers and the defaults. The choices are 4, 8, 16 and 32; larger pools are never launched automatically. Ordinary pull-request and main-branch CI runs a smaller four-worker smoke qualification.

| Setting | Manual benchmark default | Meaning |
|---|---:|---|
| Workers | 4 | Independent GitHub-hosted Ubuntu jobs |
| Processes per worker | 4 | Upper bound; actual allocation is recorded |
| Tasks | 128 | Fixed total workload, not tasks per worker |
| Grid | 48 × 48 | Integer reference diffusion simulation |
| Steps | 4,000 | Iterations per task |
| Baseline | Enabled | Identical work on one runner before fan-out |
| Job timeout | 30 minutes | Configurable up to the hosted-job limit |
| Resume run | 0 | Fresh trial; nonzero selects compatible published checkpoints |

Keep tasks and steps fixed when comparing 4/8/16/32 workers. Use at least `4 × workers` tasks to fill four processes on every node, preferably several times more. Increase steps until computation dominates provisioning and artifact overhead; do not interpret the smoke test as a large-workload scaling result.

The pipeline is:

```text
plan ──> one-runner baseline ──> worker 0 ──┐
                              worker 1 ──┤
                              worker 2 ──┼──> validate / reduce / evidence
                              worker 3 ──┘
```

The baseline is sequential, so it does not occupy a fifth concurrent compute slot. Planning and aggregation use additional short-lived jobs at different stages. Other repositories on the account still compete for concurrency. A requested 32-worker pool can run in waves on an account with a lower simultaneous-job allowance.

## Evidence and correctness

Every run publishes a manifest, per-task receipts, worker summaries and a report artifact. The reducer rejects missing workers/tasks, unexpected files, duplicates, conflicting checkpoints, wrong source/config identities, corrupt results and disagreement with the baseline. A failed worker cannot quietly become partial success.

The JSON and Actions summary report observed CPUs and process counts, execution span, peak observed compute overlap, baseline equality, result SHA-256, and execution minutes. Separate GitHub API telemetry reports job runtime, available queue times, preparation time and artifact-action durations.

**Execution speedup excludes checkout/setup/artifact steps.** Artifact timings include action startup and compression, not just network. Cross-node compute span assumes synchronized runner clocks. Runner-minutes are observed runtime, not an invoice. The aggregation snapshot cannot include its own final upload; run the telemetry collector again after completion for final pipeline totals.

Any restored checkpoint, task retry, missing baseline or unequal process budget suppresses the fresh-performance comparison. Correctness can still pass. One run is not a statistically established performance result.

## Use a real workload

Supply a checked-in JSON task list and Python adapter. An example is in [`examples/`](examples/). Each adapter invocation receives one task object on stdin and returns exactly one JSON result on stdout. Send diagnostic messages to stderr and use a nonzero exit status for failure. Tasks should be deterministic and idempotent; retries are at-least-once execution, not exactly-once side effects.

The adapter can invoke your repository's existing test or simulation executable with an argument list. The prototype provides Python 3.12 and the standard Ubuntu runner image; it does not automatically build your project, install third-party dependencies, or distribute large datasets. Keep setup explicit in your adapter/project integration, and avoid racing shared build outputs between local task processes. Use one process for internally parallel native workloads unless their thread count is explicitly bounded.

Cross-repository callers use `.github/workflows/distributed.yml` with a **full reviewed framework commit SHA** in both the workflow reference and `framework_ref`. The separate `workload` checkout is the caller's source revision, not this repository. See [`docs/REUSE.md`](docs/REUSE.md) for the complete caller and input contract. No inherited secrets or write permissions are required.

## Checkpoint recovery

A successful task is written atomically to disk immediately. An `always()` artifact step publishes completed tasks even after an ordinary task failure. Retries are bounded (one retry by default). Re-running failed jobs automatically downloads compatible prior attempts; an explicit `resume_run_id` can restore another run in the same repository and artifact namespace.

Restore requires identical source revisions, framework revision, task definitions and configuration. Changing worker count invalidates the manifest intentionally. The newest worker attempt is authoritative: an older success cannot hide a newer failure. Conflicting or corrupt receipts fail closed rather than being silently skipped.

**A killed VM or job timeout can lose work that never reached artifact storage.** Upload-on-failure is best effort, not live durable checkpointing. Seven-day artifact retention is the default. For very long workloads, use smaller independently checkpointable tasks and retain evidence explicitly before expiry.

## Local development

Python 3.11 or newer; the runtime and tests use only the standard library.

```sh
python -m unittest discover -s tests -v
python hexrunner.py plan --workers 4 --processes 2 --tasks 32 --cells 16 --steps 20 --output work/plan
python hexrunner.py worker --manifest work/plan/manifest.json --baseline --output work/results/baseline
for worker in 0 1 2 3; do
  python hexrunner.py worker --manifest work/plan/manifest.json --index "$worker" --output "work/results/worker-$worker"
done
python hexrunner.py aggregate --manifest work/plan/manifest.json --inputs work/results --output work/report
```

This local loop is a **sequential protocol test**, not a multi-machine performance measurement. Output directories must be fresh; use a different output directory and `--resume old/checkpoints` for recovery. Unit tests exercise all 1/4/8/16/32 logical topologies, deliberate failures, retries, resume, adapter timeouts and validation rejection paths.

To collect final job telemetry from a completed hosted run:

```sh
# GH_TOKEN should be a read-only token in your environment, not a command-line argument.
python scripts/telemetry.py --repo techrote/HEXADECARUNNER --run-id RUN_ID --namespace bench --output work/final-telemetry
```

Use namespace `smoke` for CI or `bench` for the manual Benchmark workflow.

## Design and operating boundaries

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for data contracts, measurement definitions and known limitations. All third-party actions are commit-pinned; compute jobs use read-only permissions and non-persistent checkout credentials. No self-hosted runner, GPU, VPN, coordinator server, inbound port or external compute account is used.

This repository is for development-related tests and benchmarks within GitHub's applicable terms and usage limits, not an always-on compute service. Public-repository runner capacity and account limits are documented by GitHub and can change; the report records observed CPU availability rather than assuming a four-core machine.

### Primary references

- [Reusable workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows)
- [Workflow artifacts](https://docs.github.com/en/actions/tutorials/store-and-share-data)
- [Hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
- [Actions limits](https://docs.github.com/en/actions/reference/limits)
- [Re-running jobs](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs)
