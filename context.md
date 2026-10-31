# Project Context: AI Lab Mentor (HackCBS 9.0)

## Current ML1 integration status (2026-11-01)

- Read shared/promoted Meko records before cross-team changes; ordinary
  agent-scoped recall omitted existing teammate work during an earlier task.
- User confirms the backend is deployed. Verified live URL:
  https://git-good-1.onrender.com/; `/health` reports `mode=stub`. Its published
  contract is multipart POST `/api/sessions` with `experiment_id`, `description`,
  `image`. Preserve the existing backend and Android interfaces.
- ML2 already implements generalized 2.0 reasoning and `ml1_v0.1` / `internal_v1`
  adapters on `origin/tanu`. ML3's shared records describe its memory adapter
  and MCP transport. Those implementations remain teammate-owned.
- ML1: calibration/review/export works, one reviewed real netlist revision 45,
  matched saved session, 18 visible real-data labels; automatic extraction is
  experimental. Local development baseline matched 2/7 central wire ends; Gemini
  image requests timed out. Supply routing in the reviewed graph needs checking.
- ML1-only `extract_upload` accepts the existing backend's image bytes and returns
  an unreviewed candidate or explicit manual fallback. `reasoning_input` delegates
  v0.1 to ML2's existing adapter and exports reviewed v0.2 through `internal_v1`.
  Tested against actual ML2 code; unsupported LED is retained, not simulated away.
- Duplicate standalone API, database, Docker and Android client files created
  before checking teammate status were backed up under ignored outputs and removed.
  No replacement service is running. Original ML1 work and user labels are preserved.
- Latest checks: 67 ML1 tests pass; real v0.2 handoff passes ML2's parser. Backend
  currently exposes an upload smoke test with models marked `not_run`; integrating
  the ML1 library into that existing route is distinct from deploying a new backend.
- Authoritative ML1 integration details: `docs/TEAM_INTEGRATION.md`.

The original product plan follows; its unchecked implementation status is historical.

Team: 4 (1 Android dev, 3 ML). Status: idea selected for further work, pending validation. Alternative still on the table: the laptop repair-quote idea (see the last section).

---

## 1. Problem statement

**General form**

> Students in hands-on practicals often can't tell whether a failed experiment reflects a conceptual misunderstanding, a wiring/procedural slip, or a faulty instrument. The information that would resolve this (what was observed, what was already tried, what an instructor verified) is rarely recorded and doesn't carry over to the next attempt or the next student. The same equipment faults and misconceptions get rediscovered every semester.

**Demo wedge:** undergraduate electronics labs. We state the pattern generally but only claim it for electronics, because that's what we build and show.

**Why it matters**
- Three different causes (concept, wiring, apparatus) look identical to a student: "the output is wrong."
- Time is wasted, confidence drops, and learning gets shallower.
- Faulty equipment stays faulty because nobody records, aggregates or reports the evidence.

**What we have not proven (be honest in the pitch)**
- No primary evidence from our own campus yet. Collecting this is a to-do item.
- Impact ceiling: the problem is real but narrower and milder per person than most social-impact topics. Execution has to carry it.

**Pitch line**
> Not a chatbot that remembers. A lab system that works out whether it's you, your wiring, or the equipment, and makes sure the next student never hits the same broken probe.

---

## 2. What we are building

A lab mentor app (Android + backend) that diagnoses *why* an experiment isn't working and turns individual sessions into verified shared knowledge using Meko for memory.

### Core design principle
The LLM **explains**; deterministic components **decide**. An experiment is a data record, not hard-coded logic, so adding an experiment never needs new code.

### Experiment record (created by the instructor)
- `experiment_id`, title, learning objective
- Reference netlist
- Expected measurements at named nodes (with tolerances)
- Allowed component set
- Optional: known common misconceptions

