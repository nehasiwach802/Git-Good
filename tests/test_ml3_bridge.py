from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import unittest
from unittest.mock import Mock
from reasoning.api import diagnose_input
from reasoning.ml3_bridge import explain


@dataclass
class Evidence:
    evidence_id:str
    description:str
    source:str
    verification:str


@dataclass
class StrictResult:
    session_id:str
    suspected_cause:str
    cause_probabilities:dict
    evidence:tuple
    limitations:tuple
    permitted_next_action:str

    def __post_init__(self):
        if set(self.cause_probabilities)!={'wiring','concept','apparatus'}:raise ValueError('All probabilities required')


@dataclass
class OptionalResult(StrictResult):
    hypothesis_support:dict|None=None

    def __post_init__(self):
        if self.cause_probabilities is None:
            if set(self.hypothesis_support)!={'wiring','concept','apparatus'}:raise ValueError('Support required')
        else:super().__post_init__()


class ML3BridgeTests(unittest.TestCase):
    def setUp(self):
        self.diagnostic=diagnose_input(json.loads(Path('examples/generalized/ml1-7400.json').read_text()))

    def call(self,kind,callback,**kwargs):
        return explain(self.diagnostic,'synthetic-session',diagnostic_type=kind,evidence_type=Evidence,explain_callback=callback,**kwargs)

    def test_optional_consumer_receives_unchanged_fact_ids_and_no_media(self):
        callback=Mock(return_value={'status':'ok','explanation':'consumer result'})
        original=deepcopy(self.diagnostic)
        self.assertEqual(self.call(OptionalResult,callback)['status'],'ok')
        sent=callback.call_args.args[0]
        self.assertIsNone(sent.cause_probabilities)
        self.assertEqual([e.evidence_id for e in sent.evidence],[f['id'] for f in self.diagnostic['findings']])
        self.assertEqual(sent.permitted_next_action,self.diagnostic['next_check']['reason'])
        self.assertFalse(hasattr(sent,'frames'));self.assertEqual(self.diagnostic,original)

    def test_strict_consumer_abstains_without_fabricated_probabilities(self):
        callback=Mock()
        response=self.call(StrictResult,callback)
        callback.assert_not_called()
        self.assertEqual(response['status'],'fallback')
        self.assertEqual(response['model_status'],'ml3_requires_probabilities')
        self.assertIsNone(response['cause_probabilities'])
        self.assertEqual(response['next_action'],self.diagnostic['next_check']['reason'])

    def test_explicit_model_probabilities_pass_through_to_strict_consumer(self):
        callback=Mock(return_value={'status':'ok'})
        values={'wiring':.7,'concept':.2,'apparatus':.1}
        self.call(StrictResult,callback,probabilities=values,probability_source='synthetic-model-fixture')
        self.assertEqual(callback.call_args.args[0].cause_probabilities,values)
        with self.assertRaises(ValueError):self.call(StrictResult,callback,probabilities=values)

    def test_invalid_probability_values_are_rejected(self):
        for value in (True,float('nan'),float('inf'),-1,2):
            with self.subTest(value=value),self.assertRaises(ValueError):
                self.call(StrictResult,Mock(),probabilities={'wiring':value,'concept':0,'apparatus':0},probability_source='fixture')

    def test_callback_failure_does_not_change_diagnosis_or_leak_error(self):
        response=self.call(OptionalResult,Mock(side_effect=RuntimeError('private-provider-error')))
        self.assertEqual(response['model_status'],'ml3_unavailable')
        self.assertNotIn('private-provider-error',json.dumps(response))
        self.assertEqual(response['next_action'],self.diagnostic['next_check']['reason'])

    def test_fallback_preserves_electrical_safety_gate(self):
        self.diagnostic['next_check']['reason']='Probe mains voltage'
        response=self.call(StrictResult,Mock())
        self.assertEqual(response['status'],'refused')
        self.assertEqual(response['next_action'],'Ask your instructor for help.')
