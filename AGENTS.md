# HEXADECARUNNER — agent instructions

**Navigation:** [README](README.md) · [Documentation index](docs/INDEX.md) · [Cross-repo agent playbook](docs/AGENT_PLAYBOOK.md) · [Reuse contract](docs/REUSE.md)

These are **execution instructions**, not a claim that every supported topology has been physically benchmarked. Use them when changing HEXADECARUNNER itself **or** assisting a consuming repository.

## Mission and reading order

1. Read the [documentation index](docs/INDEX.md) and route the question to its **canonical** contract.
2. For adopting another repository, follow the [agent playbook](docs/AGENT_PLAYBOOK.md), then the [caller/task contract](docs/REUSE.md). Do not copy framework internals into the caller by default.
3. For framework code/workflow changes, inspect [architecture](docs/ARCHITECTURE.md), [operations](docs/OPERATIONS.md) and [qualification](docs/QUALIFICATION.md), then the actual `hexrunner.py` and workflow source.
4. Treat checked-in code/workflows, not prose, as authoritative for runtime behavior. Update both tests and docs when behavior changes.

## Non-negotiable guardrails

- **Infrastructure:** GitHub-hosted `ubuntu-24.04` CPU jobs only; no self-hosted runner, physical GPU, VPN, external compute service, live public listener or shared-memory/network cluster claims.
- **Scale:** four workers by default; 8/16/32 only on explicit request. Do not automatically run all sizes, or nest matrices to create unapproved fan-out. Requested jobs may queue under account-wide limits.
- **Security:** immutable full-SHA action pins; `contents: read` and `actions: read` only; no `secrets: inherit`, deployment secrets, persistent checkout credentials or `pull_request_target` execution of untrusted code.
- **Correctness:** preserve manifest identity, task/worker coverage, newest-attempt semantics, exact baseline comparison, and upstream job-conclusion gates. Fail closed on corruption, missing data, mismatched revisions or duplicate receipts.
- **Runtime:** keep framework Python runtime standard-library-only. Adapters are **trusted user code, not sandboxed**. Bound nested native parallelism; use `processes: 1` where appropriate.
- **Recovery:** only successfully **published** compatible checkpoint artifacts survive runner loss; ordinary-failure upload is best effort. Retries are at-least-once; require idempotency.

## Agent execution sequence

**Adoption in another repository:** inspect the workload for independent tasks and deterministic outputs → define immutable task IDs/payloads → implement the consumer's adapter and task JSON → pin **both** framework references to the same reviewed 40-character commit → run local adapter/manifest checks → obtain a hosted four-worker baseline-equal run → inspect reducer report and upstream conclusions → record evidence and caveats. See the [detailed steps and stop conditions](docs/AGENT_PLAYBOOK.md).

**Change to this framework:** establish the exact baseline head → make a focused branch → preserve compatibility or deliberately document a versioned schema change → update unit/failure-path tests, documentation and links → run `python -m unittest discover -s tests -v` and actionlint → obtain hosted CI when behavior changes → publish a reviewable PR with source SHA, test evidence and any remaining unqualified behaviors.

Do not silently normalize, skip, or downgrade incorrect results to turn the reducer green. Do not quietly enable a larger worker pool to solve a failing workload.

## Validation and evidence standard

- Confirm every expected worker and the baseline (if enabled) completed successfully; inspect `report.json`, `report.md` and the correct namespace's uploaded artifacts.
- Identify caller source SHA, framework SHA, manifest/experiment ID, workload parameters, observed CPUs/processes, worker count, task coverage, failures, retries and restores.
- Distinguish **local logical topology tests**, **real hosted worker qualification**, and **fresh performance-eligible experiments**. A rerun, restored receipt, task retry, missing baseline or unequal process count suppresses fresh performance comparisons.
- Distinguish compute-only execution-span speedup from **end-to-end** latency and observed runner-minutes from GitHub billing. Review [measurement definitions](docs/ARCHITECTURE.md#measurement-definitions) and [operational telemetry](docs/OPERATIONS.md#read-results-and-final-telemetry).
- Validate relative Markdown paths and anchors with `python -m unittest discover -s tests -v`; update [index routing](docs/INDEX.md) whenever documents are added or renamed.

## Stop conditions and nonclaims

Stop and report a blocker if task results are nondeterministic without a documented canonicalization policy, if inputs or revisions cannot be reproduced, if any worker/reducer fails, or if evidence is missing. Do **not** claim that 8/16/32 physical hosts are qualified, that a checkpoint survives a killed VM before upload, that data hashes authenticate malicious workers, or that sequential local testing proves speedup.

The source-bound accepted four-worker findings are recorded in [qualification](docs/QUALIFICATION.md), not inferred from the latest successful workflow.
