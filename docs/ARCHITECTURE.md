# Architecture and acceptance contract

## Scope

The first implementation is bulk-synchronous scatter/gather: a planning barrier, optional baseline, independent worker phase, and reduction barrier. The artifact service is the exchange medium. No worker needs another worker's IP address. There is no task-stealing queue, live inter-worker socket protocol, MPI collective, shared filesystem or memory pooling.

The worker matrix supports 1/4/8/16/32 jobs internally; the user-facing benchmark offers 4/8/16/32. A baseline uses the entire manifest, not a smaller sample. The sum of all distributed shards is exactly the baseline's task set.

## Source and manifest identity

`schema=1` manifests contain caller source SHA, framework SHA, adapter path/hash, ordered task list, worker/process budget, retry policy and adapter timeout. `experiment_id` is SHA-256 over canonical JSON of all other fields. No timestamp or workflow run ID enters this content identity, permitting compatible cross-run restore. Workflow run and attempt IDs remain in worker evidence for provenance.

Tasks contain exactly `id` and `payload`. IDs are unique restricted strings, payloads are JSON objects, and non-finite/duplicate-key JSON is rejected. The planner caps task counts and validates reference workload parameters. Sort tasks by ID, then assign position modulo worker count. This is deterministic and count-balanced, not predicted-runtime-balanced.

Task receipts bind experiment identity, task ID, input digest and result digest. The hash is an integrity/content identifier, **not a signature or a proof against a malicious worker**. Baseline equality independently checks distributed output consistency, not the scientific validity of the workload implementation. The reference kernel has a separately calculated small-grid test vector.

## Worker lifecycle and recovery

A worker validates the manifest and adapter file, loads only compatible checkpoints, copies accepted receipts into a fresh output directory, and submits unfinished tasks to a bounded process pool. Successful receipts use temporary-file/fsync/atomic-rename writes. The worker continues collecting other tasks after an ordinary task failure, records failure receipts in `worker.json`, and returns nonzero if any task remains failed. GitHub matrix `fail-fast` is disabled so sibling evidence is retained.

Custom adapters run without shell interpolation in a separate process group. A task timeout kills that process group on Linux. Results are JSON with a 1 MiB size limit; adapter output is redirected to temporary files rather than held unboundedly in RAM. This is **not a sandbox or a disk-output quota**: adapters are trusted repository code and must not generate unlimited output. The bounded reference kernel relies on the configured whole-job timeout rather than a per-task subprocess timeout.

Completed local receipts are published at the end of the compute step, including ordinary failures. Checkpoint publication is not periodic. Forced termination, runner loss, cancellation or artifact-service failure can prevent upload. Only already-published receipts survive those events. Retrying may re-execute a task whose side effects occurred before its receipt was published; use idempotent adapters.

Artifacts are unique per namespace, role/index and GitHub run attempt. Restores download their own role/index, not the baseline results into every worker. Aggregation chooses the highest attempt for each expected worker; duplicate same-attempt summaries are rejected. A new incomplete attempt overrides an old complete one. Failed workers are not hidden by selecting whichever attempt looks successful.

## Reduction and evidence

Every expected worker must have a complete summary and exactly its assigned receipt filenames. Worker identities, task identities, output digests, task counts, process metadata and timing consistency are checked. Distributed task IDs must be disjoint and complete. If a baseline is enabled, its canonical per-task results must exactly match the distributed results.

`report.json` and `report.md` are written on both normal validation success and rejection. The job exits nonzero on rejection; `always()` publishes diagnostics. A failure before the reducer can start may leave only upstream checkpoints or normal job logs. There is no success fallback for missing artifacts.

`quality-aN` contains the exact source snapshot and test output used by the quality job. `NAME-plan-aN` contains the manifest. `NAME-baseline-aN` and `NAME-worker-I-aN` contain receipts and worker summaries. `NAME-report-aN` contains the manifest, reducer report and scheduling telemetry. Artifact retention defaults to seven days, so preserve important qualification records separately.

## Measurement definitions

| Field | Definition / caveat |
|---|---|
| Worker wall seconds | Monotonic elapsed time of local execution, checkpoint copying and process-pool work; excludes checkout/setup/download/upload |
| Distributed execution span | Latest worker compute finish minus earliest worker compute start, using cross-host wall-clock anchors; includes late-start skew after the earliest worker begins |
| Execution-span speedup | Single-runner wall seconds divided by distributed execution span; not end-to-end pipeline speedup |
| Parallel efficiency | Execution-span speedup divided by requested workers, not by observed peak overlap |
| Peak observed worker overlap | Maximum overlapping worker compute intervals; does not claim simultaneous CPU utilization of every process |
| Execution minutes | Sum of worker compute wall seconds / 60; excludes job provisioning and artifact actions |
| Job runner minutes | Sum of completed job durations from GitHub's API, including failed attempts; not billed cost |
| Rounded minute estimate | Sum of ceiling(job seconds / 60); explicitly not a bill or currency estimate |
| Queue seconds | Job creation-to-start when exposed by the API; otherwise null, never invented |
| Setup-to-compute seconds | Job start to the `Compute` step, including checkout/setup/download |
| Artifact-action seconds | Step duration including action initialization, compression and transport |

The current aggregation job is still running during its own telemetry snapshot. Its final duration and final upload are absent; `all_selected_jobs_completed=false` makes this explicit. The same read-only collector can be run against the completed run to obtain final totals. The API's timestamps are coarse compared with task timers. Report raw JSON and avoid treating subsecond differences as significant.

A fresh comparison is suppressed when receipts were restored, tasks retried, baseline was omitted, or per-runner process counts differ. Resumed runs can still establish correctness. For performance decisions, use independent fresh runs at the same commit and parameters, retain every result, and compare repeated observations including setup/transfer/queue overhead. Hardware placement and account-wide scheduling are not controlled by this prototype.

## Security and operational limits

Only standard `ubuntu-24.04` GitHub-hosted runners are requested. Action references are immutable SHA pins. Permissions are `contents: read` and `actions: read`; checkout credentials are not persisted. The token is exposed only to the artifact action or read-only telemetry step, not explicitly to custom adapters. Do not use `pull_request_target` for running untrusted source. Never inherit deployment or cloud secrets into the compute workflow.

Custom adapters run trusted checked-in code, not a restricted sandbox. The caller must review source revisions, task payloads and adapter behavior. Output hashes do not authenticate provenance against an adversarial workflow author. Artifact retention/storage, platform job limits, service availability and account-wide concurrency remain applicable. The workflow has bounded configurable job timeouts and bounded retries, with no recursion or automatic fan-out beyond the chosen worker count.

Large synchronized worlds, shared-memory workloads, GPUs and very large intermediate data are outside this proof of concept. Add live networking only after a separate workload-specific design and measured justification. Dynamic task scheduling and periodic durable checkpoint publication are useful future extensions, not capabilities claimed here.
