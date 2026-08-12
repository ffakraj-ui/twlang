from typing import Any, Optional

import hashlib
import sys


def content_hash(value, *, length=None) -> Any:
    # FIX #526: Use SHA-256 instead of MD5 for better collision resistance
    if isinstance(value, str):
        payload = value.encode("utf-8")
    elif isinstance(value, bytes):
        payload = value
    else:
        # FIX #531: Handle non-stringable objects gracefully
        try:
            payload = str(value).encode("utf-8")
        except Exception:
            payload = repr(value).encode("utf-8")
    # FIX #538: Handle None explicitly
    if value is None:
        payload = b"__None__"
    digest = hashlib.sha256(payload).hexdigest()
    if length is not None:
        return digest[: max(0, int(length))]
    return digest


def log(message, level="info", file=None) -> None:
    # FIX #530: Add timestamp to log output
    import time as _time
    _ts = _time.strftime("%H:%M:%S")
    stream = file
    if stream is None:
        stream = sys.stderr if str(level).lower() in {"warning", "error"} else sys.stdout
    print(f"[{_ts}] {message}", file=stream)
