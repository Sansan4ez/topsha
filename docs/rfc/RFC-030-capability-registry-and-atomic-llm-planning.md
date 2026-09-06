RFC-030 Capability Registry and Atomic LLM Planning
===================================================

Status
------

Proposed

Date
----

2026-08-31

Revised: 2026-09-07 after architecture review.

Related RFCs
------------

- RFC-003 defined the structured and hybrid corporate DB search surface.
- RFC-016 separated retrieval completion from LLM answer finalization.
- RFC-018 introduced a unified catalog for table, script, and document execution paths.
- RFC-021 diagnosed excessive hard-coded orchestration and proposed an LLM-led runtime.
- RFC-025 made route cards and typed arguments the center of retrieval.
- RFC-027 introduced business families and leaf routes.
- RFC-028 made the catalog declarative and tried to collapse routing into one decision path.
- RFC-029 split route choice and argument construction into two LLM calls.

Decision summary
----------------

Replace the current production retrieval sequence

```text
Python intent ordering
  -> LLM route choice (Call A)
  -> LLM arguments for the already chosen route (Call B)
  -> route-specific execution
  -> evidence classification
  -> route fallback graph
  -> optional ReAct recovery
  -> answer finalizer
```

with a smaller capability-oriented sequence:

```text
hard security/access gate
  -> one atomic LLM plan: outcome OR capability + typed arguments
  -> one allowlisted deterministic executor/workflow
  -> one normalized result contract
  -> no-tools LLM answer finalizer when needed
```

The planner sees the capability description and its argument contract together. It chooses the capability and fills its arguments in the same structured-output operation. A capability represents a real business operation over a table, search domain, document domain, or reviewed multi-table workflow. It is not a storage-independent intent label and it is not one node in a fallback graph.

Known multi-table questions are implemented as registered deterministic workflows. Corporate retrieval never falls back into the general ReAct loop. General workspace/tool tasks may still use the ReAct agent, but only after the top-level planner explicitly delegates to that separate capability class.

Context and motivation
----------------------

The current system has strong data and a strong model:

- normalized Postgres tables for lamps, documents, codes, categories, mountings, spheres, portfolio, and knowledge chunks;
- structured filters for the normalized lamp fields;
- exact lookups and stage-3 optimized executors;
- hybrid FTS, trigram, and semantic search over `corp.corp_search_docs`;
- compact canonical enums for series, spheres, mounting types, document types, and other stable domains;
- `gpt-5.6-terra` in the verified production path.

Despite this, routing remains the main source of regressions. The 2026-08-31 production verification exposed two representative failures:

1. `LAD LED R500 2Ex` with `flux_lm_min=11540` selected `corp_db.catalog_lookup` / `lamp_exact` instead of `corp_db.lamp_filters`.
2. simple company-fact requests intermittently selected or fell back to `corp_kb.series_description`, causing website, foundation year, address, or contact facts to disappear.

These failures are not evidence that the model cannot understand the questions. They show that the runtime gives different decision stages different fragments of the information and then lets several layers reinterpret the result.

The current implementation is substantial for a 22-visible-route catalog:

- `core/agent.py`: 4,603 lines;
- `core/documents/routing.py`: 2,390 lines;
- `core/documents/route_schema.py`: 1,087 lines;
- `core/documents/routing_policy.py`: 393 lines;
- route YAML and JSON Schema files: about 1,816 lines.

The active selector payload measured on the rebuilt stack is also revealing:

- full internal payload: about 149 KB of JSON;
- compact Call-A payload: about 7.1 KB;
- Call-A messages: about 7.9 KB.

The Call-A prompt is compact because it intentionally excludes argument schemas. That optimization also removes information needed to distinguish routes whose main difference is their argument shape.

Problem statement
-----------------

The current architecture has the wrong unit of routing and too many owners of semantic interpretation.

### 1. A leaf route is often smaller than the real capability

Several routes are alternative modes over the same data domain rather than distinct user capabilities.

Examples:

- `catalog_lookup`, `lamp_filters`, and parts of `category_lamps` all operate on the lamp catalog;
- `company_common` and `series_description` query the same `knowledge_route_id`, source file, and hybrid-search backend;
- document subtype routes all execute the same lamp-document index with a different `document_type`;
- SKU lookup directions execute one code-index capability.

Splitting one data capability into neighboring leaf routes forces the model to classify a storage mode before it can supply the values that reveal which mode is appropriate.

### 2. Route choice and arguments are artificially separated

RFC-029 Call A sees only:

- `route_id`;
- `family_id`;
- title;
- `when_to_use`.

Call B sees the chosen route's argument schema, but cannot change the route.

For the R500 2Ex incident, the most important evidence is structural:

- the user supplied a canonical `series`;
- the user supplied a numeric lower bound `flux_lm_min`;
- `lamp_filters` accepts both fields;
- `catalog_lookup` requires an exact `name`.

Call A does not see that contrast. Once it picks `catalog_lookup`, Call B cannot correct the choice. A stronger model cannot recover information that the contract deliberately withholds from the decision where it matters.

### 3. Deterministic pre-ordering remains a hidden router

Even when all visible routes fit in the selector budget, `build_route_selector_payload()` computes an `intent_family` through Python keyword logic and orders all cards by that inferred intent. The 2026-08-31 verification commit changed catalog-order presentation to `all_visible_ranked_by_intent` to reduce one regression.

This is a useful local mitigation, but it proves that route order is behaviorally significant. The LLM is not choosing from a neutral registry; it receives a list already shaped by a second classifier.

### 4. The same question is interpreted repeatedly

Company questions currently pass through overlapping mechanisms:

- Python company-fact subtype detection;
- Python facet detection;
- Call-A route selection;
- Call-B query/facet construction;
- a special company query expansion in `_route_execution_args()`;
- company payload relevance helpers;
- generic evidence classification;
- fallback from `company_common` to `series_description` and back.

The current comments correctly describe several of these as narrow exceptions. The accumulated result is still a multi-owner decision system.

### 5. Fallback graphs compensate for over-split capabilities

`company_common` and `series_description` are mutual fallbacks even though they use the same source and executor. Document subtype routes fall back to their broad sibling. Catalog and code routes need cross-family declarations to recover from selection errors.

A fallback edge is appropriate when an external dependency fails over to a genuinely different source. It is not the right way to select another mode of the same table operation.

### 6. Evidence policy is a second semantic router

After the planner has chosen and executed a route, runtime code decides whether the result is `sufficient`, `weak`, `intermediate`, `empty`, or `error`. Route-specific branches can then launch controlled fallbacks or reopen the main agent loop.

This means a successful typed executor is not authoritative about whether it answered its own contract. The orchestration layer interprets business meaning again.

### 7. The retrieval selector is mandatory for non-retrieval messages

The current catalog has no first-class outcomes for:

