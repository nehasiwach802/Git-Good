"""ML1 candidate -> reviewed connectivity -> explicitly selected analysis.

No extraction API is called here, and this module never grants human review.
"""
from copy import deepcopy
from labvision.core import CandidateError, compile_netlist, pending, validate
from labvision.digital import check_not
from .checks import finish, stable_id
from .engine import diagnose
from .handoff import prepare_reasoning_request
from .validation import ValidationError, validate_request
from .circuit import number, token
from .spice import simulate


def fail(path, message):
    raise ValidationError(path, message)


def validate_vision_request(request):
    if not isinstance(request, dict) or request.get("schema_version") != "1.0":
        fail("$.schema_version", "requires reasoning envelope 1.0")
    if not isinstance(request.get("analysis"), str) or request["analysis"] not in {"7400_as_not", "analog_from_vision"}:
        fail("$.analysis", "choose 7400_as_not or analog_from_vision")
    candidate, board = request.get("candidate"), request.get("board")
    if not isinstance(candidate, dict) or not isinstance(board, dict):
        fail("$.candidate", "candidate and board must be objects")
    # Bound work before calling the upstream compiler, including unused groups.
    for obj, field, maximum in ((candidate,"components",100),(candidate,"wires",1000),
                                 (candidate,"ports",100),(candidate,"issues",100),
                                 (board,"groups",1000)):
        if not isinstance(obj.get(field), list) or len(obj[field]) > maximum:
            fail("$." + field, f"requires an array of at most {maximum} items")
    if any(not isinstance(group,list) or len(group)>100 for group in board["groups"]):
        fail("$.board.groups", "board groups must have at most 100 holes")
    try:
        validate(candidate, board)
    except (CandidateError, KeyError, TypeError, AttributeError, OverflowError) as exc:
        fail("$.candidate", str(exc))
    if request["analysis"] == "7400_as_not":
        gate = request.get("gate", 1)
        if type(gate) is not int or not 1 <= gate <= 4:
            fail("$.gate", "requires integer gate 1..4")
        component = request.get("component_id", "U1")
        if not isinstance(component,str) or not any(c["id"]==component and c["part"]=="7400" for c in candidate["components"]):
            fail("$.component_id", "select an observed 7400 component")
        for field in ("measurements", "student_expectations"):
            rows=request.get(field, [])
            if not isinstance(rows,list) or len(rows)>2:
                fail("$."+field, "requires at most two binary truth-table rows")
            seen=set()
            for row in rows:
                if (not isinstance(row,dict) or set(row)!={"input","output"}
                        or any(type(row[k]) is not int or row[k] not in (0,1) for k in ("input","output"))):
                    fail("$."+field, "rows require integer input and output, each 0 or 1; voltages are not binary observations")
                if row["input"] in seen:
                    fail("$."+field, "duplicate input condition")
                seen.add(row["input"])
    else:
        # Validate configuration even while candidate review is pending. Dummy
        # student circuit validates reference/probes independently of conversion.
        try:
            validate_request({"schema_version":"1.0", "experiment":request["experiment"],
                              "student_circuit":request["experiment"]["circuit"],
                              "measurements":request.get("measurements",[]),
                              "student_expectations":request.get("student_expectations",{})})
        except (KeyError, TypeError):
            fail("$.experiment", "requires an analog experiment")
        if not isinstance(request.get("component_id_map",{}), dict):
            fail("$.component_id_map", "requires an object")
        ports={p["id"] for p in candidate["ports"]}
        ground=request.get("ground_port")
        if not isinstance(ground,str) or not any(p["id"]==ground and p["role"]=="gnd" for p in candidate["ports"]):
            fail("$.ground_port", "select an observed ground port explicitly")
        sources=request.get("voltage_sources")
        if not isinstance(sources,list) or not 1<=len(sources)<=10:
            fail("$.voltage_sources", "requires 1..10 explicitly configured sources")
        for s in sources:
            if not isinstance(s,dict): fail("$.voltage_sources", "sources must be objects")
            try:
                token(s["id"])
                if s["positive_port"] not in ports or s["negative_port"] not in ports:
                    raise ValueError("unknown source port")
                number(s.get("dc",0),"dc")
                number(s.get("ac",0),"ac")
            except (KeyError,TypeError,ValueError): fail("$.voltage_sources", "invalid source ID, ports or values")
        mappings=request.get("probe_ports")
        expected={p["id"] for p in request["experiment"]["probes"]}
        if not isinstance(mappings,dict) or set(mappings)!=expected:
            fail("$.probe_ports", "explicit mapping required for every analog probe")
        for mapping in mappings.values():
            if (not isinstance(mapping,dict) or set(mapping)!={"positive","negative"}
                    or not all(isinstance(n,str) and n in ports for n in mapping.values())):
                fail("$.probe_ports", "positive and negative must name observed ports")
    return request


