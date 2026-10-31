"""Android 1.1 wire contract, translated into the established workflow commands."""
from copy import deepcopy
from typing import Annotated, Literal, Union
from uuid import UUID
from pydantic import Field, create_model, field_validator
from . import models


class CreateSession(models.Strict):
    experiment_id: str = Field(min_length=1,max_length=100)
    experiment_version: str | None = Field(default=None,min_length=1,max_length=100)
    description: str = Field(min_length=1,max_length=2000)

    @field_validator('description')
    @classmethod
    def nonblank(cls,value):
        if not value.strip():raise ValueError('Description cannot be blank')
        return value.strip()


COMMANDS=(models.CorrectEndpoint,models.ReplaceCandidate,models.ConfirmCandidate,
          models.Correspondence,models.Measurements,models.SourceSettings,
          models.Message,models.CheckResult,models.CloseSession,models.Retry)
wrappers=[]
for command in COMMANDS:
    fields={name:(field.annotation,deepcopy(field)) for name,field in command.model_fields.items()
            if name not in ('event_id','expected_version','type')}
    if command is models.SourceSettings:
        fields['sources']=(dict[str,dict[str,Annotated[float,Field(strict=True,allow_inf_nan=False)]]],...)
    payload=create_model(command.__name__+'Payload',__base__=models.Strict,**fields)
    wrappers.append(create_model(command.__name__+'Event',__base__=models.Strict,
        event_id=(UUID,...),expected_session_version=(Annotated[int,Field(ge=1,strict=True)],...),
        type=(command.model_fields['type'].annotation,...),payload=(payload,...)))

AndroidEvent=Annotated[Union[tuple(wrappers)],Field(discriminator='type')]
command_by_type={command.model_fields['type'].annotation.__args__[0]:command for command in COMMANDS}


def internal_event(event):
    return command_by_type[event.type].model_validate({
        'event_id':event.event_id,'expected_version':event.expected_session_version,
        'type':event.type,**event.payload.model_dump()})


class SessionSnapshot(models.SessionResponse):
    api_version: Literal['1.1']='1.1'
    version: int = Field(alias='session_version')


def snapshot(response):
    result=deepcopy(response)
    result['api_version']='1.1'
    result['session_version']=result.pop('version')
    if result['state']=='completed':result['state']='closed'
    return result
