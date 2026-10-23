# HEXADECARUNNER

**Reusable, artifact-mediated CPU scatter/gather on GitHub Actions.** Four GitHub-hosted Ubuntu worker jobs by default; 8, 16 and 32 workers are explicit opt-ins. Each worker can run up to four local Python processes, capped by the CPUs actually observed and the tasks assigned.

This is **not** an MPI/Ray cluster, shared-memory pool, dynamic work-stealing service, or a way around account concurrency limits. It is for **independent, deterministic, idempotent** test cases, simulations, render fixtures and parameter sweeps that can exchange results at a final reduction barrier.

## Start here

| Your task | Authoritative document |
|---|---|
| **Agent adapting another repository** | [Agent playbook](docs/AGENT_PLAYBOOK.md) → [reusable workflow contract](docs/REUSE.md) |
| **Human integrating another repository** | [Reuse guide and caller YAML](docs/REUSE.md) |
| **Run a benchmark, resume or diagnose a failure** | [Operations runbook](docs/OPERATIONS.md) |
| **Understand sharding, identity, recovery, reduction or metrics** | [Architecture](docs/ARCHITECTURE.md) |
| **Verify what has actually been qualified** | [Qualification record](docs/QUALIFICATION.md) |
| **Agent modifying this framework** | [Repository agent instructions](AGENTS.md) |
| **Find the right RAG/reference section** | [Documentation index](docs/INDEX.md) |

The [documentation index](docs/INDEX.md) names the canonical owner of each contract. Follow its cross-references rather than inferring capabilities from a benchmark screenshot.

## Execution model

```text
plan ──> optional same-workload single-runner baseline
     ──> worker 0 ──┐
          worker 1 ──┼──> strict validation / reduction / report artifact
          worker 2 ──┤
          worker 3 ──┘
```

The baseline runs **before**, not alongside, the worker matrix. A deterministic manifest binds caller source SHA, framework SHA, task definitions, adapter digest, worker/process budget and retry configuration. The reducer requires complete, disjoint coverage and, when enabled, **exact per-task baseline equality**. Worker failure or missing evidence never becomes partial success.

Checkpoint receipts are written atomically on a worker and uploaded at the end of its job, including on ordinary failures where possible. **They are not durable until artifact upload succeeds.** Forced VM termination can lose local work; retries may re-execute tasks, so side-effecting adapters are unsafe unless explicitly idempotent.

## Try the reference workload

In this repository, open **Actions → Benchmark → Run workflow**. Start with 4 workers and the defaults: 128 *total* tasks, 48×48 grid, 4,000 steps per task, baseline enabled and a 30-minute compute-job timeout. Select 8/16/32 only deliberately. The ordinary pull-request/main CI is a smaller four-worker smoke test, **not** a scaling benchmark.

To run the local protocol tests (Python 3.11+; standard library only):

```sh
python -m unittest discover -s tests -v
```

Local topology tests emulate the protocol sequentially. They are **not evidence of real multinode speedup**. For experiment setup, result interpretation and final telemetry, follow the [operations runbook](docs/OPERATIONS.md).

## Adopt in another repository

1. Use the [agent playbook](docs/AGENT_PLAYBOOK.md) to confirm that the workload is embarrassingly parallel and can return deterministic JSON results.
2. Add a checked-in [task list](examples/tasks.json) and [Python adapter](examples/adapter.py) to the **consumer** repository.
3. Use the [caller YAML](docs/REUSE.md#external-repository-caller) with one reviewed 40-character HEXADECARUNNER commit SHA in **both** the workflow `uses` reference and the `framework_ref` input.
4. Qualify a four-worker baseline-equal run in the consumer repository before making performance claims or opting into larger pools.

The reusable workflow supplies Python 3.12 and an Ubuntu runner; it does **not** install your project dependencies or automatically stage large data. No inherited secrets, elevated write permissions, self-hosted runners, GPUs or live coordinator are needed.

**Qualification status:** the original framework passed 27 tests and physical four-worker hosted execution, including actual published-checkpoint restore. 8/16/32 are logically tested but **not physically qualified**. See the [evidence and source-bound qualifications](docs/QUALIFICATION.md). Compute-only execution-span speedups exclude queueing, setup, artifact transfer and aggregation; they are not end-to-end or billing measurements.

## External platform references

[Reusable workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows) · [Workflow artifacts](https://docs.github.com/en/actions/tutorials/store-and-share-data) · [GitHub-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners) · [Actions limits](https://docs.github.com/en/actions/reference/limits)
