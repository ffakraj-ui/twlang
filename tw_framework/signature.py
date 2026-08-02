from __future__ import annotations

import json
from typing import Any

from .common import content_hash

TW_SIGNATURE_SALT = "TW-FRAMEWORK-V1"


def compute_tw_signature(program: Any, *, length: int = 16) -> str:
    """
    किसी भी TW program (AST या IR, दोनों में .to_dict() होता है) का
    deterministic fingerprint निकालता है।

    यह कोई गुप्त secret नहीं है — कोई भी जिसके पास वही `.tw` source और
    वही TW framework version है, वो यही signature दोबारा बना सकता है।
    यही तो इसका मकसद है: इससे कोई भी `tw verify` चलाकर स्वतंत्र रूप से
    यह पुष्टि कर सकता है कि दिया गया HTML असल में किसी specific TW source
    को compile करने से आया है, न कि कोई हाथ से लिखा हुआ HTML जो सिर्फ
    "TW से बना है" का दावा करता है।
    """
    try:
        payload = program.to_dict()
    except Exception:
        payload = {"repr": repr(program)}
    serialized = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    return content_hash(f"{TW_SIGNATURE_SALT}::{serialized}", length=length)


def build_signature_banner(signature: str, *, title: str = "") -> str:
    safe_title = (title or "").replace("-->", "-- >")
    return (
        f"<!-- Built with TW Framework (https://github.com/ffakraj-ui/twlang) "
        f"- tw-signature:{signature} -->"
    )


def build_signature_meta_tag(signature: str) -> str:
    return (
        f'<meta name="generator" content="TW Framework">\n'
        f'<meta name="tw-signature" content="{signature}">'
    )


__all__ = [
    "compute_tw_signature",
    "build_signature_banner",
    "build_signature_meta_tag",
    "TW_SIGNATURE_SALT",
]