- small talk;
- questions about the assistant itself;
- out-of-scope questions;
- blocked requests;
- approved workspace/tool tasks.

Consequently, a request such as `Как дела?` still receives a corporate route catalog and must choose one of the database routes. On the measured stack its first candidates begin with application recommendation and catalog lookup. This is a category error, not a route-ranking problem.

### 8. The ReAct loop remains an implicit recovery system

The system prompt says the primary route has already run, then lets the main agent choose from a routing shortlist if bounded fallbacks did not produce sufficient evidence. Guardrails are needed to stop it from browsing raw files, repeating authoritative KB calls, or leaving the selected source.

This is the behavior RFC-021 and RFC-028 intended to remove. The general agent loop should not be a retrieval fallback engine.

Root cause
----------

The architectural diagnosis is **semantic authority fragmentation**, rather than evidence of insufficient model intelligence:

- one layer classifies intent;
- another chooses a route without seeing its full shape;
- another fills arguments but cannot revise the route;
- another rewrites arguments;
- another judges evidence;
- another follows fallback edges;
- another agent may try additional tools;
- a finalizer writes the answer.

Each layer is locally reasonable. Together they create information loss, duplicated interpretation, and nondeterministic seams.

The second root cause is **modeling storage modes as separate semantic routes**. A user does not distinguish `lamp_exact` from `lamp_filters`; the user asks the catalog capability for a lamp or lamps under constraints. Exact, filtered, and hybrid access are execution modes of that capability.

Atomic planning removes an information-loss boundary between capability selection and argument construction. It does not by itself prove retrieval relevance, completeness, or factual answer accuracy. Those require explicit input, execution, evidence, and answer contracts and independent evaluation.

Goals
-----

- Make one component authoritative for semantic planning.
- Let the planner see capability descriptions and typed arguments together.
- Align capabilities with real table/search/workflow boundaries.
- Reduce the visible corporate capability set from many overlapping leaf routes to a smaller set of distinct business operations.
- Keep structured filters, enums, hybrid search, optimized SQL, and read-only security boundaries.
- Represent small talk, out-of-scope requests, blocked requests, clarification, and approved workspace-agent delegation as first-class outcomes.
- Keep multi-table logic in reviewed backend workflows, not in free-form LLM tool loops.
- Make an executor authoritative for execution status and observable evidence metadata, without treating non-empty retrieval as proof of a complete answer.
- Preserve all explicit user constraints; distinguish exact matches, approximate candidates, partial evidence, and unknown coverage.
- Prevent corporate retrieval from falling into the general ReAct loop.
- Keep final user wording natural and evidence-grounded through a narrow no-tools finalizer call.
- Make new capabilities easy to add through one registry row/spec, one schema, one executor, and tests.
- Net-delete routing-specific Python branches and state.

Non-goals for v1
----------------

- Generating SQL with an LLM.
- Giving the planner arbitrary script paths, tool names, URLs, or table names.
- Removing deterministic access, security, permission, schema, or output validation.
- Removing the general ReAct agent for approved workspace operations.
- Supporting arbitrary unbounded multi-capability plans in the first release.
- Replacing the existing Postgres schema or hybrid-search implementation.
- Migrating all executors in one flag-day change.
- Weakening current golden facts, links, or filter-argument expectations to hide regressions.

Design principles
-----------------

### Capability, not route

A capability is a stable, allowlisted business operation with:

- a clear user-facing purpose;
- one typed input schema;
- one registered executor or workflow;
- declared data sources/table scopes;
- one normalized result contract.

A capability may choose exact, structured, or hybrid access internally. Those are not separate top-level routing decisions unless they expose materially different user semantics. Strategy selection changes the access method, not the user's constraints.

Consolidation requires a shared user operation, compatible input semantics, evidence/coverage rules, and no-result behavior. Shared tables, source files, or executors alone are insufficient. A `domain` argument is still a semantic choice: moving route IDs into an enum only helps when it removes duplicated behavior, not when it hides the old router inside one handler.

### One atomic semantic decision

The planner chooses the capability and fills its arguments in the same structured-output operation. It must see the fields and compact enums that determine fit.

### Deterministic execution after planning

After a plan validates, runtime does not reinterpret the user's meaning. It executes the named allowlisted handler with validated arguments.

### Backend workflows own multi-table behavior

A stable multi-table task gets a named workflow capability. The workflow performs joins and bounded subqueries itself. The LLM supplies parameters, not orchestration steps.

### Hard security stays outside the LLM

Access control, prompt-injection detection, blocked command patterns, permissions, path restrictions, DB read-only enforcement, and output sanitization run before or around planning. The LLM may classify benign out-of-scope requests, but it is not the security boundary.

### No hidden fallback router

An executor may use deterministic recovery inside its own capability, such as normalized exact match followed by bounded hybrid match. Runtime does not traverse a graph of unrelated capabilities after execution.

### No-tools finalization

The answer finalizer receives only an immutable execution envelope, normalized capability result, and concise answer policy. The envelope contains the current user request, validated canonical arguments, and resolved dialog references. It has no tools and cannot reopen retrieval. Corporate factual claims must be supported by returned evidence, not model memory.

Target high-level behavior
--------------------------

### Step 0: deterministic ingress policy

Before any LLM call:

1. enforce access mode and per-session tool permissions;
2. detect blocked/prompt-injection patterns;
3. handle explicit bot/admin commands;
4. reject known destructive or secret-exfiltration requests;
5. normalize transport wrappers without rewriting business meaning.

A hard-blocked request returns the configured blocked response and records a security event. It never reaches the planner or DB.

### Step 1: atomic planner

The planner receives:

- current user message;
- a bounded recent-dialog context for follow-ups, including the last validated plan and stable entity IDs from its result where available;
- a compact capability registry;
- each capability's generated selector-visible typed contract and compact enums;
- the allowed non-retrieval outcomes.

It returns exactly one discriminated action:

```json
{
  "action": "execute_capability",
  "capability_id": "catalog_lamps.search",
  "arguments": {
    "series": "LAD LED R500 2Ex",
    "flux_lm_min": 11540
  }
}
```

or, for example:

```json
{"action": "smalltalk"}
```

```json
{"action": "out_of_scope", "topic": "weather"}
```

```json
{
  "action": "clarify",
  "question": "Уточните, вам нужны проекты для РЖД или категории светильников для РЖД?"
}
```

```json
{
  "action": "delegate_workspace_agent",
  "task_summary": "Inspect the user's repository status"
}
```

The planner cannot return SQL, shell, file paths, executor names, evidence overrides, or arbitrary scripts.

The current message overrides earlier constraints; inheritance is allowed only for explicit conversational references such as "из них". The planner emits the complete effective arguments, not a patch requiring a second semantic merge. Unresolved references require clarification. Dialog context is scoped to the session/user and bounded by configured turn and size limits; a topic change must not silently inherit the previous product or sphere.

