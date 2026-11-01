"""Bound streamed and Content-Length bodies before form/JSON parsing."""
from fastapi.responses import JSONResponse


class BodyLimit:
    def __init__(self,app):self.app=app

    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope['method'] not in ('POST','PUT','PATCH'):
            return await self.app(scope,receive,send)
        import re
        upload=scope['path'] in ('/api/sessions','/api/legacy/v1/sessions') or re.fullmatch(r'/api/v1/sessions/[0-9a-fA-F-]{36}/image',scope['path'])
        legacy=scope['path'] in ('/api/sessions','/api/legacy/v1/sessions')
        limit=(6 if legacy else 51)*1024*1024 if upload else 512*1024
        if upload:
            headers=dict(scope.get('headers',[]))
            try:length=int(headers.get(b'content-length',b'0'))
            except ValueError:
                return await JSONResponse({'error':'invalid_content_length'},status_code=400)(scope,receive,send)
            if length>limit:
                return await JSONResponse({'error':'request_too_large'},status_code=413)(scope,receive,send)
            size=0
            async def limited_receive():
                nonlocal size
                part=await receive()
                size+=len(part.get('body',b''))
                if size>limit:
                    from fastapi import HTTPException
                    raise HTTPException(413,'Request exceeds upload limit')
                return part
            return await self.app(scope,limited_receive,send)
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
