"""Private bounded video subprocess. No raw provider failures on stdout/stderr."""
import json
from pathlib import Path
import sys
from labvision.core import CandidateError


def main():
    try:
        request=json.loads(sys.stdin.read(262145))
        from labvision.video_upload import process_video
        result=process_video(request['path'],request['board'],known_parts=request['known_parts'],
                             try_vision=request['try_vision'])
        directory=Path(request['output'])
        for frame in result['frames']:
            (directory/(frame['id']+'.jpg')).write_bytes(frame.pop('jpeg_bytes'))
        (directory/'result.json').write_text(json.dumps(result,allow_nan=False))
        return 0
    except ImportError:
        return 3
    except CandidateError:
        return 2
    except Exception:
        return 1


if __name__=='__main__':raise SystemExit(main())
