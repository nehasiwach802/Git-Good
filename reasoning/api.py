"""Shared CLI/HTTP dispatch; analog requests retain their existing format."""
from .engine import diagnose
from .validation import validate_request
from .vision import diagnose_vision, validate_vision_request
from .spice import simulate


def validate_input(request):
    if isinstance(request,dict) and "analysis" in request:
        return validate_vision_request(request)
    return validate_request(request)


def diagnose_input(request, simulator=simulate):
    if isinstance(request,dict) and "analysis" in request:
        return diagnose_vision(request, simulator)
    return diagnose(request, simulator)
