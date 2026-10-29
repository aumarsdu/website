"""Offline T02 contract cases; expectations are frozen in golden/t02_expectations.json."""

import itertools
import json
import unittest
from pathlib import Path

from contract import (
    ContractError,
    Observation,
    bind_batch_id,
    field_state,
    identity_key,
    manifest_digest,
    observation_key,
    payload_hash,
    resolve_projection,
    transformation_run,
    validate_manifest,
)

GOLDEN = json.loads(
    (Path(__file__).with_name("golden") / "t02_expectations.json").read_text(
        encoding="utf-8"
    )
)
CONFIG = json.loads(
    Path(__file__).with_name("contract_config.json").read_text(encoding="utf-8")
)
WL = GOLDEN["algorithm"]["whitelist"]
HV = GOLDEN["algorithm"]["hash_version"]


def obs(order_key: str | None, payload: str) -> Observation:
    return {"order_key": order_key, "payload": payload}


class ContractTests(unittest.TestCase):
    def test_ab_a_retains_three_observations(self) -> None:
        case = GOLDEN["ab_a"]
        result = resolve_projection([obs(**o) for o in case["sequence"]])
        self.assertEqual(
            result["history_count"], case["expected"]["observations_retained"]
        )
        self.assertEqual(result["payload"], case["expected"]["projection_payload"])
        self.assertEqual(result["status"], case["expected"]["status"])

    def test_six_batch_orderings_identical(self) -> None:
        case = GOLDEN["six_orderings"]
        payloads = set()
        for permutation in itertools.permutations(case["batches"]):
            result = resolve_projection(
                [obs(o["order_key"], o["payload"]) for o in permutation]
            )
            payloads.add((result["payload"], result["status"]))
        self.assertEqual(len(payloads), 1)
        payload, status = payloads.pop()
        self.assertEqual(payload, case["expected"]["projection_payload"])
        self.assertEqual(status, case["expected"]["status"])
        self.assertTrue(case["expected"]["permutations_all_identical"])

    def test_same_order_conflict_falls_back(self) -> None:
        case = GOLDEN["same_order_conflict"]
        result = resolve_projection([obs(**o) for o in case["sequence"]])
        self.assertEqual(result["status"], case["expected"]["status"])
        self.assertEqual(result["payload"], case["expected"]["projection_payload"])
        self.assertEqual(
            result["conflict_payloads"], case["expected"]["conflict_payloads"]
        )
        self.assertEqual(
            result["history_count"], case["expected"]["observations_retained"]
        )

    def test_unknown_order_never_wins(self) -> None:
        case = GOLDEN["unknown_order"]
        result = resolve_projection([obs(**o) for o in case["sequence"]])
        self.assertEqual(result["payload"], case["expected"]["projection_payload"])
        self.assertEqual(result["status"], case["expected"]["status"])
        self.assertEqual(
            result["history_count"], case["expected"]["observations_retained"]
        )

    def test_unknown_only_is_unresolved(self) -> None:
        result = resolve_projection([obs(None, "x")])
        self.assertEqual(result["status"], "unresolved")
        self.assertIsNone(result["payload"])

    def test_top_conflict_falls_back_to_last_verified(self) -> None:
        result = resolve_projection([obs("t1", "p1"), obs("t2", "p2"), obs("t2", "p3")])
        self.assertEqual(result["status"], "conflict")
        self.assertEqual(result["payload"], "p1")
        self.assertEqual(result["conflict_payloads"], ["p2", "p3"])
        self.assertEqual(result["history_count"], 3)

    def test_top_conflict_without_fallback_stays_conflict(self) -> None:
        result = resolve_projection([obs("t1", "p1"), obs("t1", "p2")])
        self.assertEqual(result["status"], "conflict")
        self.assertIsNone(result["payload"])
        self.assertEqual(result["conflict_payloads"], ["p1", "p2"])
        self.assertEqual(result["history_count"], 2)

    def test_id_with_separator_unambiguous(self) -> None:
        case = GOLDEN["id_separator"]
        self.assertEqual(identity_key("src", "a|b"), case["with_pipe"])
        self.assertNotEqual(case["with_pipe"], case["parts_concat"])
        decoded = json.loads(case["with_pipe"])
        self.assertEqual(decoded["native_id"], case["expected"]["round_trip_native_id"])

    def test_zero_and_padded_ids_distinct(self) -> None:
        case = GOLDEN["zero_padding"]
        self.assertNotEqual(case["zero"], case["padded"])
        self.assertEqual(identity_key("src", "0"), case["zero"])
        self.assertEqual(identity_key("src", "001"), case["padded"])
        self.assertTrue(case["expected"]["no_numeric_coercion"])

    def test_unicode_digest_stable_and_frozen(self) -> None:
        case = GOLDEN["unicode"]
        record = case["record"]
        first = payload_hash(record, WL, HV)
        self.assertEqual(first, case["expected"]["digest"])
        self.assertEqual(first, payload_hash(record, WL, HV))
        self.assertTrue(case["expected"]["repeat_stable"])

    def test_field_states_distinct(self) -> None:
        case = GOLDEN["field_states"]
        value_record = case["record_value"]
        empty_record = case["record_explicitly_empty"]
        missing_record = case["record_not_provided"]
        self.assertEqual(
            field_state(value_record, "price"), case["expected"]["states"]["price"]
        )
        self.assertEqual(
            field_state(missing_record, "title"), case["expected"]["states"]["title"]
        )
        self.assertEqual(
            field_state(empty_record, "price"), case["expected"]["explicit_empty_price"]
        )
        self.assertEqual(
            field_state(value_record, "price", failed=True),
            case["expected"]["failed_price"],
        )
        states = {field_state(r, "k") for r in ({"k": 1}, {"k": None}, {})} | {
            "extraction_failed"
        }
        self.assertEqual(len(states), 4)
        self.assertTrue(case["expected"]["distinct_triples"])

    def test_noise_fields_do_not_create_versions(self) -> None:
        case = GOLDEN["hash_exclusion"]
        self.assertEqual(case["with_noise"], case["expected"]["equals_plain_payload_A"])
        plain = payload_hash(
            {"title": "项目A", "category": "理工科", "price": "12000"}, WL, HV
        )
        self.assertEqual(plain, case["expected"]["equals_plain_payload_A"])

    def test_meaningful_change_detectable(self) -> None:
        a = payload_hash(
            {"title": "项目A", "category": "理工科", "price": "12000"}, WL, HV
        )
        b = payload_hash(
            {"title": "项目B", "category": "理工科", "price": "13500"}, WL, HV
        )
        self.assertNotEqual(a, b)
        self.assertEqual(a, GOLDEN["ab_a"]["sequence"][0]["payload"])
        self.assertEqual(b, GOLDEN["ab_a"]["sequence"][1]["payload"])

    def test_hash_version_bump_changes_digest(self) -> None:
        case = GOLDEN["hash_version_bump"]
        self.assertNotEqual(case["h1"], case["h2"])
        self.assertEqual(
            payload_hash(
                {"title": "项目A", "category": "理工科", "price": "12000"}, WL, "h1"
            ),
            case["h1"],
        )
        self.assertEqual(
            payload_hash(
                {"title": "项目A", "category": "理工科", "price": "12000"}, WL, "h2"
            ),
            case["h2"],
        )
        self.assertTrue(case["expected"]["distinct"])

    def test_observation_key_covers_context(self) -> None:
        ident = GOLDEN["ab_a"]["identity"]
        base = observation_key("b1", ident, "entry_a", "p")
        self.assertNotEqual(base, observation_key("b2", ident, "entry_a", "p"))
        self.assertNotEqual(base, observation_key("b1", ident, "entry_b", "p"))
        self.assertNotEqual(base, observation_key("b1", ident, "entry_a", "q"))
        self.assertEqual(base, observation_key("b1", ident, "entry_a", "p"))

    def test_manifest_digest_and_conflict_rejected(self) -> None:
        case = GOLDEN["manifest"]
        manifest = case["manifest"]
        validate_manifest(manifest)
        digest = manifest_digest(manifest)
        self.assertEqual(digest, case["expected"]["manifest_digest"])
        self.assertEqual(bind_batch_id({"batch-001": digest}, manifest), digest)
        other = dict(manifest)
        other["coverage"] = "partial"
        self.assertEqual(manifest_digest(other), case["expected"]["other_digest"])
        with self.assertRaisesRegex(ContractError, "identity_conflict"):
            bind_batch_id({"batch-001": digest}, other)
        with self.assertRaisesRegex(ContractError, "identity_conflict"):
            bind_batch_id({"batch-001": case["expected"]["other_digest"]}, manifest)

    def test_manifest_missing_field_rejected(self) -> None:
        manifest = dict(GOLDEN["manifest"]["manifest"])
        del manifest["coverage"]
        with self.assertRaisesRegex(ContractError, "contract_invalid"):
            validate_manifest(manifest)

    def test_manifest_wrong_contract_version_rejected(self) -> None:
        manifest = dict(GOLDEN["manifest"]["manifest"], contract_version="999")
        with self.assertRaisesRegex(ContractError, "contract_invalid"):
            validate_manifest(manifest)

    def test_new_adapter_version_new_run_same_capture(self) -> None:
        case = GOLDEN["manifest"]
        batch_id = case["manifest"]["batch_id"]
        run_a = transformation_run(batch_id, "a1")
        run_b = transformation_run(batch_id, "a2")
        self.assertNotEqual(run_a, run_b)
        self.assertTrue(case["expected"]["transformation_run_on_new_adapter_distinct"])
        self.assertEqual(batch_id, case["manifest"]["batch_id"])
        self.assertTrue(case["expected"]["capture_event_unchanged"])

    def test_config_sources_have_explicit_id_rules(self) -> None:
        self.assertEqual(CONFIG["id_rule"], "string_exact")
        self.assertTrue(CONFIG["sources"])
        for name, source in CONFIG["sources"].items():
            self.assertIn("id_field", source, name)
            self.assertIn("whitelist", source, name)
            self.assertIn("identity_status", source, name)


if __name__ == "__main__":
    unittest.main()
