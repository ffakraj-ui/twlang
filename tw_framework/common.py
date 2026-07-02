import hashlib
import sys


def content_hash(value, *, length=None):
    if isinstance(value, str):
        payload = value.encode("utf-8")
    elif isinstance(value, bytes):
        payload = value
    else:
        payload = str(value).encode("utf-8")
    digest = hashlib.md5(payload).hexdigest()
    if length is not None:
        return digest[: max(0, int(length))]
    return digest


def log(message, level="info", file=None):
    stream = file
    if stream is None:
        stream = sys.stderr if str(level).lower() in {"warning", "error"} else sys.stdout
    print(message, file=stream)
