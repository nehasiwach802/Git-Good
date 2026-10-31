"""Bound streamed and Content-Length bodies before form/JSON parsing."""
from fastapi.responses import JSONResponse


class BodyLimit:
    def __init__(self,app):self.app=app

    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope['method'] not in ('POST','PUT','PATCH'):
            return await self.app(scope,receive,send)
        limit=6*1024*1024 if scope['path'] in ('/api/sessions','/api/v1/sessions') else 512*1024
        chunks=[];size=0
        while True:
            part=await receive()
            if part['type']=='http.disconnect':return
            size+=len(part.get('body',b''))
            if size>limit:
                return await JSONResponse({'error':'request_too_large'},status_code=413)(scope,receive,send)
            chunks.append(part.get('body',b''))
            if not part.get('more_body'):break
        sent=False
        headers=dict(scope.get('headers',[]))
        if headers.get(b'content-type',b'').split(b';')[0].strip()==b'application/json':
            from reasoning.server import strict_json
            try:strict_json(b''.join(chunks))
            except (ValueError,RecursionError,OverflowError):
                return await JSONResponse({'error':'invalid_json'},status_code=400)(scope,receive,send)
        async def replay():
            nonlocal sent
            if sent:return await receive()
            sent=True
            return {'type':'http.request','body':b''.join(chunks),'more_body':False}
        await self.app(scope,replay,send)
