"""Shared CLI/HTTP dispatch; analog requests retain their existing format."""
from .engine import diagnose
from .validation import validate_request
from .vision import diagnose_vision, validate_vision_request
from .spice import simulate
from .generalized import validate_generalized, diagnose_generalized
from .adapters import adapt_request


def validate_input(request):
    if isinstance(request, dict) and request.get("schema_version") == "2.0":
        return validate_generalized(adapt_request(request))
    if isinstance(request,dict) and "analysis" in request:
        return validate_vision_request(request)
    return validate_request(request)


def diagnose_input(request, simulator=simulate):
    if isinstance(request, dict) and request.get("schema_version") == "2.0":
        return diagnose_generalized(adapt_request(request), simulator)
    if isinstance(request,dict) and "analysis" in request:
        return diagnose_vision(request, simulator)
    return diagnose(request, simulator)