### Student flow
1. Student opens an instructor-approved experiment (list or assignment link). App loads the reference by `experiment_id` and any approved notes for the selected `equipment_id`.
2. Student uploads a photo of the breadboard and describes the issue.
3. App recalls relevant history from Meko (this student's earlier attempts, equipment notes, instructor-verified knowledge).
4. Vision proposes a netlist **with per-connection uncertainty**.
5. Student confirms the unclear connections (fallback: tap-to-mark connections manually).
6. **Netlist diff** against the reference identifies wiring differences (deterministic graph comparison).
7. **SPICE simulation** of the confirmed circuit predicts what the student should measure.
8. Student enters actual measurements.
9. **Hypothesis ledger** updates probabilities across three causes: wiring error, conceptual error, apparatus fault.
10. Mentor asks the highest-information next check (evidence-linked, not generic advice) and explains the reasoning.
11. Session outcome is logged.

### Attribution logic (the novel part)
- Netlist differs from reference → **wiring error**
- Netlist correct, student's expectation or reasoning wrong → **conceptual error**
- Netlist correct, measurements still off → **suspect apparatus**

### Cross-student equipment inference
When *different* students running *different* experiments show the same anomaly on the same `equipment_id` (e.g. scope #3, CH2), the likelihood of an apparatus fault rises sharply, because equipment is the constant. The system flags it to the instructor/technician with the supporting sessions listed.

### Knowledge promotion and lifecycle
- Flagged patterns go to an instructor review queue.
- Instructor approves → becomes shared knowledge with provenance (who approved, which sessions) and an expiry tied to the equipment.
- Technician marks equipment repaired → warning retires.
- Next student sees the approved note on arrival, before spending time debugging.
- Student controls: can view, correct or forget their own personal context. Student-level memory, equipment-level notes and instructor-verified knowledge are shown as separate, labelled layers.

### Safety rules
- No guidance on mains voltage, large capacitors or live probing; the mentor refuses and points to the instructor.
- Prefer diagnostic questions ("what does the scope show at node X?") over prescriptions.
- Unverified student claims never enter shared knowledge without instructor approval.

---

## 3. Scope

**In scope (must work live)**
- Two experiments built from the same engine, e.g. RC low-pass filter and inverting op-amp
- Fixed component library (resistors, capacitors, op-amp, LED, wires) on a standard breadboard layout
- Netlist diff, SPICE prediction, hypothesis ledger, student confirmation step
- Instructor create-experiment form and approval queue
- Equipment-fault flag from seeded multi-student sessions
- Personal-context view / correct / forget

**Second experiment is added live in the demo** through the same form, as proof the system is general.

**Out of scope**
- Arbitrary circuits and components
- Other lab domains (state this as future work, don't claim it)
- Real usage data (use scripted, clearly labelled simulated sessions)

---

## 4. Demo script (target about 3 minutes)

1. Instructor creates the RC experiment (reference netlist, expected values).
2. Student A uploads a photo, confirms two unclear nets, enters measurements. System attributes the fault to apparatus and logs it.
3. Show seeded sessions from other students, on a different experiment, with the same anomaly on scope #3 CH2.
4. System flags the pattern; instructor approves it, with provenance shown.
5. Student B opens the experiment and is warned about scope #3 before starting. Compare with Student B's experience without the note.
6. Instructor creates the op-amp experiment live; the mentor works on it immediately.
7. Student corrects or forgets a piece of personal context.
8. Technician marks scope #3 repaired; the warning retires.

---

## 5. What needs to be done

### A. Before building (first priority)
- [ ] **Verify Meko:** read the API/docs, confirm what memory operations it supports (store, recall, forget, scoping per user/equipment/shared) and the judging rubric. The whole design depends on this; I have not verified it.
- [ ] **Collect 5 real incidents from our campus** (seniors, TAs, lab-mates): a fault that cost multiple students time, or a repeated misconception. If we can't find 5, the problem is smaller than assumed; reconsider.
- [ ] **Finish the repair-idea review analysis** (about 20-30 Google Maps reviews plus Reddit threads) so the two ideas are compared on evidence. Decide which one to build.
- [ ] Pick the two experiments and lock the component library.

### B. Build, by role
**Android dev**
- [ ] Experiment list / assignment-link entry
- [ ] Camera capture + session UI
- [ ] Tap-to-mark connection fallback
- [ ] Measurement entry
- [ ] Mentor chat view, with evidence links and a personal-context view/forget control

**ML person 1: Vision and netlist**
- [ ] Breadboard photo to candidate netlist with per-connection uncertainty
- [ ] Constrained to the fixed component set and layout
- [ ] Evaluate on a small set of our own labelled photos

**ML person 2: Reasoning core**
- [ ] Netlist graph diff against reference
- [ ] SPICE integration (e.g. ngspice) to produce predicted readings
- [ ] Hypothesis ledger (wiring / concept / apparatus) and next-check selection

**ML person 3: Memory and knowledge**
- [ ] Meko integration: recall before guidance, store session outcomes
- [ ] Cross-student equipment aggregation and flagging
- [ ] Promotion queue, provenance, expiry and retirement
- [ ] Mentor prompt layer (explains deterministic results, applies safety rules)

**Shared**
- [ ] Backend/API and instructor web view (create experiment, approval queue)
- [ ] Seed data: scripted sessions across both experiments, labelled as simulated

### C. Before submission
- [ ] End-to-end dry run of the demo script on a phone, with network failure fallback
- [ ] Fallback path if vision fails live (tap-to-mark)
- [ ] Slides: problem (with the campus incidents), approach, live demo, limits and next steps
- [ ] Rehearse judge Q&A (below)

---

## 6. Risks and judge Q&A

| Risk / question | Answer |
|---|---|
| Vision on breadboards is unreliable | Constrained library and layout, always confirm with the student, tap fallback |
| "Works on one circuit?" | Two experiments from one engine; second one added live |
| "Isn't this RAG plus memory?" | Attribution is deterministic (graph diff, SPICE, ledger); the LLM only explains. Plus cross-student equipment inference and knowledge lifecycle |
| "Is the data real?" | No. Seeded sessions, labelled simulated. Pilot is the next step |
| Memory poisoning | Nothing is shared without instructor approval; provenance on every item |
| Unsafe advice | Hard refusal rules for mains, large capacitors, live probing |
| "Impact is narrow" | Agree it starts with electronics; the pattern (concept vs procedure vs apparatus) holds across practicals, but we only claim what we built |

---

## 7. Alternative idea (decision pending)

**Laptop repair-quote clarity:** owners can't tell what evidence supports a quote or what they're authorising. Problem relevancy was rated roughly 8/10 against about 7/10 for the generalised lab problem, but validation is weaker (only secondary evidence) and the ML role is shakier. Choose based on which one our evidence supports better; if both pass, repair has more impact potential and lab has the cleaner build and demo.
