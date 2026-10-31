"""Declared model/analysis capabilities, independent of experiment names."""
from dataclasses import dataclass
from types import MappingProxyType

REGISTRY_VERSION = "1"


@dataclass(frozen=True)
class Model:
    pins: tuple[str, ...]
    properties: tuple[str, ...] = ()
    interchangeable: bool = False
    analyses: tuple[str, ...] = ("connectivity",)


MODELS = MappingProxyType({
    "R": Model(("1", "2"), ("value",), True, ("connectivity", "analog_ac")),
    "C": Model(("1", "2"), ("value",), True, ("connectivity", "analog_ac")),
    "V": Model(("+", "-"), ("dc", "ac"), False, ("connectivity", "analog_ac")),
    "OPAMP": Model(("+", "-", "out", "vcc", "vee"), ("gain",), False,
                   ("connectivity", "analog_ac")),
    "7400": Model(tuple(str(i) for i in range(1, 15)), (), False,
                  ("connectivity", "7400_as_not")),
})

ANALYSES = MappingProxyType({
    "connectivity": "Connectivity comparison only; no behavioral prediction",
    "analog_ac": "Single-frequency AC magnitude; ideal small-signal models",
    "7400_as_not": "Isolated 7400 NAND-as-NOT; ideal Boolean logic only",
})


def capabilities():
    return {"registry_version": REGISTRY_VERSION,
            "models": {name: {"pins": list(m.pins), "required_properties": list(m.properties),
                              "interchangeable_terminals": m.interchangeable,
                              "analyses": list(m.analyses)} for name, m in MODELS.items()},
            "analyses": dict(ANALYSES)}
