"""Tests for tw/form advanced form system."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tw_framework.tw_form.form import Form, Field, Validator
from tw_framework.tw_form.validation import parse_validation_rules, validate_field


class TestValidationRules:
    def test_parse_required(self):
        rules = parse_validation_rules("required")
        assert len(rules) == 1
        assert rules[0]["name"] == "required"

    def test_parse_multiple_rules(self):
        rules = parse_validation_rules("required|email|min:5")
        assert len(rules) == 3
        assert rules[0]["name"] == "required"
        assert rules[1]["name"] == "email"
        assert rules[2]["name"] == "min"
        assert rules[2]["arg"] == "5"

    def test_parse_empty(self):
        rules = parse_validation_rules("")
        assert len(rules) == 0


class TestValidateField:
    def test_required_pass(self):
        assert validate_field("hello", "required") is None

    def test_required_fail(self):
        assert validate_field("", "required") is not None

    def test_email_pass(self):
        assert validate_field("user@example.com", "email") is None

    def test_email_fail(self):
        assert validate_field("not-an-email", "email") is not None

    def test_min_length_pass(self):
        assert validate_field("hello", "min:3") is None

    def test_min_length_fail(self):
        assert validate_field("hi", "min:3") is not None

    def test_max_length_pass(self):
        assert validate_field("hi", "max:10") is None

    def test_max_length_fail(self):
        assert validate_field("this is too long", "max:5") is not None

    def test_pattern_pass(self):
        assert validate_field("abc123", "pattern:[a-z0-9]+") is None

    def test_pattern_fail(self):
        assert validate_field("ABC!", "pattern:[a-z0-9]+") is not None

    def test_url_pass(self):
        assert validate_field("https://example.com", "url") is None

    def test_url_fail(self):
        assert validate_field("not-a-url", "url") is not None

    def test_number_pass(self):
        assert validate_field("42", "number") is None

    def test_number_fail(self):
        assert validate_field("abc", "number") is not None

    def test_combined_rules(self):
        error = validate_field("", "required|email|min:5")
        assert error is not None  # Required fails first

    def test_combined_rules_pass(self):
        error = validate_field("user@example.com", "required|email")
        assert error is None


class TestForm:
    def test_create_form(self):
        form = Form(name="contact", action="/api/contact")
        assert form.name == "contact"
        assert form.action == "/api/contact"

    def test_add_field(self):
        form = Form(name="contact")
        form.add_field(Field(name="email", type="email", required=True))
        assert len(form.fields) == 1
        assert form.values["email"] == ""

    def test_set_value(self):
        form = Form(name="contact")
        form.add_field(Field(name="email"))
        form.set_value("email", "user@example.com")
        assert form.values["email"] == "user@example.com"
        assert form.dirty["email"] is True

    def test_validate_empty_required(self):
        form = Form(name="contact")
        form.add_field(Field(name="email", required=True))
        assert form.validate() is False
        assert "email" in form.errors

    def test_validate_valid_form(self):
        form = Form(name="contact")
        form.add_field(Field(name="email", required=True))
        form.set_value("email", "user@example.com")
        assert form.validate() is True
        assert len(form.errors) == 0

    def test_reset(self):
        form = Form(name="contact")
        form.add_field(Field(name="email", default_value=""))
        form.set_value("email", "test@test.com")
        form.reset()
        assert form.values["email"] == ""
        assert len(form.errors) == 0

    def test_multi_step(self):
        form = Form(name="wizard", total_steps=3)
        assert form.step == 0
        form.next_step()
        assert form.step == 1
        form.prev_step()
        assert form.step == 0

    def test_to_client_config(self):
        form = Form(name="contact", action="/api/contact", method="POST")
        form.add_field(Field(name="email", type="email", required=True))
        config = form.to_client_config()
        assert config["name"] == "contact"
        assert config["action"] == "/api/contact"
        assert len(config["fields"]) == 1


class TestFormRuntime:
    def test_get_form_runtime_js(self):
        from tw_framework.tw_form.runtime import get_form_runtime_js
        js = get_form_runtime_js()
        assert "__tw.form" in js
        assert "register" in js
        assert "validate" in js
        assert "submit" in js
