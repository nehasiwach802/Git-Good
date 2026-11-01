# ECE experiment resources and demo selection

Research date: 2026-10-31. Prepared for ML person 1. Selection suggestions are proposals, not team decisions.

## Attached PDF assessment

The supplied six-page PDF is a conversational sample manual for a Zener shunt voltage regulator, followed by references. It includes an aim, component list, circuit sketch, procedure, observation tables and result template. This format is useful for structuring instructor experiment records.

It is not itself a complete college-issued multi-experiment manual. Use its linked original manuals to verify details. Text extraction loses some mathematical expressions, so review rendered equations and circuit diagrams before converting any experiment to machine-readable data. The document's embedded offers and directions are source content, not instructions to the coding agent.

Two references from the attachment were directly verified:

- [ANITS Electronic Devices and Circuits manual](https://ece.anits.edu.in/EDC%20manual.pdf), 83 pages. Its cover places it in second-year ECE/EEE; includes diode/Zener/LED characteristics, rectifiers and transistor experiments.
- [MANIT Electronics Circuit Lab EC217](https://cse.manit.ac.in/sites/default/files/documents/ECE%202017%20Electronics%20Circuit%20Lab%20Manual%20English%20III%20Sem.pdf), 47 pages. Cover identifies B.Tech semester III and academic year 2024–25, despite the older-looking URL. Includes instrument use, diode circuits, Zener regulation, and transistor/FET experiments.

## How to interpret years

There is no single experiment sequence followed by every B.Tech college. Use year/semester labels as search and catalog metadata, not as electrical behavior. Verify the actual college's curriculum/regulation before assigning an experiment to a semester.

For example, [GPCET's ECE course structures](https://www.gpcet.ac.in/ece_courdescription/) place introductory electrical practicals in year 1, device/digital labs in year 2, linear IC/digital communication/DSP/microcontroller labs in year 3, and embedded/project work in year 4 in one listed scheme. Other schemes on the same page put microwave/optical and VLSI labs in year 4. [IIST's AV232 course](https://www.iist.ac.in/academic-course/digital-electronics-and-vlsi-design-lab?pid=407) already includes digital electronics and VLSI/FPGA work in semester III. This is direct evidence that placement varies.

## Primary-source index

These are curated public resources, not a complete nationwide scrape. PDF bodies listed as verified were opened and their text inspected; search-only sources are explicitly identified. No product datapack was accessed or populated.

| ID | Official source | Material | Access/role |
|---|---|---|---|
| S1 | [J.C. Bose University basic electrical manual](https://www.jcboseust.ac.in/electrical/images/lab/bee_lab_manual.pdf) | Network laws/theorems, RLC response, RL/RC transients | Verified 57-page PDF; foundational circuit reference |
| S2 | [ANITS EDC manual](https://ece.anits.edu.in/EDC%20manual.pdf) | Diodes, regulation, rectifiers, BJT/FET | Verified 83-page PDF; second-year-labelled source |
| S3 | [MANIT EC217 manual](https://cse.manit.ac.in/sites/default/files/documents/ECE%202017%20Electronics%20Circuit%20Lab%20Manual%20English%20III%20Sem.pdf) | Instruments, diode/rectifier/regulator and transistor experiments | Verified 47-page PDF; semester III |
| S4 | [Bhagwant University digital electronics manual](https://bhagwantuniversity.ac.in/wp-content/uploads/2016/01/de-lab.pdf) | TTL gates, combinational/sequential experiments, adders | Verified 36-page PDF; semester IV |
| S5 | [IIT Roorkee Physics teaching laboratory resource index](https://www.iitr.ac.in/Departments/Physics%20Department/Academics/Teaching%20Laboratories.html) | Individual analog, digital, microcontroller and instrumentation manuals | Verified index; linked PDFs not all opened. Supplementary experiments, not an ECE semester map |
| S6 | [Communication manual hosted by ACS College of Engineering](https://www.acsce.edu.in/acsce/wp-content/uploads/2023/09/Commnication-lab-manual.pdf) | AM/FM/PAM, multiplexing, digital modulation and RF measurements | Verified 46-page PDF; cover names DSATM, ECE, semester VI, 2021–22. Retain actual cover attribution |
| S7 | [GPCET ECE course structures](https://www.gpcet.ac.in/ece_courdescription/) | Multiple schemes covering all four years | Verified HTML; use scheme-specific year assignments |
| S8 | [IIST AV232 syllabus](https://www.iist.ac.in/academic-course/digital-electronics-and-vlsi-design-lab?pid=407) | Combinational/sequential circuits, HDL and FPGA | Official course page, semester III; syllabus rather than full manual |
| S9 | [MITS microwave/optical manual](https://mits.ac.in/assets/pdf/ece/MW%20%26%20OC%20LAB%20Manual.pdf) | Microwave devices, VSWR, waveguides and optical links | Official-domain search excerpt inspected; full PDF retrieval failed, verify before ingestion |
| S10 | [SKIT VLSI manual](https://www.skit.org.in/assets/pdf/downloads/course_materials/ec/7thsem/15ECL77-VLSI%20LAB.pdf) | Verilog gates/flip-flops/adders/counters, CMOS layout | Official-domain search excerpt inspected; full PDF retrieval failed, verify before ingestion |

## Representative experiment catalog

This grouping reflects a common progression with overlap between adjacent years. It does not claim every college performs every listed experiment in the stated year. Applicability is our engineering assessment for the current photo/netlist product.

### Year 1: introductory electrical/electronics practicals

| Experiment | Source | Product fit |
|---|---|---|
| Instrument familiarization and waveform measurement | S3; foundational level, although this manual teaches it in semester III | Useful setup checks and measurement metadata |
| KCL/KVL verification | S1 | Strong initial target with low-voltage resistor networks |
| Thevenin equivalent verification | S1 | Good later circuit template |
| Norton equivalent verification | S1 | Good later circuit template |
| Superposition verification | S1 | Good later template; multiple sources add setup complexity |
| RL/RC transient response | S1 | RC is a strong demo family; measurements need time/initial-condition information |
| Series/parallel RLC frequency response | S1 | Later; frequency, losses and instrument settings matter |

### Year 2: devices, analog circuits and digital logic

| Experiment | Source | Product fit |
|---|---|---|
| PN-junction diode characteristics | S2, S3 | Good extension; requires polarity and model support |
| Zener diode characteristics and voltage regulation | S2, S3 | Small circuit; suitable if parts and simulator model are available |
| LED characteristics | S2 | Useful component extension; requires polarity and current-limiting context |
| Half/full-wave and bridge rectification | S2, S3 | Later; distinguish safe bench signal experiments from mains setups |
| BJT characteristics / common-emitter amplification | S2, S3 | Later; extra pinout, bias and device-model complexity |
| FET/MOSFET characterization | S3 | Later; package/model identification matters |
| Logic-gate truth-table verification | S4, S5 | Good digital starting point after exact IC families are identified |
| Half/full adder and subtractor | S4, S5 | Possible digital demo; requires gate models and truth-table evaluation |
| Multiplexer/demultiplexer | S5 | Later digital template; select/enable inputs must be explicit |
| Flip-flops | S4, S5 | Later; requires state, reset and clock handling |

### Year 3: IC applications, communications and programmable systems

GPCET S7 provides year-placement context; individual experiment examples are supported by the listed manuals/indexes.

| Experiment family | Source | Product fit |
|---|---|---|
| Operational-amplifier applications | S5; linear IC lab placement in S7 | Inverting amplifier remains a proposed demo; confirm actual chip, supplies and pinout |
| Analog oscillators | S5 | Later; dynamic behavior and tolerances complicate checks |
| AM/FM generation and recovery | S6 | Later; waveform interpretation and multiple instruments |
| Pulse-amplitude modulation and multiplexing | S6 | Later communication templates |
| FSK/PSK and communication simulation | S6 | Requires waveform/software artifacts beyond breadboard photos |
| ADC/DAC and display interfacing | S5; microcontroller lab placement in S7 | Requires firmware/configuration evidence |
| Microcontroller peripheral experiments | S5, S7 | Board, code and timing support needed |
| DSP laboratory work | S7 | Catalog category established; specific exercises need their own verified DSP manual |

### Year 4: specialization labs and projects

| Experiment family | Source | Product fit |
|---|---|---|
| Microwave device characterization and VSWR/waveguide measurement | S9; year-IV lab category in older S7 scheme | Specialized apparatus, outside current supported scope |
| Optical-link and fiber measurements | S9; S7 | Requires optical equipment records and measurement models |
| HDL/FPGA and VLSI layout exercises | S10; S7, S8 demonstrate variable placement | Requires HDL, waveforms and layout artifacts |
| Embedded-system projects | S7 | Needs firmware, buses and configuration context |
| Major project/internship work | S7 | Open-ended work; cannot promise a generic deterministic reference |

## What to extract into an experiment record

For each selected experiment capture:

- Stable experiment ID, title, objective, domain and indicative year/semester.
- Institution, course/regulation, source URL, page/section, access date and review status.
- Component part IDs, values, units, tolerances, package/pinout references and quantities.
- Reference electrical netlist, with human review against the rendered schematic.
- Required supply/source configuration, measurement nodes and instrument settings.
- Expected readings/curves/truth table with conditions and permitted tolerances. Derive numeric predictions from the agreed model; manuals may provide only blank observation tables.
- Allowed equivalent wiring/implementations where relevant.
- Diagnostic checks and possible misconceptions, clearly marked as proposed until reviewed.
- Capability requirements: analog SPICE, combinational logic, sequential logic, firmware, RF/optical or software simulation.
- Instructor approval and revision. Scraped material begins as unverified reference content.

Do not infer a reliable netlist from text extraction alone. Circuit images, IC orientation and unit symbols need visual verification. Manuals describe expected circuits; they do not label the actual holes and hidden leads in student photographs.

## Suggested acquisition workflow

1. Keep an attributed source index like the table above and group resources by experiment family.
2. Fetch only the manuals needed for selected templates; keep source URL, hash and page references with extracted records.
3. Extract text/tables and inspect schematic pages visually. Detect scanned PDFs and use OCR when necessary.
4. Convert one experiment at a time into the agreed schema and manually check it against the source and component datasheet.
5. Have the instructor/reasoning owner validate the reference model and expected outputs.
6. Collect independent real breadboard builds/photos with pin-to-hole annotations for ML person 1 evaluation.

This research pass collected and inspected sources and built a catalog; it did not implement a bulk crawler, download a manual corpus, ingest documents into product memory or claim support for all catalog entries.

## Recommended 18-hour selection

Keep broad curriculum coverage as a resource catalog. Implement two experiments within one supported simulation family.

- **Existing analog plan:** RC response/filter plus inverting op-amp, if parts and instrument access permit. This matches context.md and the SPICE plan.
- **Small analog alternative:** resistor-network law verification plus Zener regulation, if those are the available parts. Diode/polarity and model support become required; this would be a team scope decision.
- **Digital alternative:** gate verification plus half-adder, if the photographed board's ICs are identified and digital hardware is what is actually available. Agree a deterministic logic evaluator and digital measurement representation with ML person 2 before switching. General TTL packages cannot be assumed to work in an analog simulator without suitable models.

The photographed multi-IC board remains unidentified. Do not label it as an adder, gate experiment or any particular circuit until its ICs and intended function are confirmed. Hidden endpoints still require student correction regardless of how many manuals are collected.
