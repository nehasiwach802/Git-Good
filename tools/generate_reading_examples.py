"""Generate calculated teaching examples, never measured readings or API records."""
import argparse
import json
import math
from pathlib import Path


def examples():
    fc = 1 / (2 * math.pi * 1000 * 100e-9)
    vm, vf = 5.0, 0.7
    alpha = math.asin(vf / vm)
    mean = (2 * vm * math.cos(alpha) - vf * (math.pi - 2 * alpha)) / (2 * math.pi)
    # Independent midpoint integration checks the constant-drop analytical mean.
    samples = [max(vm * math.sin(2 * math.pi * (i + .5) / 100000) - vf, 0)
               for i in range(100000)]
    assert abs(sum(samples) / len(samples) - mean) < 1e-7
    records = [
        {'name': 'NOT Gate Using IC 7400 NAND Gates',
         'model': 'ideal tied-input NAND logic; electrical limits require SN7400 datasheet conditions',
         'parameters': {'part': 'SN7400', 'supply_V': 5},
         'rows': [{'input_logic': a, 'expected_output_logic': 1-a} for a in (0, 1)]},
        {'name': "Verification of Ohm's Law", 'model': 'constant resistance DC',
         'parameters': {'resistance_ohm': 1000},
         'rows': [{'voltage_V': v, 'expected_current_A': v/1000,
                   'expected_power_W': v*v/1000} for v in (1, 2, 3, 4, 5)]},
        {'name': 'RC Low-Pass Filter', 'model': 'unloaded series R, shunt C, sine',
         'parameters': {'resistance_ohm': 1000, 'capacitance_F': 100e-9,
                        'input_Vpp': 1, 'cutoff_Hz': fc},
         'rows': [{'frequency_Hz': ratio*fc,
                   'expected_output_Vpp': 1/math.sqrt(1+ratio*ratio),
                   'expected_phase_deg': -math.degrees(math.atan(ratio)),
                   'expected_gain_dB': -10*math.log10(1+ratio*ratio)}
                  for ratio in (.1, .5, 1, 2, 10)]},
        {'name': 'Inverting Op-Amp Amplifier',
         'model': 'ideal linear negative feedback, grounded non-inverting input; supplies must permit output',
         'parameters': {'Rin_ohm': 10000, 'Rf_ohm': 47000, 'Vref_V': 0},
         'rows': [{'input_DC_V': v, 'expected_output_DC_V': -4.7*v}
                  for v in (-.2, -.1, 0, .1, .2)]},
        {'name': 'Half-Wave Rectifier', 'model': 'positive half-wave, resistive load, no capacitor',
         'parameters': {'input_Vpp': 10, 'input_offset_V': 0, 'load_ohm': 1000},
         'rows': [
             {'diode_model': 'ideal', 'expected_peak_V': vm,
              'expected_mean_V': vm/math.pi, 'expected_total_rms_V': vm/2,
              'expected_ac_only_rms_V': math.sqrt((vm/2)**2-(vm/math.pi)**2),
              'expected_mean_current_A': vm/math.pi/1000},
             {'diode_model': 'constant_drop_approximation', 'assumed_forward_drop_V': vf,
              'expected_peak_V': vm-vf, 'expected_mean_V': mean,
              'expected_total_rms_V': math.sqrt(sum(x*x for x in samples)/len(samples)),
              'expected_mean_current_A': mean/1000}]}]
    return {'status': 'calculated_examples_not_measurements', 'workflow_approved': False,
            'purpose': 'Reference research fixtures; not backend payloads or universal acceptance limits',
            'reference_document': 'docs/FIVE_EXPERIMENT_READINGS.md', 'experiments': records}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(examples(), indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(f'Wrote calculated examples: {args.out}')
