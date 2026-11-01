"""Private streaming MP4 staging; filenames and original video never go in snapshots."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from uuid import uuid4
from fastapi import HTTPException

MAX_VIDEO_BYTES=50*1024*1024


def video_path(directory,asset_id):
    if not isinstance(asset_id,str) or not re.fullmatch('[0-9a-f]{32}',asset_id):
        raise ValueError('Invalid private video asset')
    root=(Path(directory)/'video-sources').resolve()
    target=(root/(asset_id+'.mp4')).resolve()
    if target.parent!=root:raise ValueError('Invalid private video path')
    return target


@dataclass
class StagedVideo:
    directory:Path
    asset_id:str
    receipt:dict

    @property
    def path(self):return video_path(self.directory,self.asset_id)

    def discard(self):self.path.unlink(missing_ok=True)


def stage_video(stream,directory):
    asset_id=uuid4().hex
    path=video_path(directory,asset_id);path.parent.mkdir(parents=True,exist_ok=True)
    size=0;digest=sha256();header=b''
    try:
        stream.seek(0)
        with path.open('xb') as target:
            for block in iter(lambda:stream.read(1024*1024),b''):
                size+=len(block)
                if size>MAX_VIDEO_BYTES:raise HTTPException(413,'Video exceeds 50 MiB')
                if len(header)<32:header=(header+block)[:32]
                digest.update(block);target.write(block)
        if size<16 or header[4:8]!=b'ftyp':raise HTTPException(415,'An MP4 video is required')
        return StagedVideo(Path(directory),asset_id,{'content_type':'video/mp4','size_bytes':size,'sha256':digest.hexdigest()})
    except Exception:
        path.unlink(missing_ok=True)
        raise
