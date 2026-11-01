# Five-experiment readings reference

Scope confirmed by the user on 2026-11-01. This is a research and implementation
handoff for the existing ML2/backend, not a new diagnostic service or approved
production catalog. Numerical examples below are calculated, not measured lab
readings. Actual values, part numbers and reference wiring must be supplied.

## Shared measurement requirements

Record experiment/version, component values and tolerances, actual supply rails,
probe positive/negative nodes, instrument identity, range, uncertainty, frequency,
waveform, DC offset, amplitude convention and scope probe factor/coupling.
Missing measurements are unknown, never zero. Preserve raw readings and units;
normalize separately to V, A, ohm, F, Hz and degrees. Keep input/output readings
from the same stimulus and circuit revision together.

For an undistorted zero-offset sine only: Vpp = 2 Vpk and Vrms = Vpk/sqrt(2).
Do not apply that conversion to rectified, clipped or offset waveforms. A meter's
AC-only RMS and total AC+DC RMS are different quantities. Prefer measured input
at the circuit over a generator's displayed setting; its load setting matters.

Comparison policy (proposed, not a universal lab tolerance): calculate a predicted
interval from component bounds, stimulus uncertainty, instrument uncertainty and
model limits. Compare it with the measurement interval. Overlap means consistent,
not proven correct; separation means mismatch; unknown bounds mean inconclusive.
Never silently assign every experiment a 5% tolerance. Percentage error is
100*abs(measured-expected)/abs(expected) only for nonzero expected values; near
zero use an absolute uncertainty bound. Wrap phase differences modulo 360 degrees.

Diagnostic sequence: validate units/settings -> check model applicability ->
compare readings -> combine with reviewed observed wiring -> propose discriminating
checks. A reading mismatch alone cannot establish a failed component or apparatus.
Return observed evidence, expected range, assumptions, candidate causes and the
next check; do not invent confidence percentages. Reference values stay out of
the vision extractor so it cannot 'repair' the observed wiring to fit expectations.

## 1. NOT gate using IC 7400 NAND gates

Tie both inputs of one NAND together: Y = NOT(A AND A) = NOT A.
For the 14-pin SN7400, one gate uses input pins 1/2 and output 3;
pin 14 is VCC and pin 7 GND. Confirm package orientation and exact suffix.

| Input A | Expected Y |
| --- | --- |
| 0 | 1 |
| 1 | 0 |

