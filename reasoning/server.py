"""Local integration server. Bind localhost; deploy behind authenticated gateway."""
import json
import math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .api import diagnose_input
from .validation import ValidationError
from .spice import find_ngspice
from .registry import capabilities


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
        if self.path == "/capabilities":
            return self.reply(200, {"status":"ok", "analyses":["analog_ac_magnitude", "7400_as_not", "analog_from_vision"],
                                    "ngspice_available":bool(find_ngspice()), "vision_extraction_called":False,
                                    "generalized": capabilities(), "request_versions": ["1.0", "2.0"]})
        self.reply(200 if self.path == "/health" else 404,
                   {"status": "ok"} if self.path == "/health" else {"error": "not_found"})

    def do_POST(self):
        try:
            if self.headers.get("Transfer-Encoding"):
                return self.reply(400, {"error":"unsupported_transfer_encoding"})
            if len(self.headers.get_all("Content-Length", [])) != 1:
                return self.reply(400, {"error":"content_length_required"})
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 262144:
                return self.reply(413, {"error": "body_limit_256KiB"})
            self.connection.settimeout(10)
            data = self.rfile.read(size)
            if self.path != "/v1/diagnose":
                return self.reply(404, {"error": "not_found"})
            request = strict_json(data)
            self.reply(200, diagnose_input(request))
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
