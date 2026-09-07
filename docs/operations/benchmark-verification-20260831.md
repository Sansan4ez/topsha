# Production benchmark verification — 2026-09-07

## Final verification attempt (current HEAD)

**Not complete — issue `totosha-3ee9.1` remains open.** The current HEAD was rebuilt and the deterministic direct-tool, Ex/2Ex incident, RFC-028 runtime, and five independent company-fact stability runs were recorded. The full production-agent gate remained below 100%: the final full replay reached 23/26, with `sales-001-certificates-links`, `tech-034-lamp-filters-category-fallback`, and `tech-036-application-street-pole-lighting` failing answer checks. An earlier final replay reached 25/26 and exposed `tech-016-retrieval-r500-12-by-power-voltage`; subsequent focused reruns passed that case, confirming runtime answer instability rather than a reason to weaken the golden checks. The strict golden assertions were not relaxed. The focused source regression suite passed after narrow routing-state fixes; remaining production-agent failures are tracked in follow-up `totosha-d6er`.

### Current deployment metadata

| Item | Value |
|---|---|
| Source SHA before final rebuild | `a89397826c7a498df6c2d8d0f6f65b5c563aecb1` |
| Source dirty status before final rebuild | `.beads/issues.jsonl` was dirty from the required issue claim; code was clean |
| Final core image | `sha256:ce8e41915f27586b774713c00d21a08c5aabe3118a813e7d004ce9bc051206fb` |
| Final tools-api image | `sha256:76dee7771fcd5b0caa558f870a940c462c193ca1fda7c98de7a25c4a784bf65a` |
| Core build metadata | `git_sha=a89397826c7a498df6c2d8d0f6f65b5c563aecb1-dirty`, `build_time=2026-09-07T05:35:17Z` |
| tools-api build metadata | `git_sha=a89397826c7a498df6c2d8d0f6f65b5c563aecb1-dirty`, `build_time=2026-09-07T05:35:17Z` |
| Effective configured model | `gpt-5.6-terra` from `workspace/_shared/admin_config.json` |
| Provider-reported model | `gpt-5.6-terra` |
| Dataset revisions | `v1=0af31ec8dcbdbf13be26b71db3006bce765ec905`, `incident-ex-2ex=b068d714bdd8aba9ae888c4f64ecce2176d6db6c`, `incident-pfit7=1163ccc4368990b8438d578e26b4be3eec460e66`, `rfc028=a0a1a8b1d3371199ce91248a23f60e05d5b96719`, `prod-agent=9f713789cbb97938e3cb17726d2b1dff4a87d894` |

Rebuild command:

```bash
SHA=$(git rev-parse HEAD)
BUILD_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
BUILD_GIT_SHA="$SHA" BUILD_TIME="$BUILD_TIME" docker compose build core tools-api
BUILD_GIT_SHA="$SHA" BUILD_TIME="$BUILD_TIME" docker compose up -d --no-deps core tools-api
```

Health endpoints reported `status=ok`, routing catalog `valid=true`, route count 24, and RFC-026 database objects applied.

### Final gate results

| Gate | Result | Latency avg / p50 / p95 | Tokens | Estimated cost |
|---|---:|---:|---:|---:|
| Direct-tool v1 (47 direct-tool cases) | **47/47** | 250.490 / 122.315 / 733.271 ms | 0 | $0 |
| Ex/2Ex direct-tool | **6/6** | 259.031 / 165.690 / 496.522 ms | 0 | $0 |
| Ex/2Ex runtime incident smoke | **6/6**, doctor required checks 3/3 | 272.053 / 148.198 / 728.376 ms | 0 | $0 |
| RFC-028 runtime routing | **22/22** | 11,433.982 / 9,470.102 / 18,761.378 ms | 173,586 total | $0.4966275 |
| Company facts, independent clean-session runs | **5/5 each run** across 5 runs | avg 9,482.350–10,729.478 ms | 41,234–41,445 total/run | $0.087319–$0.1223725/run |
| Full prod-agent-v1 runtime (final full replay) | **23/26 (88.46%)** | 11,515.298 / 10,434.137 / 16,769.125 ms | 237,057 total | $0.6293305 |