Capture voltages on both tied input pins, output and supply relative to pin 7,
for both input states; include output loading and any LED/resistor wiring.
SN7400 recommended supply is 4.75–5.25 V; valid input LOW <=0.8 V and HIGH >=2 V
within operating limits. Intermediate inputs are undefined. Output guarantees
are different: VOH >=2.4 V at IOH=-0.4 mA; VOL <=0.4 V at IOL=16 mA under the
datasheet conditions. HIGH does not mean exactly 5 V. Do not apply these output
limits to LS/HC substitutes. Hold unused inputs at defined levels.
Source: [TI SN7400 family datasheet, sections 5–6](https://www.ti.com/lit/ds/symlink/sn7400.pdf).

Our diagnostic rules: unequal voltages on supposedly tied inputs suggest checking
the jumper/contact first. A fixed output suggests checking both input changes,
supply at the IC, selected output pin and load. LED illumination alone is not
a logic reading; an LED connected to VCC can illuminate when the output is LOW.
An invalid input prevents a truth-table failure verdict.

## 2. Verification of Ohm's law

For a resistor in its approximately constant-temperature ohmic region:
V = IR, I = V/R, R = V/I. This relationship is documented by
[NASA's Ohm's law resource](https://www.grc.nasa.gov/www/k-12/Sample_Projects/Ohms_Law/ohmslaw.html).
Derived power check: P = VI = I^2 R = V^2/R.

Capture nominal/measured resistance, tolerance, power rating, voltage directly
across the resistor and series current at several DC settings. Record current
meter burden/range when relevant. Measure resistance with power removed and
isolate parallel paths. Never connect a current input directly across a supply.

Calculated example, R=1000 ohm:

| Measured resistor voltage (V) | Ideal current (mA) | Power (mW) |
| --- | ---: | ---: |
| 1 | 1 | 1 |
| 2 | 2 | 4 |
| 3 | 3 | 9 |
| 4 | 4 | 16 |
| 5 | 5 | 25 |

Our inference: fit V = R_fit*I + intercept across multiple points, with I in A.
Report residuals and uncertainty; never divide by zero current. A constant wrong
slope suggests wrong resistance, parallel paths or unit/scale error. Curvature
suggests heating, changing source behavior or a non-ohmic part; check power and
temperature before blaming equipment. Near-zero current calls for checking the
actual resistor voltage, open wiring and the meter's current path/fuse.

## 3. RC low-pass filter

Reference topology: series R from Vin to Vout; C from Vout to ground; output
measured across C. Assume negligible output load and input measured before R.
fc = 1/(2*pi*R*C), H(jw)=1/(1+j*w*R*C).
Derived magnitude = 1/sqrt(1+(f/fc)^2); phase = -atan(f/fc).
Gain_dB = 20*log10(Vout/Vin), using identical amplitude conventions.
At fc, magnitude=1/sqrt(2), gain approximately -3.0103 dB and phase=-45 degrees.
Source: [Analog Devices filter guide](https://www.analog.com/en/resources/technical-articles/a-beginners-guide-to-filter-topologies.html).

Capture R, C, their tolerances, input/output amplitudes, frequency, phase or time
lag, probe impedance/capacitance and load. For output lag dt, phase=-360*f*dt
degrees, modulo a cycle. For finite resistive load RL, our derived model is
H = 1/(1+R/RL+j*w*R*C); passband gain is below unity. Include probe capacitance
in effective C when significant. Include source resistance only if the input
reference is upstream of it; do not double-count it with measured circuit Vin.

Calculated example, R=1 kohm, C=100 nF, fc=1591.549 Hz, Vin=1 Vpp:

| Frequency | Vout (Vpp) | Phase (degrees) |
| --- | ---: | ---: |
| 0.1 fc = 159.155 Hz | 0.99504 | -5.7106 |
| fc = 1591.549 Hz | 0.70711 | -45 |
| 10 fc = 15915.494 Hz | 0.09950 | -84.2894 |

Our rules: increasing gain with frequency suggests a high-pass/probe-location
mistake. A shifted cutoff suggests wrong R/C units/values or loading. Output
nearly equal to input at all sampled frequencies suggests checking missing/open
C or an R bypass, but only after confirming the sweep spans the expected cutoff.
For positive bounds, fc interval is [1/(2*pi*Rmax*Cmax),1/(2*pi*Rmin*Cmin)].

## 4. Inverting op-amp amplifier

For grounded non-inverting input and valid linear negative feedback:
Av=-Rf/Rin and Vout=-Vin*Rf/Rin. With non-inverting bias Vref, the derived
relationship is Vout=Vref*(1+Rf/Rin)-Vin*Rf/Rin.
The ideal equation requires suitable supply, input common-mode, output swing,
load and frequency. Source: [TI op-amp design report](https://www.ti.com/lit/pdf/slaa068).

Capture exact op-amp model/package, measured positive/negative supplies, Vref,
Rin/Rf and tolerances, load, DC input/output and/or sine amplitudes/frequency/
phase. For a sine, magnitude gain is positive while phase is approximately
180 degrees in the usable band. An RMS magnitude cannot carry the inversion sign.

Calculated low-frequency linear example, Rin=10 kohm, Rf=47 kohm, Vref=0:

| Vin DC (V) | Ideal Vout DC (V) |
| ---: | ---: |
| -0.2 | +0.94 |
| -0.1 | +0.47 |
| 0 | 0 |
| +0.1 | -0.47 |
| +0.2 | -0.94 |

These rows require supplies/model allowing both output polarities; e.g. a
ground-referenced single-positive-supply build cannot produce a negative output.
Do not diagnose that clipping as a broken IC. Real offset means the zero row
needs a nonzero uncertainty allowance. Derive usable swing from the exact
datasheet at actual load. For a sine, required slew rate >=2*pi*f*Vout_pk;
verify bandwidth against the device's noise gain 1+Rf/Rin and datasheet response.

Our rules: wrong linear gain suggests resistor ratio or measurement scaling;
positive signed DC gain suggests topology/polarity confusion; a rail-bound
output suggests saturation, feedback/power/common-mode issues. Reduce input
amplitude and frequency and inspect feedback before selecting a cause.

## 5. Half-wave rectifier

Baseline: one diode plus resistive load, sinusoidal source, no smoothing capacitor;
positive half-cycles passed. Record diode model/orientation, load, input waveform/
frequency/offset/amplitude, Vout peak, DC mean, total RMS and negative half-cycle
behavior. Use an isolated low-voltage bench source, not direct mains.

Ideal model with input peak Vm: Vdc=Vm/pi, Vrms_total=Vm/2,
Idc=Vdc/RL, ripple_frequency=f_input. Derived AC-only RMS is
sqrt(Vrms_total^2-Vdc^2); ripple_factor=Vac_rms/Vdc approximately 1.211.
These are unfiltered ideal-diode relations, not capacitor-filter formulas.
Source: [IIT Kharagpur Virtual Labs](https://be-iitkgp.vlabs.ac.in/exp/half-wave-rectification/theory.html).

Calculated example: 10 Vpp zero-offset sine (Vm=5 V), RL=1 kohm:
Vdc=1.59155 V; total RMS=2.5 V; AC-only RMS=1.92794 V;
Idc=1.59155 mA. These are ideal examples, not silicon-diode acceptance limits.

Our constant-drop approximation uses vout(theta)=max(Vm*sin(theta)-Vf,0).
For 0<=Vf<Vm, alpha=asin(Vf/Vm), and integrating the conducting interval gives
Vdc=[2*Vm*cos(alpha)-Vf*(pi-2*alpha)]/(2*pi).
At Vm=5 V and assumed Vf=0.7 V, peak=4.3 V and mean approximately 1.25717 V.
If Vm<=Vf, this approximation gives zero conduction. Vf is current/temperature
dependent; 0.7 V is an illustrative assumption, not a universal constant.
For RMS, integrate vout(theta)^2 over a full cycle and take the square root.

Our rules: negative pulses suggest diode orientation/probe polarity. Both
polarities passed suggest bypass/short or probing the input. No pulses suggest
open/reversed connection, missing source or insufficient drive. Lower peaks
may reflect normal forward drop/source resistance, not a fault. A smoothing
capacitor changes the model; ask for its value and use a separate transient
reference. Average-responding sine-calibrated AC meters can misread this waveform.

## Existing-team handoff and implementation order

ML1 supplies reviewed observed connectivity, component identities/values with
uncertainty, and image/video evidence. ML2 owns model capability, reference
calculations/simulation and reading comparisons. ML3 explains evidence and next
checks. Android/backend collect typed readings using their existing contracts.
This document does not add endpoints, rename experiment IDs or replace owners.

First configure the five instructor references and measurement fields. Then add
known-good, wrong-value, wrong-wire, wrong-unit and missing-data cases per
experiment. Verify backend capability for DC/current and nonlinear diode/transient
analysis; the older local ML2 snapshot supports R/C/V/ideal-op-amp AC and limited
7400 logic, which is not sufficient proof of all five modes being implemented.
Latest shared backend memories describe API 1.1; older local smoke-route notes
are historical, not authority for new integration.

Files generated by `tools/generate_reading_examples.py` are synthetic calculated
fixtures only. Real pass/fail tolerances and reference approval remain explicit
catalog inputs. Do not use the reference wiring to overwrite student observations.