def analog_request(request, netlist):
    ports={p["id"]:p["node"] for p in netlist["ports"]}
    ground=ports[request["ground_port"]]
    def net(name):
        return "0" if name==ground else name
    components=[]
    for c in netlist["components"]:
        if c["part"] not in {"resistor","capacitor"}:
            raise ValidationError("$.candidate.components", "analog conversion supports reviewed resistor/capacitor parts only", "unsupported_component_model")
        components.append({"id":c["id"], "type":{"resistor":"R","capacitor":"C"}[c["part"]],
                           "value":c["value_si"], "pins":{p:net(n) for p,n in c["pins"].items()}, "confirmed":True})
    for s in request["voltage_sources"]:
        components.append({"id":s["id"],"type":"V", "dc":s.get("dc",0),"ac":s.get("ac",0),
                           "pins":{"+":net(ports[s["positive_port"]]),"-":net(ports[s["negative_port"]])},"confirmed":True})
    result={"schema_version":"1.0", "safety_profile":request.get("safety_profile"),
            "experiment":deepcopy(request["experiment"]), "student_circuit":{"components":components},
            "measurements":deepcopy(request.get("measurements",[])),
            "student_expectations":deepcopy(request.get("student_expectations",{})),
            "student_probe_nodes":{pid:{p:net(ports[port]) for p,port in nodes.items()} for pid,nodes in request["probe_ports"].items()},
            "source_context":{"board_id":netlist["board_profile_id"], "candidate_revision":netlist["revision"],"reviewed_revision":netlist["revision"]}}
    return prepare_reasoning_request(result, component_id_map=request.get("component_id_map",{}))


def diagnose_vision(request, simulator=simulate):
    validate_vision_request(request)
    candidate, board = request["candidate"],request["board"]
    result={"schema_version":"1.0","findings":[],"predictions":[],
            "hypotheses":{k:{"support":"unresolved","evidence_ids":[]} for k in ("wiring","concept","apparatus")},
            "vision_source":{"candidate_id":candidate["candidate_id"],"revision":candidate["revision"],
                             "reviewed_revision":candidate["reviewed_revision"],"board_profile_id":board["id"]},
            "limitations":["Review is not proof of correct wiring, safe hardware or device health.",
                           "Digital analysis is isolated 7400 NAND-as-NOT ideal Boolean logic; no voltage/timing prediction."]}
    if request.get("safety_profile")!="instructor_approved_low_voltage":
        result.update(status="instructor_required",next_check={"kind":"instructor_review","reason":"Approved low-voltage workflow required"})
        return finish(result)
    unresolved=pending(candidate,board)
    if unresolved:
        result.update(status="needs_confirmation",pending=unresolved,
                      next_check={"kind":"confirm_connections","reason":"Review ML1 candidate, board, values and omissions before analysis"})
        return finish(result)
    exported=compile_netlist(candidate,board)
    if request["analysis"]=="analog_from_vision":
        result=diagnose(analog_request(request,exported), simulator)
        result["vision_source"]={"candidate_id":exported["candidate_id"],"revision":exported["revision"],"board_profile_id":board["id"]}
        result["reviewed_connectivity"]=exported
        return result
    if len(exported["components"]) != 1:
        # A valid LED/load can exceed the model without being a wiring fault.
        result["reviewed_connectivity"]=exported
        finding={"kind":"unsupported_analysis_scope",
                 "detail":"Isolated 7400 logic cannot evaluate additional components or loads"}
        result["findings"].append({"id":stable_id("e_",finding),**finding})
        result.update(status="instructor_required",next_check={"kind":"instructor_review",
                      "reason":"Choose a validated model for the observed additional components; no wiring fault established"})
        return finish(result)
    checked=check_not(exported,request.get("component_id","U1"),request.get("gate",1))
    result["logic_check"]=checked
    result["reviewed_connectivity"]=exported
    def evidence(kind, **fields):
        identifier=stable_id("e_",{"kind":kind,**fields})
        result["findings"].append({"id":identifier,"kind":kind,**fields})
        return identifier
    def support(kind,eid):
        result["hypotheses"][kind]["support"]="supported"
        result["hypotheses"][kind]["evidence_ids"].append(eid)
    for issue in checked["issues"]:
        support("wiring",evidence("digital_topology_mismatch",detail=issue))
    for warning in checked["warnings"]:
        evidence("undefined_unused_input",detail=warning)
    if not checked["topology_matches"]:
        check={"kind":"review_wiring","reason":"Reviewed 7400 wiring differs from isolated NAND-as-NOT topology"}
    elif checked["warnings"]:
        check={"kind":"instructor_supervised_setup_check","reason":"Unused inputs need defined states; ideal logic does not establish stable hardware"}
    else:
        result["predictions"]=[{"probe_id":"logic_truth_table","reference":{"status":"ok","truth_table":checked["truth_table"]},
                                "student":{"status":"ok","truth_table":checked["truth_table"]}}]
        mismatches=[]
        expectations={r["input"]:r["output"] for r in request.get("student_expectations",[])}
        for row in request.get("measurements",[]):
            predicted=1-row["input"]
            eid=evidence("digital_measurement_comparison",input=row["input"],predicted=predicted,
                         measured=row["output"],matches=predicted==row["output"])
            if predicted!=row["output"]:
                mismatches.append(eid)
            elif row["input"] in expectations and expectations[row["input"]]!=predicted:
                support("concept",evidence("digital_expectation_disagrees",input=row["input"],expected=expectations[row["input"]],comparison_evidence=eid))
        if mismatches:
            check={"kind":"instructor_supervised_setup_check","reason":"Binary observations disagree with ideal logic; verify supply, input definition, loading and observation", "evidence_ids":mismatches}
        elif len(request.get("measurements",[]))<2:
            check={"kind":"record_approved_measurement","reason":"Record both input conditions as explicit binary observations"}
        elif result["hypotheses"]["concept"]["support"]=="supported":
            check={"kind":"explain_prediction","reason":"Explain NAND with both inputs tied together"}
        else:
            check={"kind":"review_learning_objective","reason":"Both observations agree with the ideal truth table; hardware health remains unverified"}
    result.update(status="evaluated",next_check=check)
    return finish(result)