The full prod-agent failure request IDs were:

- `bench/20260907_054314Z_bf6194/sales-001-certificates-links` — final answer omitted the required per-entity URL pairs.
- `bench/20260907_054314Z_bf6194/tech-034-lamp-filters-category-fallback` — final answer omitted `R320`; a direct tools-api replay returned `category_filter_dropped=true` and R320 results.
- `bench/20260907_054314Z_bf6194/tech-036-application-street-pole-lighting` — final answer omitted the required height/pole evidence.
- Earlier `bench/20260907_052848Z_94a4c9/tech-016-retrieval-r500-12-by-power-voltage` returned the bounded no-result answer despite a verified tool match; focused reruns later passed it.

Selection accuracy for the final full production-agent run was **26/26**; effective execution assertions were **2/2**; answer correctness was **23/26**. This distinguishes selector success from answer/evidence correctness. Follow-up: `totosha-d6er`.

### Focused verification and environment warnings

Commands run included:

```bash
docker run --rm --entrypoint python -e PYTHONPATH=/repo -v "$PWD:/repo:ro" -w /repo totosha-core -m pytest -q core/tests --ignore=core/tests/test_sandbox.py
python3 bench/bench_run.py --docker-exec --dataset bench/golden/incident-ex-2ex-20260827.jsonl --timeout-s 180 --out ...
python3 bench/bench_run.py --docker-exec --dataset bench/golden/rfc028-routing-baseline.jsonl --force-agent-chat --chat-execution-mode runtime --expected-configured-model gpt-5.6-terra --expected-llm-model gpt-5.6-terra --timeout-s 180 --out ...
python3 scripts/incident_replay_smoke.py --docker-exec --timeout-s 180 --json
python3 scripts/doctor.py --json
```

Focused Core suite: **346 passed, 5 skipped**. The full Core pytest excluding sandbox tests passed. The tools-api image test run passed **71 tests with 1 pre-existing fixture failure** (`ToolsApiCorrelationTests.test_route_updates_correlation_context_with_tool_call_headers`, dummy connection lacks `fetchrow` for the embedding-coverage probe); the production `/health` and live tool calls were healthy.

Security doctor: **73/74**, with the known medium environment warning `perm_docker-compose.yml` (`docker-compose.yml` mode `0o664`, expected `0o644`). No benchmark assertions or golden facts/routes/tool args were changed to hide failures.

The original 2026-08-31 evidence follows for historical comparison; its rebuilt SHA `10bd54e` is not evidence for current HEAD.


## Outcome

**Not complete — issue `totosha-3ee9.1` remains open.** The stack was rebuilt from the checked-out SHA and the deterministic data plane and RFC-028 routing baseline passed. The required production-agent and full Ex/2Ex runtime gates did not reach 100%; no golden assertions, expected facts, route ids, or tool arguments were relaxed.

Concrete follow-up bugs were created:

- `totosha-qzg8` — stabilize company-fact production-agent verification.
- `totosha-7wtt` — restore the canonical R500 2Ex runtime route and argument contract.

## Verified source and deployment

| Item | Value |
|---|---|
| Git SHA rebuilt | `10bd54e5cc3cc000ac2097d6bfce353d270b831b` |
| Compose command | `BUILD_GIT_SHA="$SHA" BUILD_TIME="$BUILD_TIME" docker compose build core tools-api` followed by `... docker compose up -d --no-deps core tools-api` |
| Final verified Core build time | `2026-08-31T03:32:44Z` |
| Final verified Core image | `sha256:a7497eb48142c4411a2b09d15144461bc4ae87072404a3410d82be03ca3cab6f` |
| Final verified tools-api build time | `2026-08-31T03:28:57Z` |
| Final verified tools-api image | `sha256:c441e3b76205e08ab67993606a558a5d89883114b3042214dab6c196700c858a` |
| Health | Core and tools-api healthy; `/health` reports the SHA/build time above |
| Effective configured model | `gpt-5.6-terra` from `workspace/_shared/admin_config.json` |
| Provider-reported model pin | `gpt-5.6-terra` (`meta.llm_models`) |

