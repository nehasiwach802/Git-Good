import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
from reasoning.api import diagnose_input, validate_input
from reasoning.observations import ExperimentCatalog
from reasoning.session import advance_session
from reasoning.validation import ValidationError
from reasoning.registry import capabilities
from reasoning.adapters import ml1_v01


def load(name="rc"):
    return json.loads(Path(f"examples/generalized/{name}.json").read_text())


def forbidden(*args):
    raise AssertionError("uncertain/unsupported evidence must not reach simulation")


class GeneralizedTests(unittest.TestCase):
    def test_two_experiments_same_engine_real_spice(self):
        for name, value in (("rc", 2**-.5), ("divider", .5)):
            with self.subTest(name=name):
                result = diagnose_input(load(name))
                self.assertEqual(result["status"], "evaluated")
                self.assertEqual(result["hypotheses"]["wiring"]["support"], "unresolved")
                self.assertAlmostEqual(result["predictions"][0]["student"]["value"], value, places=6)

    def test_unknown_and_alternatives_are_not_wiring_faults(self):
        for name, kind in (("rc-unknown", "unknown_connection"), ("rc-uncertain", "alternative_connections")):
            result = diagnose_input(load(name), forbidden)
            self.assertEqual(result["status"], "needs_confirmation")
            self.assertEqual(result["hypotheses"]["wiring"]["support"], "unresolved")
            self.assertTrue(any(f["kind"] == kind for f in result["findings"]))
            self.assertFalse(result["predictions"])

    def test_confirmed_wrong_wiring(self):
        request = load()
        request["reference"]["analysis"] = {"engine": "connectivity"}
        request["observation"]["components"][0]["pins"]["2"]["net"] = "wrong"
        result = diagnose_input(request, forbidden)
        self.assertEqual(result["hypotheses"]["wiring"]["support"], "supported")
        self.assertEqual(result["next_check"]["kind"], "review_wiring")

    def test_correcting_extraction_does_not_retain_fault(self):
        request = load("rc-uncertain")
        first = advance_session(request, simulator=forbidden)
        request["observation"] = load()["observation"]
        request["observation"].update(revision=2, reviewed_revision=2)
        second = advance_session(request, first["state"])
        self.assertEqual(second["result"]["hypotheses"]["wiring"]["support"], "unresolved")
        self.assertEqual(len(second["state"]["snapshots"]), 2)

    def test_missing_identity_needs_explicit_correspondence(self):
        request = load()
        request.pop("component_map")
        result = diagnose_input(request, forbidden)
        self.assertEqual(result["status"], "needs_confirmation")
        self.assertEqual(result["hypotheses"]["wiring"]["support"], "unresolved")

    def test_confirmed_independent_property_during_partial_review(self):
        request = load("rc-unknown")
        request["observation"]["components"][1]["properties"]["value"] = 2e-6
        result = diagnose_input(request, forbidden)
        self.assertEqual(result["status"], "needs_confirmation")
        self.assertTrue(any(f["kind"] == "wrong_property" and f["certainty"] == "confirmed" for f in result["findings"]))

    def test_unknown_values_request_evidence(self):
        request = load()
        request["observation"]["components"][0]["properties"]["value"] = None
        result = diagnose_input(request, forbidden)
        self.assertEqual(result["status"], "needs_confirmation")
        self.assertFalse(any(f["kind"] == "wrong_property" for f in result["findings"]))

    def test_unsupported_analysis_or_model_is_explicit(self):
        request = load()
        request["reference"]["analysis"] = {"engine": "transient"}
        self.assertEqual(diagnose_input(request, forbidden)["status"], "unsupported_analysis")
        request = load()
        request["observation"]["components"][0]["model"] = "unmodeled_part"
        self.assertEqual(diagnose_input(request, forbidden)["status"], "unsupported_analysis")

    def test_draft_and_missing_safety_do_not_run(self):
        for field in ("approval", "safety"):
            request = load()
            if field == "approval": request["reference"]["approval"] = "draft"
            else: request.pop("safety_profile")
            self.assertEqual(diagnose_input(request, forbidden)["status"], "instructor_required")

    def test_malformed_fields(self):
        mutations = [
            lambda r: r.update(component_map={"seen_R1": "R1", "seen_C1": "R1"}),
            lambda r: r.update(component_map={"missing": "R1"}),
            lambda r: r["observation"].update(revision=True),
            lambda r: r["observation"].update(reviewed_revision=2),
            lambda r: r["observation"]["components"][0]["pins"]["2"].update(alternatives="bad"),
            lambda r: r["observation"]["components"][0]["properties"].update(value=float("nan")),
            lambda r: r["reference"]["analysis"]["probes"][0].update(positive_port="unknown"),
            lambda r: r["reference"]["analysis"]["probes"][0].update(frequency_hz=0),
            lambda r: r.update(problem_description=[]),
            lambda r: r["observation"]["components"][0]["pins"].pop("1"),
        ]
        for mutate in mutations:
            request = load(); mutate(request)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                validate_input(request)

    def test_session_reference_and_physical_revision_boundaries(self):
        request = load()
        first = advance_session(request)
        for mutate in (
                lambda r: r["reference"].update(version="2"),
                lambda r: r["observation"].update(id="another"),
                lambda r: r["observation"]["components"][0]["pins"]["1"].update(net="edited")):
            edited = copy.deepcopy(request); mutate(edited)
            with self.assertRaises(ValueError): advance_session(edited, first["state"], forbidden)

    def test_observation_is_not_modified(self):
        request = load("rc-uncertain"); original = copy.deepcopy(request)
        diagnose_input(request, forbidden)
        self.assertEqual(request, original)

    def test_catalog_is_versioned_defensive_copy(self):
        record = load()["reference"]
        catalog = ExperimentCatalog([record])
        result = catalog.get(record["experiment_id"], "1")
        result["ports"].clear()
        self.assertTrue(catalog.get(record["experiment_id"], "1")["ports"])
        with self.assertRaises(ValueError): ExperimentCatalog([record, record])
        with self.assertRaises(ValidationError): catalog.get("unknown", "1")
        request = load()
        request.pop('reference')
        request.update(experiment_id=record['experiment_id'], experiment_version='1')
        self.assertEqual(diagnose_input(catalog.bind(request))['status'], 'evaluated')

    def test_draft_reference_cannot_confirm_a_fault(self):
        request = load()
        request['reference']['approval'] = 'draft'
        request['observation']['components'][0]['properties']['value'] = 2000
        result = diagnose_input(request, forbidden)
        self.assertEqual(result['hypotheses']['wiring']['support'], 'unresolved')

    def test_passive_terminal_reversal_and_net_renaming(self):
        request = load()
        pins = request['observation']['components'][0]['pins']
        pins['1'], pins['2'] = pins['2'], pins['1']
        result = diagnose_input(request)
        self.assertEqual(result['hypotheses']['wiring']['support'], 'unresolved')
        self.assertEqual(result['predictions'][0]['student']['status'], 'ok')

    def test_ml1_adapter_uses_actual_candidate_without_reference(self):
        request = load("ml1-7400")
        result = diagnose_input(request)
        self.assertEqual(result["status"], "evaluated")
        self.assertEqual(result["next_check"]["kind"], "review_learning_objective")
        candidate = request["input"]["payload"]["candidate"]
        candidate["reviewed_revision"] = None
        candidate["wires"][0]["b"]["confirmed"] = False
        obs = ml1_v01(request["input"]["payload"])
        self.assertFalse(obs["completeness_confirmed"])
        self.assertFalse(any(p["confirmed"] for c in obs["components"] for p in c["pins"].values()))
        self.assertEqual(diagnose_input(request, forbidden)["status"], "needs_confirmation")

    def test_adapter_does_not_accept_both_inputs(self):
        request = load("ml1-7400")
        request["observation"] = load()["observation"]
        with self.assertRaises(ValidationError): validate_input(request)

    def test_explicit_port_correspondence(self):
        request = load()
        request['observation']['ports']['detected_output'] = request['observation']['ports'].pop('OUT')
        self.assertEqual(diagnose_input(request, forbidden)['status'], 'needs_confirmation')
        request['port_map'] = {'detected_output': 'OUT'}
        result = diagnose_input(request)
        self.assertEqual(result['status'], 'evaluated')
        self.assertEqual(result['predictions'][0]['student']['status'], 'ok')
        request['port_map'] = {'missing': 'OUT'}
        with self.assertRaises(ValidationError): validate_input(request)

    def test_registry_declares_limits(self):
        result = capabilities()
        self.assertNotIn("transient", result["analyses"])
        self.assertTrue(result["models"]["R"]["interchangeable_terminals"])
        self.assertNotIn("analog_ac", result["models"]["7400"]["analyses"])

    def test_model_registry_change_invalidates_session(self):
        from unittest.mock import patch
        request = load()
        state = advance_session(request)['state']
        with patch('reasoning.registry.REGISTRY_VERSION', 'new-models'):
            with self.assertRaises(ValueError): advance_session(request, state, forbidden)

    def test_cli_generalized_request(self):
        result = subprocess.run([sys.executable, "-m", "reasoning", "examples/generalized/rc-uncertain.json"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "needs_confirmation")
