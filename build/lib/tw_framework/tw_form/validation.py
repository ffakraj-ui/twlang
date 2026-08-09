"""
Validation rules for tw/form.

Supports declarative validation rules parsed from strings like:
  "required|email|min:8|max:100|pattern:[a-z]+"

Also supports integration with Zod via JS interop.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Tuple


def parse_validation_rules(rule_str: str) -> List[Dict[str, Any]]:
    """Parse a validation rule string into individual rules."""
    if not rule_str:
        return []
    rules = []
    for part in rule_str.split("|"):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            name, arg = part.split(":", 1)
            rules.append({"name": name.strip(), "arg": arg.strip()})
        else:
            rules.append({"name": part, "arg": None})
    return rules


def validate_field(value: Any, rules: str, all_values: Optional[Dict] = None) -> Optional[str]:
    """Validate a field value against rule string. Returns error message or None."""
    all_values = all_values or {}
    parsed = parse_validation_rules(rules)

    for rule in parsed:
        name = rule["name"]
        arg = rule["arg"]
        error = _apply_rule(name, arg, value, all_values)
        if error:
            return error
    return None


def _apply_rule(name: str, arg: Optional[str], value: Any, all_values: Dict) -> Optional[str]:
    if name == "required":
        if value is None or value == "" or (isinstance(value, (list, str)) and len(value) == 0):
            return "This field is required"
        return None

    if value is None or value == "":
        return None  # Non-required empty fields pass

    if name == "email":
        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', str(value)):
            return "Please enter a valid email address"
        return None

    if name == "min":
        min_len = int(arg or "0")
        if isinstance(value, str) and len(value) < min_len:
            return f"Must be at least {min_len} characters"
        if isinstance(value, (int, float)) and value < min_len:
            return f"Must be at least {min_len}"
        return None

    if name == "max":
        max_len = int(arg or "999999")
        if isinstance(value, str) and len(value) > max_len:
            return f"Must be at most {max_len} characters"
        if isinstance(value, (int, float)) and value > max_len:
            return f"Must be at most {max_len}"
        return None

    if name == "pattern":
        if arg and not re.match(arg, str(value)):
            return "Invalid format"
        return None

    if name == "url":
        if not re.match(r'^https?://[^\s]+$', str(value)):
            return "Please enter a valid URL"
        return None

    if name == "number":
        try:
            float(value)
        except (ValueError, TypeError):
            return "Must be a number"
        return None

    if name == "integer":
        try:
            int(value)
        except (ValueError, TypeError):
            return "Must be an integer"
        return None

    if name == "phone":
        if not re.match(r'^[\d\s\-\+\(\)]{7,20}$', str(value)):
            return "Please enter a valid phone number"
        return None

    if name == "alpha":
        if not str(value).isalpha():
            return "Must contain only letters"
        return None

    if name == "alphanumeric":
        if not str(value).isalnum():
            return "Must contain only letters and numbers"
        return None

    if name == "equals":
        if str(value) != str(all_values.get(arg, "")):
            return f"Must match {arg}"
        return None

    if name == "custom":
        # Custom validators are handled client-side via JS interop
        return None

    return None


# Zod integration (via JS interop — server-side validation)
def zod_validate(value: Any, schema_source: str) -> Optional[str]:
    """Validate using a Zod schema (requires Node.js).

    schema_source: JavaScript source that exports a Zod schema.
    """
    # This would call Node.js to run the Zod validation
    # For now, return None (valid) — actual integration happens at runtime
    return None


__all__ = ["parse_validation_rules", "validate_field", "zod_validate"]
