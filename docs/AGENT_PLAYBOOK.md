# Agent playbook — adopt HEXADECARUNNER in another repository

**Navigation:** [Documentation index](INDEX.md) · [Agent contract](../AGENTS.md) · [Reuse interface](REUSE.md) · [Operations](OPERATIONS.md) · [Architecture](ARCHITECTURE.md)

**Goal:** convert a consuming repository's eligible finite CPU workload into a reproducible, fail-closed GitHub Actions scatter/gather job **without modifying HEXADECARUNNER runtime by default**. This is a procedure for agents, not an autonomous authorization to consume a large runner allocation.

## Applicability gate

Admit the workload only if each task can execute independently with a stable ID, fixed inputs and a deterministic JSON result, and its expected compute cost is large enough to amortize separate runner checkout, queue and artifact steps. Good fits: test shards with stable outcomes, fixed-seed simulations, deterministic renders returning hashes, parameter sweeps. Poor fits: one synchronized world simulation, shared-memory solver, live MPI collective, stateful transactions or tasks requiring communication among workers.

Before editing, inspect the consumer's task runner, dependency/bootstrap mechanism, CI policy, task count, thread pools, side effects, timeout and result stability. Establish that GitHub-hosted `ubuntu-24.04` with Python 3.12 can run the task; the reusable workflow does not install project dependencies or stage large datasets for you. If native tooling or packages are needed, plan and review explicit consumer integration; do not claim it works until the actual job confirms it.