`delegate_workspace_agent` is the sole workspace entry action, not an alternative spelling of `execute_capability`. Its registered permission profile excludes corporate DB/search tools and corporate corpus access, including through shell/filesystem/network paths. Session permissions remain an upper bound. Corporate knowledge requests, including requests to use shell to read the corpus, cannot be fulfilled through this delegation. A mistaken initial delegation must not become an alternate corporate retrieval path.

### Step 2: schema validation and canonicalization

Runtime:

- verifies that `capability_id` is active and allowed for the session;
- rejects unknown fields and attempts to override locked scope/security arguments;
- resolves declared canonical aliases and enums, applies declared defaults and locked arguments, then validates the complete effective arguments;
- validates both JSON Schema and declared cross-field invariants, including range ordering and compatible field combinations;
- permits at most one schema-local repair call for malformed output or invalid arguments, with the same capability after it is validly selected; unresolved business ambiguity returns clarification, not invented values;
- returns a bounded planning error if repair fails; no executor or general agent is invoked.

Defaults must not invent business constraints. Every explicit constraint remains mandatory unless the user explicitly replaces it in the current turn. Unsupported or contradictory combinations require clarification or a typed validation failure; silently ignoring a field is prohibited.

Canonicalization may normalize an explicit alias such as `R500 2Ex` to `LAD LED R500 2Ex`. It must not infer a different business capability.

### Step 3: deterministic capability execution

The registered executor runs once. It may contain bounded deterministic substeps within its contract.

Examples:

- catalog search: exact match, structured filter query, or bounded hybrid retrieval depending on validated arguments;
- knowledge search: source-scoped hybrid search using the original query and selected domain/facets;
- document lookup: one bounded batch query for the requested names and document type;
- recommendation workflow: sphere/category resolution, lamp ranking, and portfolio enrichment across reviewed tables.

### Step 4: normalized result contract

Every capability returns a schema-validated envelope with capability-specific typed `data`. The following illustrative catalog result distinguishes execution from coverage and links every fact to an entity and evidence source:

```json
{
  "status": "success",
  "capability_id": "catalog_lamps.search",
  "coverage": "complete",
  "coverage_basis": "Exhaustive scoped filter query; one matching row, no truncation",
  "match_kind": "exact",
  "data": [{"entity_id": "lamp:example", "series": "LAD LED R500 2Ex", "flux_lm": 12000}],
  "facts": [{"entity_id": "lamp:example", "field": "flux_lm", "value": 12000, "source_ids": ["source:1"]}],
  "sources": [{"source_id": "source:1", "entity_id": "lamp:example", "title": "Catalog record"}],
  "links": [],
  "missing_items": [],
  "limitations": [],
  "clarification": null,
  "diagnostics": {
    "execution_strategy": "structured",
    "row_count": 1,
    "requested_constraints": {"series": "LAD LED R500 2Ex", "flux_lm_min": 11540},
    "applied_constraints": {"series": "LAD LED R500 2Ex", "flux_lm_min": 11540}
  }
}
```

Allowed statuses are:

- `success` — the executor completed its declared operation and returned data/evidence; this is not a guarantee that the full user question is answered;
- `empty` — the operation returned no matches within its declared source scope and search strategy; approximate search must not interpret this as proof that the information does not exist;
- `needs_clarification` — the capability is correct, but a required business value is ambiguous or absent;
- `error` — execution failed.

The executor owns this status. The agent layer does not run a second route-specific relevance classifier.

Evidence coverage is separate:

- `complete` — all contract-defined requested items are covered, with a declared basis such as an exhaustive scoped lookup or a fully resolved bounded batch;
- `partial` — some requested items are covered and identifiable items are missing or failed;
- `unknown` — completeness cannot be established, the default for free-text top-k retrieval.

`coverage` describes the declared operation, not an assertion that every relevant fact in the world was retrieved. `missing_items` is populated only when requested items are identifiable; an empty list with `unknown` coverage does not prove completeness. Per-item outcomes distinguish missing data from dependency errors in document batches and workflows. `limitations` records truncation, source scope, and incomplete workflow stages.

`match_kind` is `exact`, `approximate`, `mixed`, or `not_applicable`. Approximate entity candidates are separate from confirmed matches in typed `data`; they must never be presented as exact product facts for the requested entity.

Facts reference stable entity and source IDs. Search excerpts carry source IDs and source text; they are evidence candidates, not automatically verified answers. Links reference their source/entity IDs. Runtime validates reference integrity and allowlisted output fields, not business relevance. Diagnostics and internal table/path identifiers are excluded from the finalizer-visible projection.

For company website/year/address requests, a result containing only a website does not authorize invented year/address facts. A deterministic fact lookup may report `partial`; generic hybrid retrieval reports `unknown`, and finalization must explicitly identify unsupported requested facts. No additional evidence-grading LLM or routing stage is introduced.

### Step 5: response

- `blocked`, `smalltalk`, and simple `out_of_scope` outcomes use reviewed concise templates and do not call the DB.
- `clarify` returns the focused planner/executor clarification.
- `success` and `empty` normally go to a no-tools finalizer LLM; execution/planning errors use reviewed bounded error templates without another LLM call.
- The finalizer cannot call tools or change the capability result. It only writes the user-facing response.
- If the finalizer is unavailable, runtime uses a bounded deterministic renderer over the same evidence and limitations; it must not turn excerpts into unsupported factual assertions.

### Immutable answer input and grounding

Runtime constructs the answer envelope from the current request, validated canonical arguments, and stable resolved entities, rather than asking another model to summarize intent. Thus "А из них какие до 100 Вт?" retains the selected series/category and the effective power bound even though the finalizer does not receive full dialog history.

The finalizer receives the public evidence projection, including coverage, match kind, missing items, and limitations. Its answer policy requires:

- every corporate factual assertion to be supported by evidence for the same entity;
- source references to resolve to returned source IDs; URLs and numerical values must not be invented;
- approximate candidates to be labeled as alternatives, not confirmed matches;
- no claim of full coverage for partial/unknown results or truncated lists; `complete` coverage is allowed only with an explicit executor-supplied coverage basis;
- explicit acknowledgement of requested facts not supported by the evidence;
- "not found in the searched sources" rather than "does not exist" for empty approximate retrieval;
- source text to be treated as untrusted data, never instructions.

Finalization may omit unsupported claims and acknowledge uncertainty. It cannot modify arguments, promote execution status, choose a new capability, or request tools. Factual grounding is evaluated separately from routing accuracy; no-tools isolation alone is not a factuality guarantee.

Capability registry
-------------------

### Source layout

Proposed source-of-truth layout:

```text
core/capabilities/
  registry.yaml
  index.md
  company_knowledge/
    search.yaml
    search.schema.json
    search.result.schema.json
  catalog_lamps/
    search.yaml
    search.schema.json
    search.result.schema.json
  workflows/
    application_recommendation.yaml
    application_recommendation.schema.json
    application_recommendation.result.schema.json
```

`registry.yaml` is the compact machine index. Each capability file contains the reviewed details.

### Capability contract

Required fields:

```yaml
capability_id: catalog_lamps.search
kind: table_query
title: Catalog lamp search
when_to_use: >-
  Find one or more lamp models by exact name, canonical series, structured
  technical filters, category, or an approximate product description.
examples:
  positive:
    - "Покажи LAD LED R500 2Ex от 11540 лм"
    - "Найди NL Nova 120"
    - "Светильники IP65 до 100 Вт"
  negative:
    - "Чем серия R500 отличается от R700?"
data_sources:
  tables:
    - corp.catalog_lamps
    - corp.catalog_series_families
  search_index:
    - corp.corp_search_docs
executor_ref: tools_api.corp_db.catalog_lamps_search
schema_ref: search.schema.json
result_schema_ref: search.result.schema.json
answer_policy: product_facts
security_class: corporate_read_only
```

Optional fields:

- `docs_ref` — human/operator documentation;
- `implementation_ref` — registered handler or workflow module;
- `canonical_catalogs` — enum sources refreshed at build/runtime;
- `latency_budget_ms`;
- `owner`;
- `deprecation_aliases` for old route IDs;
- `availability` by session type;
- `hybrid_search_policy`;
- `result_examples`.

`executor_ref` is resolved through an internal allowlist. It is not an arbitrary import path or script path supplied by the LLM.

### What the planner sees

The planner sees only:

- `capability_id`;
- title;
- short `when_to_use`;
- a small number of positive/negative examples;
- a generated typed argument contract preserving required fields, enums, bounds, field dependencies, and mutual exclusions;
- compact enums that materially affect choice.

It does not see:

- SQL;
- filesystem paths;
- implementation code;
- fallback graphs;
- observability labels;
- retry internals;
- raw table credentials;
- result-ranking internals.

The full input schema is the single source of truth. Planner contracts are generated from it; only non-semantic documentation may be shortened. Cross-field invariants not expressible in the provider's schema subset are declared once alongside the schema, included in planner instructions, and enforced by deterministic validation. Hand-maintained compact signatures that omit decision-relevant constraints are prohibited.

For providers with reliable function calling, corporate capabilities and non-retrieval actions are exposed as mutually exclusive tools, with parallel calls disabled. Otherwise runtime compiles one discriminated-union structured-output contract. Runtime accepts exactly one action and rejects zero/multiple actions; no tools execute before validation. The pinned provider/model must pass integration tests for its actual supported schema subset, enum handling, required/nullable fields, and one-action enforcement. If the complete semantic contract exceeds the budget, revise the capability design or budget explicitly rather than silently truncating it.

Initial capability map
----------------------

The first implementation should deliberately consolidate current routes. The exact final names are subject to implementation review, but the target shape is:

| Capability | Primary data | Replaces or absorbs |
|---|---|---|
| `company_knowledge.search` | `knowledge_chunks`, `corp_search_docs` | `company_common`, `series_description`, `lighting_norms`, `luxnet` as one source-scoped search capability with a compact `domain` enum |
| `catalog_lamps.search` | `catalog_lamps`, `categories`, `catalog_series_families`, hybrid index | exact catalog lookup, lamp filters, category lamp listing, representative examples as modes/fields of one catalog capability where semantics overlap |
| `catalog_documents.lookup` | `catalog_lamp_documents`, `catalog_lamps` | broad and subtype document routes using `names[]` and optional `document_type` |
| `catalog_codes.lookup` | `etm_oracl_catalog_sku`, `catalog_lamps` | forward and reverse SKU/ETM/ORACL/article routes |
| `mountings.lookup` | `mounting_types`, `category_mountings` | available mounting options and named compatibility checks using optional typed fields |
| `sphere_categories.lookup` | `spheres`, `sphere_curated_categories`, `categories` | curated category-by-sphere lookup; diagnostics-only full mapping remains hidden from planner |
| `portfolio.search` | `portfolio`, `spheres`, hybrid index | named object and sphere portfolio lookup, distinguished by arguments rather than neighboring routes |
| `application_recommendation.run` | reviewed multi-table workflow | current recommendation script over spheres, curated categories, lamps, and portfolio |
| `document_corpus.search` | concrete indexed document domains | explicit search inside known documents; not a generic corporate fallback |
| `delegate_workspace_agent` (non-retrieval action) | session-permitted non-corporate tools | sole explicit entry into the existing ReAct agent for repository/sandbox work, with a corporate-access-denying permission profile |

This map is a consolidation hypothesis, not a target count to optimize at the expense of semantics. Validate shared operation/input/evidence/no-result contracts before merging, especially for company facts, norms, and Luxnet. A `domain` enum must select a reviewed source scope under one shared contract, not dispatch to hidden route-specific fallback trees. Measure executor strategies, special cases, and state as well as visible capability count.

### Example: catalog capability