The five remediation commits were inspected before verification:

- `e0ab451` — mounting route semantics (`totosha-il0l`)
- `7878e21` — series knowledge to company KB (`totosha-z3wc`)
- `845e403` — document route identity (`totosha-or6b`)
- `7585e99` — certificate links (`totosha-w09q`)
- `37c4b19` — portfolio evidence (`totosha-6tpo`)

## Fast tests

Commands:

```bash
docker run --rm --entrypoint python --network totosha_agent-net \
  -v "$PWD:/repo:ro" -w /repo/core totosha-core -m unittest -q \
  tests.test_route_catalog_check tests.test_route_selector_fake \
  tests.test_routing_catalog tests.test_routing_guardrail \
  tests.test_corp_db_tool tests.test_rfc027_llm_only

docker run --rm --entrypoint python -v "$PWD:/repo:ro" -w /repo \
  totosha-core -m unittest -q \
  bench.tests.test_algorithmic_eval bench.tests.test_compare \
  bench.tests.test_routing_accuracy_summary bench.tests.test_routing_eval \
  bench.tests.test_run_modes scripts.tests.test_admin_auth \
  scripts.tests.test_asr_compat_smoke scripts.tests.test_corp_db_lamp_filters_latency \
  scripts.tests.test_doctor scripts.tests.test_incident_replay_smoke
```

| Suite | Result |
|---|---:|
| Core focused route/guardrail/contract tests | 161 passed, 3 skipped |
| Bench and scripts unit tests | 56 passed |
| Full Core pytest excluding Docker sandbox tests | 333 passed, 4 skipped, **1 failed** |
| tools-api pytest in a production-image dependency container | 71 passed, **1 failed** |

The full Core pytest failure was `tests/test_tools.py::test_schedule_task_add_list_cancel`: live scheduler output was `✅ Scheduled at 22:50 (once)` and did not expose the test-required `task_<id>`. It is outside the benchmark-remediation changes. The tools-api failure was `tests/test_corp_db_correlation.py::ToolsApiCorrelationTests::test_route_updates_correlation_context_with_tool_call_headers`: its dummy connection has no `fetchrow` for the embedding-coverage observability probe. Neither failure changes the deterministic benchmark results below.

## Deterministic data-plane and incident checks

Commands:

```bash
python3 bench/bench_run.py --docker-exec --dataset bench/golden/v1.jsonl \
  --timeout-s 180 --out bench/results/verification-20260831/direct-tool-v1-final.jsonl
python3 bench/bench_eval.py --dataset bench/golden/v1.jsonl \
  --results bench/results/verification-20260831/direct-tool-v1-final.jsonl

python3 bench/bench_run.py --docker-exec --dataset bench/golden/incident-pfit7.jsonl \
  --timeout-s 180 --out bench/results/verification-20260831/incident-pfit7-final.jsonl
python3 bench/bench_eval.py --dataset bench/golden/incident-pfit7.jsonl \
  --results bench/results/verification-20260831/incident-pfit7-final.jsonl

python3 scripts/incident_replay_smoke.py --docker-exec --timeout-s 180 --json
```

| Dataset / gate | Result | Latency avg / p50 / p95 | Tokens | Cost |
|---|---:|---:|---:|---:|
| `v1.jsonl` direct tool | **50/50** | 830.735 / 107.993 / 3860.254 ms | 20,664 / 1,004 / 21,668 | $0.06672 |
| `incident-pfit7.jsonl` | **3/3** | 453.742 / 413.759 / 645.382 ms | 0 | $0 |
| Ex/2Ex direct-tool dataset | **6/6** | 129.140 / 132.633 / 168.069 ms | 0 | $0 |
| Ex/2Ex runtime chat replays | **5/6** | n/a | n/a | n/a |

