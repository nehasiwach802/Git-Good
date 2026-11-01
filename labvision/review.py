"""Human-readable review sheet for unverified image extraction results."""

from .core import endpoints, pending, validate, resolved, endpoint_label


def review_markdown(candidate, board):
    validate(candidate, board)

    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")

    points = list(endpoints(candidate))
    unknown = sum(not resolved(p) for _, p, _ in points)
    unresolved = pending(candidate, board)
    lines = [
        "# Photo extraction review", "",
        f"Candidate: `{candidate['candidate_id']}`, revision {candidate['revision']}.", "",
        "**Unverified model observations. This sheet is not a labelled ground truth or a wiring diagnosis.**", "",
        f"Components: {len(candidate['components'])}; wires: {len(candidate['wires'])}; "
        f"ports: {len(candidate['ports'])}; unknown endpoints: {unknown}/{len(points)}.", "",
        f"Board profile: `{board['id']}`. Board confirmed: {candidate['board_confirmed']}.", "",
        "Board connectivity groups are provisional until physically verified. "
        "Verify the physical board numbering, orientation and connected groups before accepting any hole IDs.", "",
        "## Components", "", "| ID | Proposed part | Identity/orientation reviewed |",
        "|---|---|---|",
    ]
    lines += [f"| {cell(c['id'])} | {cell(c['part'])} | {c['identity_confirmed']} |"
              for c in candidate["components"]]
    lines += ["", "## Endpoint proposals", "",
              "| Endpoint | Proposed hole / external terminal | Alternatives | Confidence | Reason |",
              "|---|---|---|---|---|"]
    lines += [f"| {cell(name)} | {cell(endpoint_label(p) if resolved(p) else 'UNKNOWN')} | "
              f"{cell(', '.join(p['alternatives']))} | {cell(p['confidence'])} | {cell(p['reason'])} |"
              for name, p, _ in points]
    lines += ["", "## Model-reported issues", ""]
    lines += [f"- {cell(issue)}" for issue in candidate["issues"]] or ["- None reported."]
    lines += ["", "## Required review", ""]
    lines += [f"- {cell(issue)}" for issue in unresolved] or ["- No schema review items remain."]
    lines += ["", "## Export status", "",
              "BLOCKED: unresolved review items remain." if unresolved
              else "Review complete; electrical correctness still requires reasoning/measurement checks.", "",
              "Do not mark connections confirmed solely because a model proposed them. "
              "Compare to the physical board or an independently annotated closeup. "
              "Hidden connections and unreadable labels require additional evidence.", ""]
    return "\n".join(lines)