A single catalog capability can use a schema such as:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "query": {"type": "string", "maxLength": 500},
    "name": {"type": "string", "maxLength": 240},
    "series": {"type": "string", "enum": ["LAD LED R500", "LAD LED R500 2Ex", "NL Nova"]},
    "category": {"type": "string", "maxLength": 160},
    "ip": {"type": "string", "maxLength": 8},
    "power_w_min": {"type": "integer", "minimum": 1, "maximum": 2000},
    "power_w_max": {"type": "integer", "minimum": 1, "maximum": 2000},
    "flux_lm_min": {"type": "integer", "minimum": 1, "maximum": 500000},
    "flux_lm_max": {"type": "integer", "minimum": 1, "maximum": 500000},
    "examples_only": {"type": "boolean"},
    "limit": {"type": "integer", "minimum": 1, "maximum": 10}
  },
  "anyOf": [
    {"required": ["query"]}, {"required": ["name"]},
    {"required": ["series"]}, {"required": ["category"]},
    {"required": ["ip"]}, {"required": ["power_w_min"]},
    {"required": ["power_w_max"]}, {"required": ["flux_lm_min"]},
    {"required": ["flux_lm_max"]}
  ]
}
```

This is an illustrative subset, not the production filter inventory. The production schema preserves every supported normalized filter, rejects blank selectors, and declares these additional invariants:

- each numeric minimum must be no greater than its maximum;
- `examples_only=true` requires `category` and is incompatible with exact `name`;
- every supplied exact field and structured constraint is combined with AND semantics;
- `query` supplies approximate matching/ranking only; it never overrides exact fields or numeric bounds;
- unsupported residual requirements expressed in `query` require clarification rather than being silently ignored.

The backend selects execution strategy deterministically, without weakening these invariants:

| Effective arguments | Strategy and semantics |
|---|---|
| Exact `name`, no other constraints | Exact entity lookup; a missing entity is not replaced by a similar one |
| `name` plus filters | Resolve the exact entity and test all filters; mismatch returns no exact match |
| Structured fields, optionally with `query` | Restrict candidates by all fields, then rank within that set using `query` if present |
| Approximate `query` only | Bounded hybrid candidate search, labeled approximate |
| Category plus `examples_only=true` | Bounded showcase query preserving all supplied filters and reporting its sample limit |

Explicit constraints are never dropped or widened in v1. In particular, adapters must disable the current `_lamp_filters()` power-widening/category-dropping retries rather than wrapping their result as an exact success. An exact-name miss may return clearly separated approximate suggestions only where the capability contract explicitly supports them; suggestions cannot change `empty` exact-match semantics or acquire facts belonging to the requested name. Constraint-relaxation policies are deferred beyond v1.

For the R500 2Ex incident, there is no competition between `catalog_lookup` and `lamp_filters`. The planner chooses `catalog_lamps.search` and supplies `series` plus `flux_lm_min`; the executor naturally uses the structured-filter path.

### Example: company knowledge capability

`company_knowledge.search` uses one source-scoped hybrid capability with arguments such as:

- `domain`: `company_common|lighting_norms|luxnet`;
- `query`: the user's natural question or a concise LLM-produced retrieval query;
- `facets`: compact optional enum list;
- `series`: optional bounded array of canonical series values, allowing comparisons without discarding one side of the request.

`series_description` may merge with company knowledge when it shares the search and evidence contract, not merely because both use the same source file and backend. Series becomes an argument/facet. Domain/facet selection must be tested as semantic argument accuracy, even after the old route IDs disappear. If norms or Luxnet require materially different input, evidence, or no-result behavior, keep a distinct capability rather than conceal that difference behind `domain`.

If natural conversational wording performs poorly in hybrid search, fix search normalization, indexing, or ranking in the executor. Do not introduce another Python router-side query rewrite for individual fact subtypes.

Multi-table and complex questions
---------------------------------

### Known repeated complex task

Create one workflow capability.

Example:

```text
application_recommendation.run
  -> resolve sphere/application profile
  -> fetch curated categories
  -> expand executable categories
  -> rank catalog lamps
  -> fetch bounded portfolio evidence
  -> return one normalized result
