# Documentation index and retrieval map

**Navigation:** [README](../README.md) · [Agent instructions](../AGENTS.md) · [Agent playbook](AGENT_PLAYBOOK.md)

This is the **entrypoint for document retrieval (including RAG)**. Read the smallest authoritative section for the question; use links to expand to adjacent contracts. This repository does **not** contain or claim a vector-indexing service. Each document owns a different layer of guidance to avoid conflicting duplicated instructions.

## Choose the canonical source

| Query / decision | Read first | Then consult |
|---|---|---|
| Can this workload use artifact-mediated distributed jobs? | [Playbook — applicability gate](AGENT_PLAYBOOK.md#applicability-gate) | [Architecture — scope](ARCHITECTURE.md#scope) |
| What exactly should a coding agent implement in another repo? | [Playbook — adoption steps](AGENT_PLAYBOOK.md#adoption-steps) | [Reuse — caller contract](REUSE.md#external-repository-caller) |
| What YAML inputs, task JSON, adapter stdout and outputs are supported? | [Reuse](REUSE.md) | [Reference examples](../examples/tasks.json), [adapter](../examples/adapter.py) |
| How do sharding, identities, checkpoint selection and fail-closed reduction work? | [Architecture](ARCHITECTURE.md) | [Recovery operations](OPERATIONS.md#recover-work-after-failure) |
| How to launch, measure, rerun, or troubleshoot a hosted run? | [Operations](OPERATIONS.md) | [Architecture — measurement definitions](ARCHITECTURE.md#measurement-definitions) |
| Which configurations actually passed independent/hosted checks? | [Qualification](QUALIFICATION.md) | [Operations — claims](OPERATIONS.md#performance-claim-discipline) |
| What constraints apply to modifications to this framework? | [Repository agent instructions](../AGENTS.md) | [Existing CI](../.github/workflows/ci.yml) |

## Document ownership and boundaries

- **[AGENTS.md](../AGENTS.md)** — normative rules for a repository-editing agent, including safety gates and required review evidence.
- **[AGENT_PLAYBOOK.md](AGENT_PLAYBOOK.md)** — operational adoption decision tree and agent handoff for *other repositories*; no competing input-spec table.
- **[REUSE.md](REUSE.md)** — authoritative *consumer-facing interface*: full caller workflow example, accepted inputs, task/result protocol and workflow outputs.
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — authoritative *implementation invariants*: manifest, deterministic assignment, reducer, checkpoint validation, security boundaries and metric definitions.
- **[OPERATIONS.md](OPERATIONS.md)** — authoritative *operator procedures*: dispatch, benchmarking, diagnostics, restore, telemetry and limits.
- **[QUALIFICATION.md](QUALIFICATION.md)** — immutable-context *historical evidence*: observed hosted runs and explicit scope of acceptance, **not** a statement that every selectable worker count was run.
- **[README.md](../README.md)** — short human discovery page and a route to the documents above.

## Shared vocabulary

| Term | Meaning | Contract |
|---|---|---|
| **Caller/workload** | Repository whose source revision, task list and adapter are executed | [Reuse](REUSE.md#external-repository-caller) |
| **Framework** | Pinned HEXADECARUNNER workflow and `hexrunner.py` source | [Architecture](ARCHITECTURE.md#source-and-manifest-identity) |
| **Worker** | One GitHub-hosted compute job, with 1–4 bounded local processes | [Operations](OPERATIONS.md#run-the-reference-benchmark) |
| **Manifest / experiment ID** | Canonical identity binding source, configuration and tasks | [Architecture](ARCHITECTURE.md#source-and-manifest-identity) |
| **Baseline** | Single runner executing the **full identical task set** before fan-out | [Architecture](ARCHITECTURE.md#scope) |
| **Checkpoint** | Published task receipts eligible for identity-checked restoration; not a live durable write | [Operations](OPERATIONS.md#recover-work-after-failure) |
| **Fresh-performance eligible** | Run without restore, retry or rerun, with baseline and equal process budgets | [Architecture](ARCHITECTURE.md#measurement-definitions) |

## Retrieval and editing conventions

Keep a single top-level heading per document. Place a **Navigation** line below it linking here and relevant neighbors; use descriptive `##` headings that GitHub turns into stable anchors. Reference files with **relative Markdown links**, and prefer deep links to exact headings when explaining a policy. Never copy an evidence figure without its source, qualification scope and exclusions.

When changing the interface, update [reuse](REUSE.md), the [playbook](AGENT_PLAYBOOK.md) and tests. When changing execution semantics, update [architecture](ARCHITECTURE.md), [operations](OPERATIONS.md), [qualification](QUALIFICATION.md) **only if new evidence is actually collected**, and the affected regression tests. The [documentation link test](../tests/test_doc_links.py) checks local relative links and heading anchors.

**Further reading:** [GitHub reusable workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows) · [Actions limits](https://docs.github.com/en/actions/reference/limits).
