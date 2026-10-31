"""Local integration server. Bind localhost; deploy behind authenticated gateway."""
import json
import math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .engine import diagnose
from .validation import ValidationError


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("non-finite JSON constant")

    def real(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("non-finite JSON number")
        return result

    return json.loads(data, object_pairs_hook=pairs, parse_constant=constant, parse_float=real)


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, payload):
        body = json.dumps(payload, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.reply(200 if self.path == "/health" else 404,
                   {"status": "ok"} if self.path == "/health" else {"error": "not_found"})

    def do_POST(self):
        if self.path != "/v1/diagnose":
            return self.reply(404, {"error": "not_found"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 262144:
                return self.reply(413, {"error": "body_limit_256KiB"})
            self.connection.settimeout(10)
            request = strict_json(self.rfile.read(size))
            self.reply(200, diagnose(request))
        except ValidationError as exc:
            self.reply(400, {"error": "invalid_request", "code": exc.code,
                             "path": exc.path, "detail": exc.detail})
        except (ValueError, KeyError, TypeError, AttributeError, RecursionError) as exc:
            self.reply(400, {"error": "invalid_request", "code": "malformed_request",
                             "path": "$", "detail": str(exc)})
        except TimeoutError:
            self.reply(408, {"error": "request_timeout"})


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