**STOP** if the workload cannot be made idempotent or exact-result-comparable under the [reuse protocol](REUSE.md#task-and-adapter-contract). Propose a separate architecture for high-frequency cross-node exchange rather than forcing it into scatter/gather.

## Adoption steps

1. **Record an integration plan.** Name the consumer repository/branch, reviewed HEXADECARUNNER commit, fixed total task set, 4 initial workers, requested 1–4 local processes, desired baseline and evidence gate. Keep 8/16/32 an explicit follow-on choice, not an automatic matrix.
2. **Author task data.** Check in e.g. `ci/distributed-tasks.json`. Use 1–4096 unique stable task IDs with exactly `id` and object `payload`. Keep total tasks fixed across worker-count comparisons; use at least one task per worker, preferably at least `4 × workers` when using four processes per worker. See the [canonical task list](../examples/tasks.json).
3. **Author the adapter.** Check in e.g. `ci/distributed-adapter.py`, based on the [example](../examples/adapter.py). Read one JSON task from stdin; write exactly one stable JSON result (≤1 MiB) to stdout, diagnostics to stderr; exit nonzero on failure. Bound child process/thread use, avoid shared mutable build output and irreversible side effects. The reducer compares exact JSON results, not a numeric tolerance.
4. **Add a narrowly scoped caller workflow.** Copy the [full caller example](REUSE.md#external-repository-caller). Pin `uses: techrote/HEXADECARUNNER/.github/workflows/distributed.yml@<40-char-sha>` and `with.framework_ref` to the **same reviewed exact SHA**. Set `name` uniquely within a workflow run, set `task_file`/`adapter` relative to the consumer checkout, request `baseline: true`, and use read-only permissions. Do not pass `secrets: inherit`.
5. **Rehearse locally before hosting.** Validate task-file syntax, adapter output and deterministic repeatability; exercise the source-bound framework planner and local protocol (see [reuse](REUSE.md#local-rehearsal)). Run the consumer's own unit tests and the framework's tests if making framework changes. Sequential local worker emulation checks *protocol correctness only*, not multi-host execution.
6. **Qualify a single four-worker hosted run.** Confirm `plan`, `baseline`, each expected worker and `aggregate` conclude successfully. Inspect `report.json`, `report.md`, source/framework identities, complete coverage, exact baseline equality and the artifact namespace. Use [operations](OPERATIONS.md#read-results-and-final-telemetry).
7. **Publish reproducible evidence.** Record caller SHA, pinned framework SHA, task count/parameters, observed CPUs and per-worker processes, retry/restore state, manifest ID, result digest, link to Actions run and artifact, and any limitations. Declare correctness separately from performance eligibility.
8. **Only then propose scaling.** Require explicit permission for 8/16/32 workers. Hold workload/config fixed and use repeated fresh runs; never present a logical topology unit test or short smoke run as evidence of multi-node scaling.

## Local rehearsal

From a checkout of the **consumer repository**, with a separate reviewed checkout of HEXADECARUNNER available as `../HEXADECARUNNER`, use an isolated fresh output directory. Replace the SHA and paths to match the proposed caller:

```sh
python ../HEXADECARUNNER/hexrunner.py plan \
  --workers 4 --processes 2 \
  --task-file ci/distributed-tasks.json \
  --adapter ci/distributed-adapter.py \
  --workdir . --source "$(git rev-parse HEAD)" \
  --framework-source FULL_FRAMEWORK_COMMIT_SHA \
  --output work/plan
python ../HEXADECARUNNER/hexrunner.py worker \
  --manifest work/plan/manifest.json --baseline \
  --workdir . --output work/results/baseline
for i in 0 1 2 3; do
  python ../HEXADECARUNNER/hexrunner.py worker \
    --manifest work/plan/manifest.json --index "$i" \
    --workdir . --output "work/results/worker-$i"
done
python ../HEXADECARUNNER/hexrunner.py aggregate \
  --manifest work/plan/manifest.json \
  --inputs work/results --output work/report
```

The `plan` command prints a matrix JSON line in addition to writing the manifest. Use a **fresh output directory** for each rehearsal; the worker rejects pre-existing receipt files. The local sequence is not a hosted distributed measurement, and the local source SHA is a provenance label rather than independent verification of a clean working tree. For real qualification, review and commit the consumer code first.

## Acceptance and reporting

Completion requires an actual consumer-repo PR or commit containing the task JSON, adapter, caller workflow and any dependency setup; reproducible local pass; and (when runtime qualification is in scope) a hosted **four-worker baseline-equal** report. If hosted execution is unavailable, mark the integration as **implemented but not hosted-qualified**.

Before claiming speedup, check `performance_eligible` and `performance_exclusions` in `report.json`, then quantify scheduling/setup/artifact overhead with [operations telemetry](OPERATIONS.md#read-results-and-final-telemetry). Record any suppressed comparison as **correctness-only**, not a performance result. One eligible trial cannot support a stable scaling claim.

## Agent handoff prompt

Copy and fill this prompt when delegating an integration in a **different** repository:

> Integrate the reviewed HEXADECARUNNER artifact-mediated distributed CPU workflow into `TARGET_REPOSITORY`. Read `techrote/HEXADECARUNNER/AGENTS.md`, `docs/INDEX.md`, `docs/AGENT_PLAYBOOK.md` and `docs/REUSE.md` at framework commit `FULL_FRAMEWORK_COMMIT_SHA`. Inspect the target's actual tasks, runtime dependencies, determinism and side effects before editing. Add a checked-in deterministic task list and JSON-stdin/stdout Python adapter, plus a minimal reusable-workflow caller pinned to that same full SHA in `uses` and `framework_ref`. Begin with four workers, baseline enabled, read-only permissions and no inherited secrets. Validate local semantics and hosted upstream jobs, complete coverage and exact baseline equality. Open a focused PR documenting both source SHAs, task and process settings, evidence URLs and failures. Do not launch 8/16/32, modify framework internals, or claim speedup without explicit approval and fresh qualified measurements. Report blockers rather than weakening reducer checks.

## Escalation paths

If the caller needs additional libraries or a native build, document a safe reproducible bootstrap and obtain a separate implementation decision—do not silently modify the pinned upstream reusable workflow. If tasks are nondeterministic, define stable canonicalization (or a separately reviewed reducer design) first; **never hide differences by returning a constant**. If workers fail or restored artifacts disagree, follow the [diagnostic table](OPERATIONS.md#diagnose-a-failed-run) and preserve evidence. If an outcome contradicts existing documentation, check [architecture](ARCHITECTURE.md) and code, then propose a documentation or versioned contract fix.
