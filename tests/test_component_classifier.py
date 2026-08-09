"""Tests for the component classifier."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tw_framework.component_classifier import (
    ComponentClassifier, ComponentClassification, STATIC,
    CLIENT, SERVER,
)


class TestComponentClassification:
    def test_static_component(self):
        c = ComponentClassifier()
        source = """div { class "card" } {
  h1 { "Hello World" }
  p { "This is static content" }
}"""
        result = c.classify("Card", source)
        assert result.classification == STATIC
        assert result.needs_client_js is False

    def test_client_component_with_state(self):
        c = ComponentClassifier()
        source = 'state { count 0 }\nbutton { on:click "count++" } { "{count}" }'
        result = c.classify("Counter", source)
        assert result.classification == CLIENT
        assert result.needs_client_js is True
        assert result.needs_state is True

    def test_client_component_with_events(self):
        c = ComponentClassifier()
        source = 'button { on:click "submit" } { "Submit" }'
        result = c.classify("SubmitButton", source)
        assert result.classification == CLIENT
        assert result.needs_client_js is True

    def test_client_component_with_bind(self):
        c = ComponentClassifier()
        source = 'input { bind:value "name" }'
        result = c.classify("Input", source)
        assert result.classification == CLIENT

    def test_client_component_with_tw_state_import(self):
        c = ComponentClassifier()
        source = 'import { store } from "tw/state"'
        result = c.classify("StateComp", source)
        assert result.classification == CLIENT
        assert result.needs_state is True

    def test_client_component_with_tw_router_import(self):
        c = ComponentClassifier()
        source = 'import { Link } from "tw/router"'
        result = c.classify("NavLink", source)
        assert result.classification == CLIENT
        assert result.needs_router is True

    def test_client_component_with_tw_realtime_import(self):
        c = ComponentClassifier()
        source = 'import { socket } from "tw/realtime"'
        result = c.classify("LiveCounter", source)
        assert result.classification == CLIENT
        assert result.needs_realtime is True

    def test_explicit_static(self):
        c = ComponentClassifier()
        source = 'static true\nbutton { on:click "x" } { "Click" }'
        result = c.classify("ForcedStatic", source)
        assert result.classification == STATIC
        assert result.needs_client_js is False

    def test_explicit_client(self):
        c = ComponentClassifier()
        source = 'client true\nh1 { "Hello" }'
        result = c.classify("ForcedClient", source)
        assert result.classification == CLIENT
        assert result.needs_client_js is True

    def test_classify_page(self):
        c = ComponentClassifier()
        source = """page { title "Home" }
state { count 0 }
div {
  button { on:click "count++" } { "Count: {count}" }
}"""
        result = c.classify_page(source)
        assert result.classification == CLIENT
        assert result.needs_state is True
