import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
from reasoning.circuit import normalize
from reasoning.spice import simulate


class SpiceAdapterTests(unittest.TestCase):
    def setUp(self):
        self.request = json.loads(Path('examples/rc.json').read_text())
        self.circuit = normalize(self.request['student_circuit'])
        self.probe = self.request['experiment']['probes'][0]

    @patch('reasoning.spice.shutil.which', return_value='ngspice')
    def test_generated_deck_and_parser(self, _):
        def run(argv, **kwargs):
            deck = Path(kwargs['cwd'],'circuit.cir').read_text()
            self.assertIn('R0 n0 n1 1000', deck)
            self.assertIn('ac lin 1 ', deck)
            self.assertNotIn('v(0)', deck)
            self.assertIsInstance(argv,list)
            self.assertNotIn('shell',kwargs)
            Path(kwargs['cwd'],'reading.txt').write_text('1.59154943e2 7.0710678e-1\n')
            return subprocess.CompletedProcess(argv,0)
        with patch('reasoning.spice.subprocess.run',side_effect=run):
            self.assertAlmostEqual(simulate(self.circuit,self.probe)['value'],.70710678)

    @patch('reasoning.spice.shutil.which', return_value='ngspice')
    def test_timeout_and_solver_failure(self, _):
        with patch('reasoning.spice.subprocess.run',side_effect=subprocess.TimeoutExpired('ngspice',5)):
            self.assertEqual(simulate(self.circuit,self.probe)['status'],'timeout')
        with patch('reasoning.spice.subprocess.run',return_value=subprocess.CompletedProcess([],1)):
            self.assertEqual(simulate(self.circuit,self.probe)['status'],'failed')

    def test_directive_injection_rejected(self):
        self.probe['positive'] = 'output)\nshell command'
        with self.assertRaises(ValueError): simulate(self.circuit,self.probe)

    def test_real_solver_degenerate_and_differential_probes(self):
        import copy
        short=copy.deepcopy(self.circuit)
        source=next(c for c in short['components'] if c['type']=='V')
        source['pins']['+']='0'
        self.assertEqual(simulate(short,self.probe)['status'],'failed')
        reverse={**self.probe,'positive':'0','negative':'output'}
        self.assertAlmostEqual(simulate(self.circuit,reverse)['value'],2**-.5,places=6)
        same={**self.probe,'negative':'output'}
        self.assertEqual(simulate(self.circuit,same)['value'],0)
