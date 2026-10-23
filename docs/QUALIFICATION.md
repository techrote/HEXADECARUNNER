# Qualification record — HEX-001

**Navigation:** [Documentation index](INDEX.md) · [Architecture](ARCHITECTURE.md) · [Operations](OPERATIONS.md) · [Reuse](REUSE.md) · [README](../README.md)

**Evidence status:** the original proof of concept has completed **final-head acceptance and post-merge four-worker hosted qualification**. Earlier provisional qualification notes below are retained as historical context, not current blockers. 8/16/32 are **logical/topology-tested only**; no physical 8/16/32 hosted qualification is claimed.

## Accepted final-head and main qualification

The accepted implementation head was [`9032881e4c9f8c1d62b2faf80c7f94e32743b7f6`](https://github.com/techrote/HEXADECARUNNER/commit/9032881e4c9f8c1d62b2faf80c7f94e32743b7f6), merged through [PR #2](https://github.com/techrote/HEXADECARUNNER/pull/2) to `main` at `32586d4fc3790e5026f3c3187ab36c1f10ca3bba`. [Final acceptance details](https://github.com/techrote/HEXADECARUNNER/pull/2#issuecomment-6351326103) record 27 passing tests, actionlint, byte-for-byte independent downloaded-artifact readback and source/test rerun. This was an implementation self-review plus independent artifact readback, **not** a separate human review.

| Fresh four-worker hosted observation | [Final-head PR CI](https://github.com/techrote/HEXADECARUNNER/actions/runs/39854171311) | [Post-merge main CI](https://github.com/techrote/HEXADECARUNNER/actions/runs/39854645706) |
|---|---:|---:|
| Baseline compute seconds | 13.650 | 14.846 |
| Distributed compute span seconds | 4.154 | 8.203 |
| Peak observed compute overlap | 4 workers | 3 workers |
| **Compute-span speedup only** | **3.286×** | **1.810×** |
| Total tasks, grid, steps | 64; 48×48; 1,000 | 64; 48×48; 1,000 |
| Baseline equality | All 64 exact | All 64 exact |

Each compute runner in these runs observed 4 CPUs and 4 processes. Variation in scheduled overlap matters: these are **small correctness smoke trials**, not end-to-end speedup, heavy-workload scaling, a billing estimate or 8/16/32-host qualification. The first implementation trial below measured 1.638× and must not be discarded.

The [final-head hosted partial rerun](https://github.com/techrote/HEXADECARUNNER/actions/runs/39854171311) restored **all 16** task receipts for worker 0 and recomputed zero; the reducer retained the same canonical digest and properly suppressed performance eligibility. Corrected scheduling telemetry excluded five duplicate carried-forward physical job records. The post-merge main run passed the eight-job workflow, including the four-worker baseline/reducer.

Canonical result SHA-256: `f831021a822ab96a8c9fa0ec326fa9988e625c0d8f96beecff4668b94ffd1c35`.

| Final-head evidence archive | Artifact ID | Verified ZIP SHA-256 |
|---|---:|---|
| `quality-a1` | 12458797817 | `772ef23941371dc48fa512d132dbd46db5cc033835e3df212c574d9ceb5a7f0e` |
| `smoke-report-a1` | 12458168437 | `7612cab77e4355bb6e15acbb98b4658546beda1c30e23a0a7329a6fe592fe608` |
| `smoke-report-a2` | 12458018978 | `9081c462660ef21fed83b4727bc68b87bc1cc3ac2095fa1e553a07076611c8d9` |

Artifact IDs and hashes document the historical readback, **not** permanent availability: artifacts default to seven-day retention. See [operations — result interpretation](OPERATIONS.md#read-results-and-final-telemetry) and [architecture — measurement definitions](ARCHITECTURE.md#measurement-definitions).

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

**Historical pre-acceptance note:** the hardened suite expanded to **27 tests**. The required final hosted checks, independent artifact readback and merge verification were subsequently completed; see [accepted final-head and main qualification](#accepted-final-head-and-main-qualification). The original initial-run success alone was not the acceptance gate.

## Recovery and measurement clarifications

Automatic rerun is best-effort checkpoint reuse: a shard with no published data restarts its work. Explicit `resume_run_id` requires published compatible data and fails when absent. Corrupt, conflicting or foreign data is never silently ignored. The workflow still cannot recover local receipts lost before upload.

Runner-minute telemetry covers the selected workflow namespace (plan, baseline, worker jobs, aggregate), not unrelated caller jobs such as `quality`. It includes failed physical attempts but deduplicates carried-forward records by job name, runner ID and identical start/end timestamps. In-progress aggregation snapshots omit their own eventual completion/upload duration. Recollect after completion for final totals; none of these fields is a billing statement.

## Qualification boundary and next experiments

Only four-worker hosted execution and actual same-run checkpoint restore are accepted here. The logical 1/4/8/16/32 topology suite and selectable 8/16/32 matrix inputs are **not** evidence that physical 8/16/32 launches ran. For future scaling evidence, use the [repeatable benchmark procedure](OPERATIONS.md#benchmark-protocol), the [eligibility rules](ARCHITECTURE.md#measurement-definitions) and the [agent acceptance checklist](AGENT_PLAYBOOK.md#acceptance-and-reporting). New runs must be recorded under their own exact source identities, not silently appended to the 2026-10-22 acceptance.
