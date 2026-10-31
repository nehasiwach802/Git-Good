# Git-Good

AI Lab Mentor prototype. ML person 1's first implementation converts reviewed
breadboard observations into an electrical netlist, with a Gemini image adapter
and a small 7400 NAND-as-NOT reference check.

**Status:** working local software prototype using synthetic labelled fixtures.
Real-photo extraction accuracy has not been measured. The attached circuit photos
have not been assigned verified hole-level labels. No Android/backend UI yet.

## Run locally

Python 3.10+; no third-party dependencies. Run from this directory:

```powershell
python -m labvision inspect examples/7400-not.candidate.json --board examples/board-30.json
python -m labvision confirm examples/7400-not.candidate.json --board examples/board-30.json --expected-revision 1 --reviewed --out outputs/7400-reviewed.json
python -m labvision export outputs/7400-reviewed.json --board examples/board-30.json --out outputs/7400-netlist.json
python -m labvision check-not outputs/7400-reviewed.json --board examples/board-30.json
```

The fixture is synthetic; reviewing it verifies the software example, not a real
physical circuit. For real photos, `--reviewed` acknowledges that the student has
checked the board topology, chip identity/orientation, every connection, component
value/port and missing objects. Unknown endpoints and alternative choices must be
resolved first.

Correct a pin or wire endpoint, then review the new revision:

```powershell
python -m labvision correct examples/7400-not.candidate.json --board examples/board-30.json --target W1.b --hole A17 --expected-revision 1 --out outputs/edited.json
```

This example deliberately introduces wrong wiring. Export preserves it so the
reference checker can identify the mismatch. It does not silently fix the circuit.

## Extract a photo with Gemini

Create `.env` in this project directory (it is excluded from Git):

```dotenv
GEMINI_API_KEY=your_actual_key
GEMINI_MODEL=your_available_model_id
```

The extractor loads this file automatically, including when imported by another
backend. Existing environment variables override file values, and `--model`
overrides the configured model. Optional `export` prefixes and quoted values are
accepted. File values are parsed as text and never executed. Keep your key local.

```powershell
python -m labvision board --rows 63 --out outputs/my-board.json
python -m labvision extract "C:\path\to\breadboard.jpeg" --board outputs/my-board.json --out outputs/photo-candidate.json
python -m labvision inspect outputs/photo-candidate.json --board outputs/my-board.json
python -m labvision report outputs/photo-candidate.json --board outputs/my-board.json --out outputs/photo-review.md
```

The generated board excludes power rails; verify or edit the profile for your
actual hardware. Gemini's output is always unreviewed. Use manual JSON editing to
add missed components/wires or confirm part values; preserve revision history as
described in the handoff document. If extraction fails, start from a manually
filled candidate using the example format. Do not treat example wiring as labels
for your photograph.

For slower image requests, add `--timeout 180` (maximum 300 seconds). To keep a
local provider-response artifact for debugging, add
`--raw-response outputs/photo-provider.json`. This saves response content only,
without request headers or credentials. The `report` command produces a Markdown
review sheet; unknown endpoints remain blocked from netlist export.
Models that support thinking levels can also use `--thinking-level low` to limit
reasoning effort for extraction. The response schema leaves hole IDs as strings;
local validation still enforces membership in the supplied board profile.
If the student has identified a chip, pass `--known-part 7400`. This supplies part
identity only, never expected wiring. Missing model endpoint reasons/alternatives
are filled with explicit defaults; human confirmation flags remain false.

## Checks and documents

```powershell
python -m unittest discover -s tests -v
```

- [Implemented format and integration notes](docs/ML1_HANDOFF.md)
- [Draft 7400 experiment](examples/7400-not.experiment.json)
- [18-hour plan](ML1_PLAN.md)
- [Official experiment resources](EXPERIMENT_RESOURCES.md)
- [Project context](context.md)

Pending: real-photo evaluation, board alignment/overlays, Android confirmation UI,
team API agreement, and ML person 2's full reasoning/simulation integration.
