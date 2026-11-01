"""Small deterministic MP4 fixtures; no user media or external model calls."""
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory
import cv2
import numpy as np


@lru_cache(maxsize=2)
def mp4_bytes(large=False):
    width,height,count=(320,240,64) if large else (64,48,12)
    with TemporaryDirectory() as directory:
        path=Path(directory)/'synthetic.mp4'
        writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),10,(width,height))
        if not writer.isOpened():raise RuntimeError('MP4 test writer unavailable')
        random=np.random.default_rng(42)
        for i in range(count):
            frame=random.integers(0,256,(height,width,3),dtype=np.uint8) if large else np.full((height,width,3),i*15,dtype=np.uint8)
            writer.write(frame)
        writer.release()
        return path.read_bytes()