The full incident smoke failed only for canonical R500 2Ex. Failure request id:

- `incident-smoke/canonical_r500_2ex/15084bffff3c41b19ed1d89b3a5c963d`

It selected `corp_db.catalog_lookup` / `lamp_exact` instead of required `corp_db.lamp_filters` with `series=LAD LED R500 2Ex` and `flux_lm_min=11540`. The reproducible failure is tracked in `totosha-7wtt`.

## RFC-028 production routing baseline

Command:

```bash
python3 bench/bench_run.py --docker-exec \
  --dataset bench/golden/rfc028-routing-baseline.jsonl \
  --force-agent-chat --chat-execution-mode runtime \
  --expected-configured-model gpt-5.6-terra \
  --expected-llm-model gpt-5.6-terra --timeout-s 180 \
  --out bench/results/verification-20260831/rfc028-routing-runtime-verified.jsonl
python3 bench/bench_eval.py --dataset bench/golden/rfc028-routing-baseline.jsonl \
  --results bench/results/verification-20260831/rfc028-routing-runtime-verified.jsonl
```

**22/22 passed (100%).** Routing accuracy was 22/22 with no mismatches. Latency was 8,133.251 ms average, 7,205.925 ms p50, and 13,071.969 ms p95. Token usage was 159,707 prompt + 4,812 completion = 164,519 total; estimated cost was **$0.4029035**.

## Production-agent E2E

Command:

```bash
python3 bench/bench_run.py --docker-exec \
  --dataset bench/golden/prod-agent-v1.jsonl \
  --chat-execution-mode runtime \
  --expected-configured-model gpt-5.6-terra \
  --expected-llm-model gpt-5.6-terra --timeout-s 180 \
  --out bench/results/verification-20260831/prod-agent-runtime-verified-current.jsonl
python3 bench/bench_eval.py --dataset bench/golden/prod-agent-v1.jsonl \
  --results bench/results/verification-20260831/prod-agent-runtime-verified-current.jsonl
```

**23/26 passed (88.46%): acceptance criterion not met.** Model pins passed on all rows: configured and provider-reported model were both `gpt-5.6-terra`.

| Metric | Value |
|---|---:|
| Latency avg / p50 / p95 | 10,008.845 / 9,482.939 / 15,156.959 ms |
| Prompt / completion / total tokens | 227,527 / 8,355 / 235,882 |
| Estimated cost | $0.6014065 |
| Route accuracy | 23/26 |

Failures and request IDs:

- `mk-001-founded-year` — answer had no year and route fell back to `series_description`; `bench/20260831_033653Z_74e99b/mk-001-founded-year`
- `mk-002-website` — answer omitted `ladzavod.ru` and route fell back to `series_description`; `bench/20260831_033653Z_74e99b/mk-002-website`
- `mk-003-head-office` — answer omitted the required Chelyabinsk/Chaykovskogo address and route fell back to `series_description`; `bench/20260831_033653Z_74e99b/mk-003-head-office`

Earlier reruns produced 25/26 with a varying company-fact failure. This confirms nondeterministic production-agent company-fact behavior rather than a valid reason to relax the golden suite; it is tracked in `totosha-qzg8`.

## Security doctor

Command:

```bash
python3 scripts/doctor.py --json
```

Doctor recorded 73/74 checks passing. The sole environmental warning/failure is:

- `[MEDIUM] perm_docker-compose.yml`: mode `0o664`; expected `0o644`.

All security controls, blocked/injection patterns, access checks, sandbox limits, and RFC-026 database checks passed. The permission warning is pre-existing deployment hygiene and not a benchmark behavior regression.

## Decision

Do not close `totosha-3ee9.1` until `totosha-qzg8` and `totosha-7wtt` are resolved and the complete production-agent and full incident runtime gates reach 100% with the same model pins.