```

The planner only supplies typed parameters such as `application_key`, `context_profile`, protection requirements, and limits.

### New complex task

Add a capability only when the execution semantics are genuinely new.

Decision rule:

1. If the existing capability and schema already express the request, add an example and regression test; do not add a new capability.
2. If the same table capability needs another filter field, extend its schema and executor.
3. If the request requires a stable join/workflow over several sources, add a reviewed workflow capability and handler.
4. If the request needs a new source of truth, add a new capability owned by that source.
5. If the request is out of product scope, add or refine an out-of-scope example/policy, not a DB route.

This avoids turning every production wording into another leaf route or Python keyword branch.

### Arbitrary compound requests

V1 keeps one planner action per turn. If a user asks several independent questions, the planner either:

- chooses an existing workflow capability that covers the compound business task; or
- asks the user to split or prioritize the request.

A bounded `actions[1..3]` plan may be evaluated later, but it should not be introduced until traffic shows that one-action planning is insufficient. This keeps execution and error semantics simple.

Non-retrieval outcomes
----------------------

The planner contract includes explicit non-DB outcomes.

| User request | Outcome | DB/tool calls |
|---|---|---:|
| `Как дела?` | `smalltalk` | 0 |
| `Кто ты и чем можешь помочь?` | `self_description` | 0 |
| `Какая погода в Москве?` | `out_of_scope` | 0 |
| `Удали все данные из БД` | deterministic security/permission block | 0 |
| ambiguous corporate ask | `clarify` | 0 |
| approved repository/sandbox task | `delegate_workspace_agent` | only session-allowed general tools after delegation |

Small talk and out-of-scope responses should be concise reviewed templates. The planner identifies the benign category; security validators handle dangerous requests before planning.

LLM decomposition decision
--------------------------

The system should not create four independent long-lived agents for routing, arguments, DB execution, and answer writing.

### Recommended stages

1. **Planner LLM call**
   - isolated compact context;
   - capability choice and arguments together;
   - no general tools;
   - strict structured output;
   - one repair maximum.

2. **Deterministic executor/workflow**
   - no LLM for known SQL/filter/join behavior;
   - typed input and result schemas;
   - read-only and bounded.

3. **Finalizer LLM call**
   - isolated context containing the immutable execution envelope, public evidence projection, and answer policy;
   - no tools;
   - no route catalog;
   - no ability to reopen retrieval.

4. **General ReAct agent**
   - separate capability used only for approved workspace/tool tasks;
   - never entered because corporate retrieval was empty or weak.

### Why not separate route and argument agents

The R500 2Ex failure demonstrates the cost: route choice needs the argument shape to judge the route correctly. Separating them removes useful information and prevents correction.

### Why not an LLM DB-query agent

The allowed tables, joins, filters, and hybrid modes are known. An LLM-generated SQL or free-form query plan adds risk without adding useful flexibility. The LLM should fill typed business parameters; backend code should execute them.

### Why keep a separate finalizer call

Answer synthesis and capability selection need different context:

- planning needs compact capability contracts;
- finalization needs evidence and style policy;
- combining them would either expose broad tools after evidence is ready or force evidence into the planner context.

A finalizer is a stateless no-tools LLM call, not another autonomous agent.

Security model
--------------

The proposal preserves the existing layered security model.

### Before planning

- access mode and allowlist checks;
- bot/core prompt-injection checks;
- blocked patterns;
- message size/rate limits;
- explicit command handling.

### At planning validation

- action and capability allowlist;
- JSON Schema validation;
- locked args applied last;
- no arbitrary executor/script/path/tool fields;
- capability availability filtered by session type;
- maximum string, array, numeric, and plan-size bounds.

### At execution

- read-only DB credentials;
- parameterized SQL only;
- fixed executor registry;
- bounded limits/timeouts;
- no planner-provided SQL or shell;
- workflow-specific resource budgets.

### At output

- normalized result schema;
- source/citation preservation;
- secret and encoded-output sanitizer;
- finalizer has no tools and cannot expose hidden implementation fields.

Fallback and error policy
-------------------------

### Allowed internal fallback

A capability may perform bounded deterministic recovery inside its own data contract.

Examples:

- normalized exact name -> exact lookup; optional bounded approximate suggestions remain separately labeled and do not replace a missing exact match;
- canonical enum match -> approved alias resolution;
- lexical hybrid result -> semantic fallback inside the same source scope;
- multi-name document batch where one name is absent but others succeed, with per-item outcomes and partial coverage.

These are executor implementation details and appear as `diagnostics.execution_strategy`, not new semantic route choices. They preserve every explicit constraint and source scope. Internal recovery is not permission to remove a category, widen a numeric range, substitute an entity, or treat partial evidence as complete.

### Disallowed global fallback

Runtime does not automatically switch from one business capability to another after `empty` or `error`.

- `empty` -> report no matches in the searched scope or ask a capability-local clarification; do not infer global absence from approximate search;
- `needs_clarification` -> ask exactly that question;
- `error` -> bounded service error;
- suspected planner mismatch -> log for replay; do not launch a hidden route graph.

A future one-time replan may be evaluated only with explicit telemetry proving it improves quality without recreating the current architecture.

Observability
-------------

Canonical fields become:

- `planner_action`;
- `capability_id`;
- `capability_version`;
- `planner_model`;
- `planner_latency_ms`;
- `planner_prompt_chars`;
- `planner_repair_status`;
- `capability_arg_validation_status`;
- `capability_arg_keys`;
- `executor_ref`;
- `executor_strategy` (`exact|structured|hybrid|workflow|direct`);
- `table_scopes`;
- `result_status`;
- `result_row_count`;
- `result_coverage`;
- `result_match_kind`;
- `missing_item_count`;
- `constraint_preservation_status`;
- `finalizer_mode`;
- `finalizer_latency_ms`;
- `db_call_count`;
- `workspace_agent_delegated`.

Fields such as `selected_family_id`, fallback route counts, fallback scope, route-stage, evidence grade, and guardrail attempts become migration-only compatibility telemetry and are deleted after cutover.

Required dashboards/reports:

- per-capability selection accuracy and domain/facet confusion within consolidated capabilities;
- semantic argument accuracy and explicit-constraint preservation;
- evidence relevance/coverage and answer factuality/completeness, scored separately;
- first-pass argument validity;
- result-status distribution;
- planner and finalizer p50/p95;
- zero-DB compliance for non-retrieval outcomes;
- capability confusion matrix;
- repeated-run stability for production-agent cases;
- cost per capability and per completed answer.

Registry lifecycle
------------------

### Build and validation

CI validates:

- unique capability IDs;
- valid input and result JSON Schemas;
- executor references resolve to the allowlist;
- table/search scopes are declared;
- enum sources exist and remain below configured prompt budgets;
- every capability has positive and negative examples;
- every capability has unit, integration, and benchmark ownership metadata;
- no planner-visible arbitrary paths or executor internals;
- compiled planner contract stays within the prompt-size budget without semantic truncation;
- generated planner schemas retain all decision-relevant input constraints;
- result fact/link/source references are valid and internal diagnostics are excluded from answer input;
- declared cross-field validators and executor strategies have ownership and contract tests.

### Adding support for a new request

The operator classifies the failure before changing the registry:

| Failure type | Correct change |
|---|---|
| existing capability selected, argument missing | improve capability schema/hints/example or canonical enum |
| wrong capability selected despite schema fit | improve compact `when_to_use` and contrastive examples |
| existing executor cannot express requested filter | add field and backend support to that capability |
| stable multi-table task | add workflow capability and deterministic handler |
| poor hybrid result | fix index/search/ranking in executor |
| out-of-scope request hit DB | add/clarify non-retrieval outcome examples |
| malicious request reached planner | fix deterministic ingress policy |

Do not add Python keyword branches as the default response to traffic.

Migration plan
--------------

### Phase 0: baseline and shadow artifacts

1. Freeze the current production-agent, RFC-028, Ex/2Ex, and direct-tool gates.
2. Add repeated-run stability reporting, not only one-run accuracy.
3. Generate an inventory mapping every current route to tables, executor modes, schema fields, fallback edges, and golden cases.
4. Record current planner/finalizer latency, tokens, and cost.
5. Inventory routing-specific orchestration and executor complexity: dispatch branches, strategies, exceptional rewrites, retry policies, and state fields. Record which will be deleted, retained, or replaced; moving a branch between modules is not a reduction.
6. Freeze a held-out paraphrase/multi-turn/adversarial evaluation set independently of prompt examples.

### Phase 1: capability registry in shadow mode

1. Add `core/capabilities/` and registry validation.
2. Define the initial consolidated capability set.
3. Compile it into an atomic planner contract and verify the pinned provider's schema/function-calling behavior.
4. Implement shared validation, immutable execution/answer envelopes, normalized results, and the no-tools finalizer before the first live capability. Add adapters over reviewed APIs without retaining their constraint-relaxing behavior.
5. Run the new planner in shadow mode beside the existing router without executing it.
6. Compare capability choice and arguments against goldens and labeled real traces. Old route predictions are diagnostic baselines, not semantic ground truth.

### Phase 2: first complete vertical slices

Migrate capabilities with clear table contracts through the entire new pipeline first:

- catalog documents;
- codes/SKU;
- mountings;
- sphere curated categories.

Expose both:

- new `capability_id`;
- compatibility `legacy_route_id` derived from validated arguments/result mode.

Each migrated capability uses atomic planning -> validation -> constraint-preserving executor/adapter -> normalized evidence -> no-tools finalizer or direct renderer. It never enters the old evidence grader, fallback graph, or corporate ReAct path. Partial document batches exercise coverage and per-item outcomes from the first slice.

Compatibility IDs are telemetry/test aliases only, never inputs to execution control. They allow legacy assertions to be checked where the mapping is unambiguous. For consolidated combinations without a one-to-one legacy route, maintain explicit versioned mappings and strict strategy/argument/fact assertions instead of inventing a legacy route to control behavior.

### Phase 3: catalog consolidation

1. Introduce `catalog_lamps.search` over exact, structured, category, and hybrid modes.
2. Make execution mode deterministic from validated arguments.
3. Remove route competition between `catalog_lookup` and `lamp_filters`.
4. Verify the complete Ex/2Ex incident dataset, all technical filter cases, exact-name-plus-filter combinations, and hybrid ranking within hard constraints.
5. Assert requested/applied constraint equality and disable inherited filter-relaxation retries.

### Phase 4: knowledge consolidation

1. Introduce `company_knowledge.search` with `domain`, `facets`, `query`, and optional `series`.
2. Remove `company_common` <-> `series_description` fallback semantics.
3. Remove company subtype query rewriting from agent orchestration.
4. Improve hybrid search/index behavior for natural questions where necessary.
5. Verify repeated company-fact runs, not one lucky 26-case run, including partial facts and irrelevant non-empty retrieval.
6. Validate consolidation by shared input/evidence semantics; retain separate capabilities if `domain` merely hides incompatible operations.

### Phase 5: workflow coverage and complete cutover

1. Register application recommendation and other stable multi-table flows as workflow capabilities using the already established normalized result/finalizer contracts.
2. Represent incomplete workflow stages with coverage, limitations, and per-item outcomes.
3. Complete migration of remaining corporate entry points; verify none can enter the old fallback/ReAct pipeline.
4. Keep ReAct only behind explicit `delegate_workspace_agent`, enforcing corporate-access-denying permissions even when the initial planner choice is wrong.
5. Confirm end-to-end grounding and renderer behavior for every capability, not only successful full-result paths.

### Phase 6: remove compatibility architecture

After full gate success:

- delete Python intent pre-ordering from production planning;
- delete route/argument split calls;
- delete fallback graph traversal;
- delete route-specific evidence classifiers from agent orchestration;
- delete company-fact subtype/query rewriting used for routing;
- delete routing shortlist injection into the general agent prompt;
- delete migration-only route telemetry;
- retain declarative schemas, executor validation, security, and benchmark aliases only as long as consumers require them.

Rollout and rollback
--------------------

Use one mutually exclusive full-pipeline mode:

- `routing_mode=current_routes`;
- `routing_mode=capability_planner_shadow`;
- `routing_mode=capability_planner_canary`;
- `routing_mode=capability_planner_primary`.

Canary by admin/test users first. Every eligible request records both old route prediction and new capability prediction while shadow mode is active. Only the active pipeline executes; shadow errors do not alter user-visible behavior. Report shadow overhead separately from target-path latency/cost.

During partial rollout, the registry marks which capabilities have complete vertical implementations. In canary, a new plan targeting an unmigrated capability transfers the untouched request to the intact legacy pipeline before any new execution, with explicit compatibility telemetry. This temporary coverage switch is not an `empty`/`error` fallback and is removed before primary acceptance. Migrated capabilities always run the full new path. Do not splice the new planner into old evidence/fallback orchestration.

Before Phase 6, rollback switches the entire pipeline to `current_routes`, not just the planner. Reviewed APIs remain available to the legacy path; v3 adapters enforce the new contracts without changing legacy behavior. No DB migration is required.

After Phase 6 removes the legacy pipeline, rollback requires deploying the retained pre-cleanup release artifact and its compatible configuration. Do not advertise a runtime switch to deleted code. Record and test the rollback procedure at each boundary.

Testing approach
----------------

### Unit tests

- registry and schema validation;
- capability/action allowlist;
- planner output validation and one repair limit;
- canonical enum injection;
- non-retrieval outcomes produce zero DB calls;
- exact/structured/hybrid executor mode selection;
- normalized result contracts;
- finalizer cannot call tools;
- workspace-agent delegation is explicit and permission-filtered, including corporate access through general tools;
- generated planner contract preserves semantic schema constraints and cross-field invariants;
- exact fields and numeric filters are conjunctive and cannot be silently dropped;
- fact/source/entity references validate and diagnostics are not exposed to the finalizer;
- partial batches, unknown search coverage, approximate candidates, and deterministic renderers preserve limitations.

### Deterministic contract tests

- every capability executes directly with fixed arguments and fake dependencies;
- all normalized lamp filter fields remain supported;
- workflow capabilities query only declared tables/handlers;
- security blocks occur before planner/executor invocation;
- adapters disable existing power-widening/category-dropping retries in v3;
- query ranking runs within hard-filter candidate sets;
- result-schema violations produce bounded errors rather than exposing unvalidated data;
- mistaken workspace delegation cannot invoke corporate tools or read the corporate corpus through shell/filesystem/network paths.

### Planner tests with fake LLM

- scripted atomic capability + arguments;
- invalid capability;
- unknown args;
- locked arg override;
- repair success/failure;
- smalltalk/out-of-scope/clarify/delegate outcomes.

### Provider contract tests

On the pinned production provider/model, verify strict function/structured-output behavior, actual schema subset support, enum handling, and rejection of zero/multiple actions. Provider integration tests are separate from fake-LLM validation tests. Provider-reported model pins must match configuration; schema degradation must fail visibly rather than remove constraints.

### Production E2E

Required cases include:

- `LAD LED R500 2Ex` with `flux_lm_min=11540` -> `catalog_lamps.search`, structured strategy, canonical series and numeric filter;
- exact model facts -> same capability, exact strategy;
- approximate product ask -> same capability, hybrid strategy;
- company website/year/address/contacts -> `company_knowledge.search`, no series fallback;
- series comparison -> `company_knowledge.search` with series-aware arguments;
- certificates for several series -> `catalog_documents.lookup` with bounded `names[]`;
- application recommendation -> one workflow capability;
- `Как дела?` -> smalltalk and zero DB calls;
- weather -> out-of-scope and zero DB calls;
- destructive DB request -> deterministic block and zero planner/DB calls;
- approved git/repository task -> explicit workspace-agent delegation;
- exact model plus an incompatible power/flux constraint -> no exact match, not a different model;
- approximate query plus series/IP/power bounds -> every returned candidate preserves the bounds;
- request for website/year/address with only website evidence -> supported website plus explicit missing facts, no invented year/address;
- irrelevant non-empty hybrid result -> no unsupported answer merely because execution succeeded;
- missing exact entity with similar candidates -> clearly labeled suggestions, not an exact-match success;
- partial document batch or workflow dependency failure -> per-item outcomes and partial coverage;
- "А из них какие до 100 Вт?" -> resolved prior entities and complete effective arguments reach both executor and finalizer;
- topic change -> no stale series/sphere/constraint inheritance;
- corporate question mistakenly delegated to workspace -> no alternate corporate access;
- adversarial instructions in retrieved text -> treated as evidence text, not finalizer instructions.

### Stability gate

A single passing run is insufficient for stochastic production E2E. Three passing runs are a release smoke gate, not proof of routing or answer stability.

Score four layers independently: capability selection (including domain/facets), semantic argument correctness/constraint preservation, evidence relevance/coverage, and final answer factuality/completeness. JSON validity and non-empty rows are not proxies for the latter layers. Use fixed expected facts and source/entity checks where deterministic; independently reviewed labels for open-text evidence/answers must not rely solely on the finalizer's self-assessment.

Keep existing incident goldens and a separate held-out set of paraphrases, reordered constraints, multi-turn references/topic changes, partial results, and negative retrieval cases. Run each stability case at least 10 times on the pinned configuration, including capability-order permutations. Report per-case pass rates, sample sizes, observed failure types, and uncertainty rather than only an aggregate percentage. Any prompt/schema tuning based on held-out failures requires a fresh held-out set for acceptance.

Before primary rollout:

- RFC-028/compatibility routing baseline: 100%;
- Ex/2Ex runtime replay: 100%;
- production-agent suite: 100% in at least three consecutive full runs on the pinned model;
- no variation of company-fact failures between runs;
- configured and provider-reported model pins match;
- no weakening of facts, links, or filter arguments;
- zero DB calls for every non-retrieval benchmark case;
- zero observed hard-constraint violations, unsupported required factual assertions, or corporate-access bypasses across the stability set;
- no regression against the frozen baseline in any of the four independently scored layers, including per-capability and company-fact slices;
- every missing required fact is either answered from evidence or explicitly acknowledged as unsupported; acknowledgement is measured separately from successful factual completion and cannot hide a retrieval regression.

Performance and cost budgets
----------------------------

The capability planner should replace Call A + Call B, not add a third call.

Initial budgets:

- planner calls per corporate request: 1 normally, 2 only after invalid structured output;
- planner prompt: target <= 20 KB for the initial consolidated registry;
- finalizer calls: 1 for retrieved answers, 0 for reviewed direct outcomes and planning/execution errors;
- no general agent-loop call for corporate retrieval;
- planner p95 no worse than current Call A + Call B aggregate p95;
- total production-agent p95 and tokens no worse than the verified pre-migration baseline, with a target improvement from removing fallback and ReAct iterations.

Alternatives considered
-----------------------

### Continue patching route descriptions and order

Rejected as the primary strategy. It can improve individual cases, but leaves split semantic authority, schema information loss, fallback graphs, and non-retrieval misclassification intact.

### Keep two LLM calls but let Call B reselect the route

Rejected. This creates negotiation or looping between two planners and makes ownership less clear. One atomic typed choice is simpler.

### One full ReAct agent with all tools and the whole registry

Rejected for corporate retrieval. It increases context, permits route drift after evidence is sufficient, requires more guardrails, and makes cost/latency less bounded. ReAct remains useful for open-ended workspace tasks after explicit delegation.

### Fully deterministic keyword classifier

Rejected. It recreates the current accumulation of language-specific branches and will not generalize to new phrasing. Deterministic code validates and executes; the LLM performs semantic mapping.

### Four specialized autonomous agents

Rejected for v1. Independent router, argument, DB, and answer agents duplicate context and create handoff errors. The selected design uses two narrow stateless LLM calls around a deterministic executor, not four autonomous agents.

Risks and mitigations
---------------------

### Consolidated schemas become too large

Mitigations:

- consolidate only semantically overlapping modes;
- generate compact planner contracts from full schemas without dropping decision-relevant constraints;
- include compact enums only where useful;
- keep large free-text domains out of enums;
- enforce prompt budgets in CI.

### A broad capability hides executor complexity

Mitigations:

- keep executor strategy and requested/applied constraints explicit in diagnostics;
- maintain focused direct-tool tests per strategy;
- measure special-case branches, retry policies, state fields, and duplicated schema logic across orchestration and executors, not only route count or orchestration LOC;
- split a capability only when user semantics and input contract are genuinely different, not merely because SQL paths differ.

### One wrong capability no longer has automatic cross-family fallback

This is intentional. Hidden fallback masks planner errors and creates incorrect answers. Use replay evidence to improve the planner contract; use clarification for ambiguity; allow deterministic recovery only inside the selected capability.

### Compatibility route IDs change

During migration, emit `capability_id` and a derived `legacy_route_id` where a reviewed mapping exists. Aliases never control execution. Version ambiguous consolidated mappings explicitly while retaining strict strategy, constraint, source, fact, and link assertions; a smaller ID set is not itself an accuracy improvement.

Acceptance criteria
-------------------

1. Production corporate planning uses one atomic structured-output call that chooses a capability and supplies its arguments together.
2. The planner sees the selector-visible argument shape and compact enums of each candidate capability.
3. Route choice and argument construction are no longer separate LLM calls in the primary capability-planner path.
4. The initial visible capability set is consolidated around real table/search/workflow boundaries and contains materially fewer overlapping choices than the current 22 visible routes.
5. R500 2Ex plus `flux_lm_min=11540` selects one catalog capability and executes its structured-filter strategy with the canonical series and numeric bound.
6. Company facts and series knowledge no longer depend on mutually falling back leaf routes over the same source file.
7. Runtime contains no production Python keyword classifier that reorders or overrides the capability planner's semantic choice.
8. Agent orchestration does not rewrite capability arguments after validation except declared canonicalization and locked/default args.
9. Every capability has one registered executor/workflow and one normalized result schema.
10. The executor's `success|empty|needs_clarification|error` status is authoritative for execution, with separate coverage, match kind, and per-item outcomes. Non-empty search does not imply answerability; agent orchestration does not apply a second route-specific evidence grader.
11. Corporate retrieval never enters the general ReAct loop after capability execution.
12. The answer finalizer has no tools and cannot reopen retrieval.
13. Small talk, self-description, out-of-scope, clarification, blocked request, and workspace-agent delegation are explicit top-level outcomes.
14. Small talk, weather, and blocked destructive DB requests execute zero corporate DB calls; hard-blocked requests execute zero planner calls as well.
15. Stable multi-table tasks execute through registered bounded workflow capabilities rather than LLM-generated tool sequences.
16. Capability schemas preserve structured filters and compact canonical enums; hybrid search remains available for approximate or similarity-oriented requests.
17. New request support follows the registry lifecycle: example/schema/executor/workflow/policy changes are chosen by failure type instead of defaulting to Python keyword patches.
18. Current deterministic and factual goldens are not weakened; compatibility route IDs remain available during migration.
19. RFC-028 baseline, Ex/2Ex runtime replay, and production-agent gates pass 100%, with the production-agent suite passing at least three consecutive full pinned-model runs.
20. Routing-related Python and runtime state are net-reduced after compatibility cleanup. The migration report inventories removed and retained branches, strategies, retry policies, and state across both orchestration and executors; relocating complexity is not counted as deletion.
21. All explicit exact fields and structured constraints are preserved conjunctively; v3 never drops categories or widens numeric ranges. Conflicting combinations clarify/fail validation or return no match, never a silently broadened answer.
22. The planner contract is generated from the authoritative schema without semantic truncation. Pinned-provider tests enforce the supported schema contract and exactly one action, independently of fake-LLM tests.
23. The finalizer receives immutable effective arguments and resolved entities for follow-ups, plus evidence linked by source/entity IDs. It cannot invent corporate facts/URLs, present alternatives as exact matches, or hide missing evidence.
24. Held-out repeated-run tests independently score routing, semantic arguments, evidence, and answer quality, including order permutations, multi-turn context, partial results, and irrelevant non-empty retrieval. The stability gate records no hard-constraint violations, unsupported required factual assertions, or corporate-access bypasses.
25. Every live migrated capability uses a complete vertical new pipeline from its first canary deployment. Compatibility IDs never drive execution; rollback switches the whole pipeline before cleanup and uses a tested prior release artifact after cleanup.
26. Workspace delegation denies corporate tools and indirect corpus access even after an incorrect initial planner decision. There is only one workspace delegation action.
27. Capability consolidation is justified by shared business/input/evidence/no-result contracts, not just shared storage. Company domain/facet accuracy and executor special-case complexity remain visible after route consolidation.
