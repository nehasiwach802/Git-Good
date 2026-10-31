from copy import deepcopy
import io
import json
from pathlib import Path
import unittest
from unittest.mock import Mock

from PIL import Image
from labvision.core import CandidateError, confirm, endpoint
from labvision.handoff import reasoning_input
from labvision.upload import extract_upload


ROOT = Path(__file__).resolve().parents[1]


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.candidate = json.loads((ROOT/'examples/7400-not.candidate.json').read_text())
        self.board = json.loads((ROOT/'examples/board-30.json').read_text())
        stream = io.BytesIO()
        Image.new('RGB', (128, 128), 'white').save(stream, format='PNG')
        self.image = stream.getvalue()

    def test_v01_uses_existing_ml2_adapter_and_preserves_uncertainty(self):
        spec = reasoning_input(self.candidate, self.board)
        self.assertEqual(spec['adapter'], 'ml1_v0.1')
        self.assertFalse(spec['payload']['candidate']['board_confirmed'])
        self.assertIsNone(spec['payload']['candidate']['reviewed_revision'])
        self.candidate['wires'][0]['a']['hole'] = None
        self.assertIsNotNone(spec['payload']['candidate']['wires'][0]['a']['hole'])

    def test_v02_requires_review_and_preserves_external_net(self):
        self.candidate['schema_version'] = '0.2'
        external = dict(endpoint(), external_terminal='SUPPLY_A')
        self.candidate['wires'].append({'id': 'Supply', 'a': external, 'b': endpoint('G10')})
        vcc = next(p for p in self.candidate['ports'] if p['role'] == 'vcc')
        vcc['endpoint'] = deepcopy(external)
        with self.assertRaises(CandidateError):
            reasoning_input(self.candidate, self.board)
        reviewed = confirm(self.candidate, self.board, 1)
        result = reasoning_input(reviewed, self.board)
        self.assertEqual(result['adapter'], 'internal_v1')
        observation = result['payload']
        vcc_node = observation['ports']['VCC']['net']
        self.assertEqual(observation['components'][0]['pins']['14']['net'], vcc_node)
        self.assertEqual(observation['source']['external_terminals']['SUPPLY_A'], vcc_node)
        self.assertTrue(observation['components'][0]['pins']['14']['confirmed'])
        self.assertEqual(observation['source']['endpoint_provenance']['VCC']['external_terminal'], 'SUPPLY_A')

    def test_v02_does_not_drop_unsupported_loads_or_change_values(self):
        self.candidate['schema_version'] = '0.2'
        self.candidate['components'] += [
            {'id': 'R1', 'part': 'resistor', 'identity_confirmed': False,
             'value_si': 1000, 'value_confirmed': False,
             'pins': {'1': endpoint('C10'), '2': endpoint('C12')}},
            {'id': 'D1', 'part': 'led', 'identity_confirmed': False,
             'pins': {'anode': endpoint('D10'), 'cathode': endpoint('D12')}}]
        observed = reasoning_input(confirm(self.candidate, self.board, 1), self.board)['payload']
        self.assertEqual([c['model'] for c in observed['components']], ['7400', 'R', 'LED'])
        self.assertEqual(observed['components'][1]['properties']['value'], 1000)

    def test_manual_upload_calls_no_provider_and_returns_null_pins(self):
        provider = Mock()
        result = extract_upload(self.image, self.board, known_parts=['7400'], try_vision=False, extractor=provider)
        provider.assert_not_called()
        self.assertEqual(result['status'], 'manual_entry_required')
        self.assertIsNone(result['netlist'])
        self.assertTrue(all(p['hole'] is None for p in result['candidate']['components'][0]['pins'].values()))

    def test_provider_timeout_returns_truthful_fallback_without_private_details(self):
        provider = Mock(side_effect=CandidateError('SECRET_PROVIDER_DETAIL'))
        result = extract_upload(self.image, self.board, known_parts=['7400'], extractor=provider)
        provider.assert_called_once()
        self.assertEqual(result['mode'], 'manual_fallback')
        self.assertEqual(result['error_code'], 'vision_unavailable')
        self.assertNotIn('SECRET_PROVIDER_DETAIL', json.dumps(result))

    def test_provider_cannot_grant_human_review(self):
        proposed = confirm(self.candidate, self.board, 1)
        provider = Mock(return_value=proposed)
        result = extract_upload(self.image, self.board, known_parts=['7400'], extractor=provider)
        self.assertEqual(result['mode'], 'gemini')
        self.assertFalse(result['candidate']['board_confirmed'])
        self.assertIsNone(result['candidate']['reviewed_revision'])
        self.assertTrue(all(not p['confirmed'] for p in result['candidate']['components'][0]['pins'].values()))
        self.assertNotIn('reference', provider.call_args.kwargs)
        self.assertNotIn('candidate', provider.call_args.kwargs)

    def test_bad_or_oversized_upload_is_not_sent_to_provider(self):
        provider = Mock()
        for data in (b'not-an-image', b'x'*(5*1024*1024+1)):
            with self.assertRaises(CandidateError):
                extract_upload(data, self.board, extractor=provider)
        provider.assert_not_called()


if __name__ == '__main__':
    unittest.main()
