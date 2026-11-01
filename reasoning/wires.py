"""Unpowered, reviewed physical wire observations; never infer wires from a reference."""
from labvision.core import board_groups, pending, require, validate
from .checks import finish, stable_id


def validate_reference(reference, board=None):
    require(isinstance(reference, dict), 'wire reference must be an object')
    for key in ('experiment_id', 'version'):
        require(isinstance(reference.get(key), str) and 0 < len(reference[key]) <= 200,
                key + ' required')
    require(reference.get('approval') in ('draft', 'approved'), 'invalid reference approval')
    require(isinstance(reference.get('analysis'), dict) and
            reference['analysis'].get('engine') == 'wire_connections', 'invalid wire engine')
    require(reference.get('ports') == {}, 'wire reference has no external ports')
    circuit = reference.get('circuit')
    require(isinstance(circuit, dict) and circuit.get('components') == [], 'wire reference has no components')
    wires = circuit.get('wires')
    require(isinstance(wires, list) and len(wires) <= 1000, 'reference wires must be a list of at most 1000')
    ids, occupied = set(), set()
    holes = None
    if board is not None:
        require(board.get('capture_mode') == 'wire_connections', 'wire capture mode required')
        holes = board_groups(board)
    for wire in wires:
        require(isinstance(wire, dict), 'reference wire must be an object')
        name = wire.get('id')
        require(isinstance(name, str) and name and name not in ids, 'unique wire ID required')
        ids.add(name)
        for side in ('a', 'b'):
            hole = wire.get(side)
            require(isinstance(hole, str) and hole and hole not in occupied, 'distinct reference holes required')
            require(holes is None or hole in holes, 'reference hole outside board')
            occupied.add(hole)
    return reference


def validate_request(request):
    require(request.get('schema_version') == '2.0', 'wire request requires schema 2.0')
    board = request.get('board')
    require(isinstance(board, dict), 'board required')
    validate_reference(request.get('reference'), board)
    validate(request.get('candidate'), board)
    require(request.get('measurements', []) == [], 'wire exercise requires no electrical readings')
    return request


def diagnose_wires(request):
    validate_request(request)
    candidate, board, reference = request['candidate'], request['board'], request['reference']
    unresolved = pending(candidate, board)
    result = {'schema_version':'2.0', 'status':'needs_confirmation' if unresolved else 'evaluated',
        'reference':{'experiment_id':reference['experiment_id'],'version':reference['version']},
        'observation':{'id':candidate['candidate_id'],'revision':candidate['revision']},
        'pending':unresolved,'capability_gaps':[],
        'findings':[], 'predictions':[],
        'hypotheses':{k:{'support':'unresolved','evidence_ids':[]} for k in ('wiring','concept','apparatus')},
        'limitations':['Unpowered wire placement only; no electrical continuity, contact quality or voltage is measured.'],
        'next_check':{'kind':'confirm_connections' if unresolved else 'review_learning_objective',
            'reason':'Review every wire endpoint and board orientation.' if unresolved else
                     'Explain which breadboard holes each reviewed wire connects; no powered measurement is required.'}}
    if unresolved:
        result['limitations'].extend(unresolved)
        return finish(result)
    groups = board_groups(board)
    observed = {tuple(sorted((w['a']['hole'], w['b']['hole']))) for w in candidate['wires']}
    expected = {tuple(sorted((w['a'], w['b']))) for w in reference['circuit']['wires']}

    def finding(kind, **fields):
        value = {'kind':kind, 'certainty':'confirmed', **fields}
        value['id'] = stable_id('e_', value)
        result['findings'].append(value)
        return value['id']

    for wire in candidate['wires']:
        a, b = wire['a']['hole'], wire['b']['hole']
        finding('reviewed_wire_connection', wire_id=wire['id'], a=a, b=b,
                same_board_strip=groups[a] == groups[b])
    if reference['approval'] != 'approved':
        finding('wire_reference_not_approved', observed_wire_count=len(observed))
        result['limitations'].append('Reference is a draft: observed connections are listed without judging placement correct or incorrect.')
    else:
        for pair in sorted(expected - observed):
            result['hypotheses']['wiring']['evidence_ids'].append(finding('missing_expected_wire', holes=list(pair)))
        for pair in sorted(observed - expected):
            result['hypotheses']['wiring']['evidence_ids'].append(finding('unexpected_wire', holes=list(pair)))
        # Strip equivalence is informative and never substitutes for exact physical placement.
        strip_pairs = lambda pairs: sorted(tuple(sorted((groups[a], groups[b]))) for a, b in pairs)
        finding('wire_placement_comparison', exact_match=observed == expected,
                strip_pairs_match=strip_pairs(observed) == strip_pairs(expected),
                observed_wire_count=len(observed), expected_wire_count=len(expected))
        if observed != expected:
            result['hypotheses']['wiring']['support'] = 'supported'
            result['next_check'] = {'kind':'review_wiring',
                'reason':'With the board unpowered, review the reported missing or unexpected hole pairs against the approved exercise.'}
    return finish(result)
