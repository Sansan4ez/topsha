import unittest

from bench.bench_lib import (
    eval_algorithmic_payload,
    eval_checks,
    check_entity_url_pairs,
    evaluate_case_result,
    get_execution,
    get_validation,
    resolve_path_values,
    select_artifact,
)


class BenchAlgorithmicEvalTests(unittest.TestCase):
    def test_get_execution_and_validation_are_backward_compatible(self):
        case = {
            "id": "legacy-case",
            "golden": {"checks": [{"type": "contains_any", "value": ["ok"]}]},
        }

        self.assertEqual(get_execution(case)["mode"], "agent_chat")
        self.assertEqual(get_validation(case)["mode"], "legacy_text")

    def test_resolve_path_values_supports_indexes_and_wildcards(self):
        payload = {
            "results": [
                {"name": "A", "url": "https://a"},
                {"name": "B", "url": "https://b"},
            ],
            "resolved_application": {"application_key": "warehouse"},
        }

        values, error = resolve_path_values(payload, "results[*].url")
        self.assertIsNone(error)
        self.assertEqual(values, ["https://a", "https://b"])

        values, error = resolve_path_values(payload, "resolved_application.application_key")
        self.assertIsNone(error)
        self.assertEqual(values, ["warehouse"])

    def test_select_artifact_uses_primary_or_selector(self):
        row = {
            "meta": {
                "primary_artifact": {"tool": "corp_db_search", "kind": "lamp_exact", "payload": {"status": "success"}},
                "bench_artifacts": [
                    {"tool": "corp_db_search", "kind": "lamp_exact", "payload": {"status": "success"}},
                    {"tool": "doc_search", "kind": "doc_search", "payload": {"status": "success"}},
                ],
            }
        }

        artifact, payload, error = select_artifact(row, {"tool": "doc_search", "kind": "doc_search"})
        self.assertIsNone(error)
        self.assertEqual(artifact["tool"], "doc_search")
        self.assertEqual(payload["status"], "success")

    def test_select_artifact_can_combine_all_matching_artifacts(self):
        row = {
            "meta": {
                "bench_artifacts": [
                    {
                        "tool": "doc_search",
                        "kind": "doc_search",
                        "payload": {"status": "success", "query": "q1", "results": [{"preview": "R500 cert"}]},
                    },
                    {
                        "tool": "doc_search",
                        "kind": "doc_search",
                        "payload": {"status": "success", "query": "q2", "results": [{"preview": "R700 cert"}]},
                    },
                ],
            }
        }

        artifact, payload, error = select_artifact(row, {"tool": "doc_search", "kind": "doc_search", "all_matches": True})
        self.assertIsNone(error)
        self.assertEqual(artifact["combined_artifacts"], 2)
        self.assertEqual(payload["status"], "success")
        self.assertEqual(len(payload["results"]), 2)
        self.assertEqual(payload["queries"], ["q1", "q2"])

    def test_incident_semantic_checks_apply_to_every_result(self):
        payload = {
            "results": [
                {
                    "series_name": "LAD LED R500 2Ex",
                    "name": "LAD LED R500-4-O-12-140L 2Ex",
                    "luminous_flux_lm": 19768,
                },
                {
                    "series_name": "LAD LED R500 2Ex",
                    "name": "LAD LED R500-4-60-12-140L 2Ex",
                    "luminous_flux_lm": 22803,
                },
            ]
        }
        passed, errors = eval_algorithmic_payload(
            payload,
            [
                {"type": "all_equals", "path": "results[*].series_name", "value": "LAD LED R500 2Ex"},
                {"type": "all_contains", "path": "results[*].name", "value": ["R500", "2Ex"]},
                {"type": "none_contains", "path": "results[*].name", "value": ["R320"]},
                {"type": "all_number_range", "path": "results[*].luminous_flux_lm", "min": 11540},
                {"type": "absent", "path": "filters.series"},
            ],
        )

        self.assertTrue(passed, errors)

        payload["results"][1]["name"] = "LAD LED R500-4-60-12-140L Ex"
        passed, errors = eval_algorithmic_payload(
            payload,
            [{"type": "all_contains", "path": "results[*].name", "value": ["R500", "2Ex"]}],
        )

        self.assertFalse(passed)
        self.assertTrue(any(error.startswith("all_contains:") for error in errors))

    def test_entity_url_pairs_require_per_entity_association(self):
        expected = [
            {"entity": "LAD LED R500", "url": "https://example/r500.pdf"},
            {"entity": "LAD LED LINE", "url": "https://example/line.pdf"},
        ]
        answer = "- LAD LED R500: https://example/r500.pdf\n- LAD LED LINE: https://example/line.pdf"
        passed, error = check_entity_url_pairs(answer, expected)
        self.assertTrue(passed, error)

        swapped = "- LAD LED R500: https://example/line.pdf\n- LAD LED LINE: https://example/r500.pdf"
        passed, error = check_entity_url_pairs(swapped, expected)
        self.assertFalse(passed)
        self.assertIn("missing_pairs", error)

        missing = "- LAD LED R500: https://example/r500.pdf"
        passed, error = check_entity_url_pairs(missing, expected)
        self.assertFalse(passed)

        generic = "- CE-сертификат для LAD LED R500: https://example/r500.pdf"
        passed, error = check_entity_url_pairs(
            generic,
            [{"entity": "LAD LED R500", "url": "https://example/r500.pdf", "forbidden": ["CE-сертификат"]}],
        )
        self.assertFalse(passed)
        self.assertIn("forbidden_on_pair", error)

        limited = "- Сертификат для LAD LED R500: https://example/r500.pdf\n  Ограничение: подтип CE не подтвержден."
        passed, error = check_entity_url_pairs(
            limited,
            [{"entity": "LAD LED R500", "url": "https://example/r500.pdf", "forbidden": ["CE-сертификат"]}],
        )
        self.assertTrue(passed, error)

    def test_text_checks_support_forbidden_tokens(self):
        passed, errors = eval_checks(
            "Подходит LAD LED R320 Ex",
            [{"type": "not_contains_any", "value": ["R500", "2Ex"]}],
        )
        self.assertTrue(passed, errors)

        passed, errors = eval_checks(
            "Подходит LAD LED R500 2Ex",
            [{"type": "not_contains_any", "value": ["R500", "2Ex"]}],
        )
        self.assertFalse(passed)
        self.assertTrue(any(error.startswith("not_contains_any:") for error in errors))

    def test_evaluate_case_result_runs_algorithmic_checks(self):
        case = {
            "id": "app-case",
            "validation": {
                "mode": "algorithmic",
                "artifact_selector": {"tool": "corp_db_search", "kind": "application_recommendation"},
                "checks": [
                    {"type": "equals", "path": "resolved_application.application_key", "value": "sports_high_power"},
                    {"type": "len_gte", "path": "recommended_lamps", "value": 2},
                    {"type": "all_prefix", "path": "recommended_lamps[*].url", "value": "https://ladzavod.ru/catalog/"},
                ],
            },
            "routing": {"selected_source": "corp_db"},
        }
        row = {
            "status": "ok",
            "meta": {
                "retrieval_selected_source": "corp_db",
                "bench_artifacts": [
                    {
                        "tool": "corp_db_search",
                        "kind": "application_recommendation",
                        "payload": {
                            "resolved_application": {"application_key": "sports_high_power"},
                            "recommended_lamps": [
                                {"url": "https://ladzavod.ru/catalog/r500"},
                                {"url": "https://ladzavod.ru/catalog/r700"},
                            ],
                        },
                    }
                ],
            },
        }

        evaluation = evaluate_case_result(case, row)
        self.assertTrue(evaluation["passed"])
        self.assertEqual(evaluation["errors"], [])
        self.assertTrue(evaluation["selection_ok"])
        self.assertTrue(evaluation["execution_ok"])
        self.assertIsNone(evaluation["answer_correctness_ok"])

    def test_effective_route_assertions_are_separate_from_selection(self):
        case = {
            "id": "document-fallback",
            "validation": {"mode": "legacy_text", "text_checks": [{"type": "contains_any", "value": ["паспорт"]}]},
            "routing": {
                "route_id": "passport_by_lamp_name",
                "selected_source": "corp_db",
                "effective_route_id": "corp_kb.company_common",
                "used_fallback_route_id": "corp_kb.company_common",
                "used_fallback_scope": "cross_family",
                "evidence_status": "sufficient",
            },
        }
        row = {
            "status": "ok",
            "answer": "Паспорт: https://example/passport.pdf",
            "execution_mode": "agent_chat",
            "meta": {
                "retrieval_leaf_route_id": "passport_by_lamp_name",
                "retrieval_selected_source": "corp_db",
                "retrieval_route_id": "corp_kb.company_common",
                "retrieval_used_fallback_route_id": "corp_kb.company_common",
                "retrieval_used_fallback_scope": "cross_family",
                "retrieval_evidence_status": "sufficient",
            },
        }
        evaluation = evaluate_case_result(case, row)
        self.assertTrue(evaluation["passed"])
        self.assertTrue(evaluation["selection_ok"])
        self.assertTrue(evaluation["execution_ok"])
        self.assertTrue(evaluation["answer_correctness_ok"])

        row["meta"]["retrieval_used_fallback_route_id"] = "corp_db.catalog_lookup"
        evaluation = evaluate_case_result(case, row)
        self.assertFalse(evaluation["passed"])
        self.assertTrue(evaluation["selection_ok"])
        self.assertFalse(evaluation["execution_ok"])

    def test_hybrid_validation_uses_bench_artifact_not_full_runtime_answer_shape(self):
        case = {
            "id": "company-fact-live",
            "validation": {
                "mode": "hybrid",
                "artifact_selector": {"tool": "corp_db_search", "kind": "hybrid_search"},
                "checks": [
                    {"type": "equals", "path": "status", "value": "success"},
                    {"type": "contains_any", "path": "results[*].preview", "value": ["239-18-11"]},
                ],
                "text_checks": [
                    {"type": "contains_any", "value": ["239-18-11"]},
                ],
            },
            "routing": {"selected_source": "corp_db"},
        }
        row = {
            "status": "ok",
            "answer": "Телефон: +7 (351) 239-18-11\nEmail: lad@ladled.ru",
            "meta": {
                "retrieval_selected_source": "corp_db",
                "bench_artifacts": [
                    {
                        "tool": "corp_db_search",
                        "kind": "hybrid_search",
                        "payload": {
                            "status": "success",
                            "result_format": "compact_company_fact_v1",
                            "results": [
                                {"preview": "Телефон +7 (351) 239-18-11, email lad@ladled.ru."}
                            ],
                        },
                    }
                ],
            },
        }

        evaluation = evaluate_case_result(case, row)
        self.assertTrue(evaluation["passed"])
        self.assertEqual(evaluation["artifact"]["tool"], "corp_db_search")


if __name__ == "__main__":
    unittest.main()
