"""FastAPI upload smoke test. Images are validated then discarded."""
from hashlib import sha256
from io import BytesIO
from typing import Annotated, Literal
from uuid import uuid4
import warnings

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 20_000_000


class ImageReceipt(BaseModel):
    content_type: str
    size_bytes: int
    sha256: str
    width: int
    height: int


class StubResponse(BaseModel):
    request_id: str
    mode: Literal['stub'] = 'stub'
    status: Literal['connection_ok'] = 'connection_ok'
    experiment_id: str
    description: str
    image: ImageReceipt
    message: str
    ml1: dict = Field(default_factory=dict)
    ml2: dict = Field(default_factory=dict)


app = FastAPI(title='Git-Good Android connection test', version='0.1.0',
              description='Upload connectivity test only. ML1 and ML2 are stubs. No images are retained, no diagnosis is performed.')


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Avoid echoing image/form contents in error responses or logs.
    return JSONResponse(status_code=422, content={'error': 'invalid_request',
        'fields': ['.'.join(str(x) for x in e['loc']) for e in exc.errors()]})


@app.get('/health')
def health():
    return {'status': 'ok', 'mode': 'stub', 'service': 'android-connection-test'}


@app.post('/api/sessions', response_model=StubResponse, status_code=200,
          responses={413: {'description': 'Image exceeds 5 MiB'},
                     415: {'description': 'Unsupported or invalid image'},
                     422: {'description': 'Missing or invalid form fields'}})
async def upload(
    experiment_id: Annotated[str, Form(min_length=1, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')],
    description: Annotated[str, Form(min_length=1, max_length=2000)],
    image: Annotated[UploadFile, File(description='A JPEG or PNG image, up to 5 MiB')],
):
    try:
        if not description.strip():
            raise HTTPException(422, detail='description cannot be blank')
        if image.content_type not in {'image/jpeg', 'image/png'}:
            raise HTTPException(415, detail='JPEG or PNG required')
        data = await image.read(MAX_IMAGE_BYTES + 1)
        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(413, detail='Image exceeds 5 MiB')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(BytesIO(data)) as picture:
                    expected = {'JPEG': 'image/jpeg', 'PNG': 'image/png'}.get(picture.format)
                    if expected != image.content_type:
                        raise HTTPException(415, detail='Image content does not match JPEG/PNG content type')
                    width, height = picture.size
                    if width * height > MAX_PIXELS:
                        raise HTTPException(413, detail='Image exceeds 20 megapixels')
                    picture.verify()
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError,
                Image.DecompressionBombWarning, Image.DecompressionBombError):
            raise HTTPException(415, detail='Image could not be validated') from None
        return StubResponse(
            request_id=str(uuid4()), experiment_id=experiment_id, description=description.strip(),
            image=ImageReceipt(content_type=image.content_type, size_bytes=len(data),
                               sha256=sha256(data).hexdigest(), width=width, height=height),
            message='Upload received. Android and backend are connected. ML1/ML2 are stubs; no circuit diagnosis was performed.',
            ml1={'mode': 'stub', 'status': 'not_run', 'components': [], 'connections': []},
            ml2={'mode': 'stub', 'status': 'not_run', 'diagnosis': None},
        )
    finally:
        await image.close()
