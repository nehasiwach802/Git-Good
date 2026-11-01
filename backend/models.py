"""Versioned Android event and response contract."""
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
import math


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class EventBase(Strict):
    event_id: UUID
    expected_version: int = Field(ge=1, strict=True)


class CorrectEndpoint(EventBase):
    type: Literal['correct_endpoint']
    candidate_revision: int = Field(ge=1, strict=True)
    target: str = Field(min_length=1, max_length=100)
    hole: str | None = Field(default=None, max_length=100)
    external_terminal: str | None = Field(default=None, max_length=100)


class ReplaceCandidate(EventBase):
    type: Literal['replace_candidate']
    candidate_revision: int = Field(ge=1, strict=True)
    candidate: dict


class ConfirmCandidate(EventBase):
    type: Literal['confirm_candidate']
    candidate_revision: int = Field(ge=1, strict=True)
    acknowledgement: Literal['reviewed_all_connections_and_board']


class Correspondence(EventBase):
    type: Literal['set_correspondence']
    component_map: dict[str, str | None]
    port_map: dict[str, str] = Field(default_factory=dict)


class Measurements(EventBase):
    type: Literal['measurements']
    candidate_revision: int = Field(ge=1, strict=True)
    measurements: list[dict] = Field(max_length=20)
    student_expectations: dict | list = Field(default_factory=dict)


class SourceSettings(EventBase):
    type: Literal['source_settings']
    candidate_revision: int = Field(ge=1, strict=True)
    sources: dict[str, dict[str, float]]

    @field_validator('sources',mode='before')
    @classmethod
    def finite_sources(cls,value):
        if not isinstance(value,dict) or any(not isinstance(v,dict) or any(type(x) not in (int,float) or not math.isfinite(x) for x in v.values()) for v in value.values()):
            raise ValueError('Source settings must be finite numbers')
        return value


class Message(EventBase):
    type: Literal['message']
    text: str = Field(min_length=1, max_length=2000)


class CheckResult(EventBase):
    type: Literal['check_result']
    check_id: str = Field(min_length=1, max_length=100)
    observation: str = Field(min_length=1, max_length=2000)


class Complete(EventBase):
    type: Literal['complete']
    resolved: bool = Field(strict=True)


class Retry(EventBase):
    type: Literal['retry_extraction']


class CloseSession(EventBase):
    type: Literal['close_session']
    resolved: bool = Field(default=False,strict=True)


NativeXY = Annotated[list[Annotated[float,Field(strict=True,allow_inf_nan=False)]],Field(min_length=2,max_length=2)]


class GridBinding(Strict):
    candidate_revision: int = Field(ge=1,strict=True)
    frame_id: str = Field(pattern=r'^F[1-6]$')
    image_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    board_fingerprint: str = Field(pattern=r'^[0-9a-f]{64}$')


class AcceptGrid(EventBase,GridBinding):
    type: Literal['accept_grid']
    left_top: str = Field(pattern=r'^[AEFJ][1-9][0-9]?$')
    right_top: str = Field(pattern=r'^[AEFJ][1-9][0-9]?$')
    acknowledgement: Literal['reviewed_grid_alignment_and_printed_labels']


class RejectGrid(EventBase,GridBinding):
    type: Literal['reject_grid']


class TapEndpoint(EventBase,GridBinding):
    type: Literal['tap_endpoint']
    target: str = Field(min_length=1,max_length=100)
    xy: NativeXY


class AddWire(EventBase,GridBinding):
    type: Literal['add_wire']
    wire_id: str = Field(pattern=r'^[A-Za-z][A-Za-z0-9_-]{0,63}$')
    a_xy: NativeXY
    b_xy: NativeXY
    acknowledgement: Literal['reviewed_same_physical_wire']


class RemoveWire(EventBase):
    type: Literal['remove_wire']
    candidate_revision: int = Field(ge=1,strict=True)
    wire_id: str = Field(pattern=r'^[A-Za-z][A-Za-z0-9_-]{0,63}$')


class GridSuggestionRequest(GridBinding):
    expected_session_version: int = Field(ge=1,strict=True)
    xy: NativeXY


class GridSuggestionResponse(GridBinding):
    session_version: int
    suggestion: dict


SessionEvent = Annotated[CorrectEndpoint | ReplaceCandidate | ConfirmCandidate | Correspondence |
                         Measurements | SourceSettings | Message | CheckResult | Complete | Retry,
                         Field(discriminator='type')]


class SessionResponse(BaseModel):
    api_version: Literal['1.0'] = '1.0'
    session_id: str
    version: int
    state: Literal['awaiting_image','extracting','awaiting_review','diagnosing','awaiting_measurement','awaiting_check_result','completing','completed','closed','failed']
    experiment_id: str
    experiment_version: str
    description: str
    candidate_revision: int | None
    candidate: dict | None
    board: dict
    image: dict | None
    messages: list[dict]
    actions: list[dict]
    diagnostic: dict | None
    explanation: dict | None
    ml1: dict
    ml3: dict
    error: dict | None
    simulated: bool
    memory_available: bool
    job_id: str | None
