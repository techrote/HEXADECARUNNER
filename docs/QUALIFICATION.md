# Qualification record — HEX-001

## Initial hosted qualification, 22 October 2026

PR #2 / issue #1. Initial implementation head `cbfafb658b04ddd2f86b24bba7826b612ae2fdc9`; tested PR merge/source SHA `e5be7c49e863689ac18ca69b79f868abc66539c0`.

Run: https://github.com/techrote/HEXADECARUNNER/actions/runs/39852249389

The initial run completed successfully: 21 unit/integration tests, actionlint, planning, the baseline, four independent GitHub-hosted worker jobs, strict reduction and evidence upload. Downloaded source and report archives were independently SHA-256-verified; the source tests were also rerun locally. The logical 1/4/8/16/32 topologies were tested locally, **not** as 8/16/32 physical hosted nodes.

| Initial smoke measurement | Observed |
|---|---:|
| Total tasks | 64 |
| Reference grid / steps | 48 x 48 / 1,000 |
| Workers | 4 |
| Observed CPUs / processes on each compute runner | 4 / 4 |
| Single-runner baseline compute time | 7.412 s |
| Four-worker compute span | 4.524 s |
| Peak observed compute overlap | 4 workers |
| Compute-only speedup | 1.638x |
| Baseline equality | All 64 results equal |

This is a small functional smoke run, not a heavy-workload scaling benchmark. The speedup excludes setup, transfers and other job overhead. Do not extrapolate to 8/16/32 workers or assume linear scaling.

Canonical result digest: `f831021a822ab96a8c9fa0ec326fa9988e625c0d8f96beecff4668b94ffd1c35`.

## Actual hosted checkpoint restore

Worker 0 was explicitly rerun in attempt 2 of the same run. It restored all 16 task receipts and computed zero tasks; reduction again passed with the same canonical result digest. The report correctly suppressed the fresh-performance comparison. This is hosted artifact restore evidence, not just a local mock.

## Artifact locators and verified archive hashes

| Artifact | ID | ZIP SHA-256 |
|---|---|---|
| quality-a1 | 12458600130 | `1d400cac92bd21309f062de1e7d2e8ee1ebfe5a3317213d04e9560c2e251b81d` |
| smoke-report-a1 | 12458205943 | `2954e42b7d1c693b6b0b2f5ec8e23ae7f0d7adadb875cbee4a843044527a0040` |
| smoke-report-a2 | 12457229506 | `457e0d4e8449b200b976bc8df86e552a4606be5602b6f5e731af5b20b5eec025` |

Artifacts have seven-day retention. Preserve ZIPs externally before expiry when durable raw evidence is needed. This committed record preserves source/run identity, measured findings, artifact locators and hashes; it does not claim the artifact service stores them forever.

## Review findings addressed in the hardening revision

- An upstream worker can fail before publishing a new summary. The reducer now also gates on the actual upstream worker/baseline job conclusions, so old successful artifacts cannot produce a green report for that case.
- Duplicate attempt detection now includes older attempts even when a newer attempt was encountered first.
- Restore validates summary identity even when no successful task receipt exists. Explicit empty restore is rejected. An automatic job rerun with no published checkpoints can recompute from scratch, with no fresh-performance claim.
- All reruns, even without cache reuse, are excluded from fresh single-attempt speedup comparisons.
- Process pools explicitly use forkserver on supported platforms, otherwise spawn, avoiding inherited threaded-parent state.
- The real partial rerun exposed copied GitHub job records: unchanged jobs appeared with new IDs/attempts but the same physical runner and original start/end. Telemetry now counts each identical physical execution once, preserving the earliest queue timestamp. The original attempt-2 telemetry totals are superseded by this correction; its compute correctness/restore evidence remains valid.
- Current official Node 24 action releases are pinned by full commit SHA; artifact download digest mismatch remains a hard error.

The hardened suite contains **27 tests**, all passing locally. Final hosted checks against the hardened PR head, independent evidence readback, and merge verification must be recorded in PR #2 before acceptance; initial-run success alone is not the final-head acceptance gate.

## Recovery and measurement clarifications

Automatic rerun is best-effort checkpoint reuse: a shard with no published data restarts its work. Explicit `resume_run_id` requires published compatible data and fails when absent. Corrupt, conflicting or foreign data is never silently ignored. The workflow still cannot recover local receipts lost before upload.

Runner-minute telemetry covers the selected workflow namespace (plan, baseline, worker jobs, aggregate), not unrelated caller jobs such as `quality`. It includes failed physical attempts but deduplicates carried-forward records by job name, runner ID and identical start/end timestamps. In-progress aggregation snapshots omit their own eventual completion/upload duration. Recollect after completion for final totals; none of these fields is a billing statement.
