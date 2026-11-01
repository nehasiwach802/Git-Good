"""One minimal API-access request; never print credentials or provider error bodies."""

import json
import argparse
import base64
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from labvision.config import gemini_settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", help="optional JPEG/PNG for a minimal vision-access probe")
    parser.add_argument("--out", help="optional local response JSON")
    parser.add_argument("--thinking-level", choices=("low", "medium", "high"))
    args = parser.parse_args()
    settings = gemini_settings()
    key, model = settings["GEMINI_API_KEY"], settings["GEMINI_MODEL"]
    if not key or not re.fullmatch(r"[A-Za-z0-9_.-]+", model):
        print(json.dumps({"ok": False, "error": "missing key or invalid model configuration"}))
        return 2
    parts = [{"text": "Reply with OK."}]
    if args.image:
        image_data = Path(args.image).read_bytes()
        if not 0 < len(image_data) <= 10 * 1024 * 1024:
            print(json.dumps({"ok": False, "error": "image size must be 1 byte to 10 MB"}))
            return 2
        mime = "image/jpeg" if image_data.startswith(b"\xff\xd8\xff") else "image/png"
        parts = [{"text": "In one short sentence, describe the visible electronic components. Do not infer wiring."},
                 {"inline_data": {"mime_type": mime, "data": base64.b64encode(image_data).decode()}}]
    payload = {"contents": [{"parts": parts}],
               "generationConfig": {"maxOutputTokens": 256 if args.image else 32}}
    if args.thinking_level:
        payload["generationConfig"]["thinkingConfig"] = {"thinkingLevel": args.thinking_level.upper()}
    request = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.load(response)
            result = {"ok": True, "http_status": response.status, "model": model,
                      "candidate_received": bool(data.get("candidates"))}
            if args.image and data.get("candidates"):
                result["image_description"] = "".join(
                    part.get("text", "") for part in data["candidates"][0].get("content", {}).get("parts", [])
                    if not part.get("thought"))[:500]
            if args.out:
                target = Path(args.out)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(result))
        return 0
    except urllib.error.HTTPError as exc:
        result = {"ok": False, "http_status": exc.code, "model": model}
        try:
            error = json.loads(exc.read()).get("error", {})
            status = error.get("status", "")
            if re.fullmatch(r"[A-Z_]+", status):
                result["status"] = status
            reasons = [item.get("reason", "") for item in error.get("details", [])
                       if isinstance(item, dict)]
            result["reasons"] = [r for r in reasons if re.fullmatch(r"[A-Z_]+", r)]
        except (ValueError, AttributeError, TypeError):
            pass
        print(json.dumps(result))
        return 1
    except (urllib.error.URLError, TimeoutError) as exc:
        reason = getattr(exc, "reason", exc)
        print(json.dumps({"ok": False, "error": "network_connection_failed",
                          "failure_type": type(reason).__name__}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
