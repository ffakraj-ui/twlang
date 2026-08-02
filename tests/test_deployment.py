"""Tests for deployment metadata, adapters, and zero‑config detection."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from tw_framework import compiler
from tw_framework.adapters import vercel, netlify
from tw_framework.framework import generate_deploy_metadata


class TestDeploymentMetadata(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.tmpdir, "dist")
        os.makedirs(self.output_dir, exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_generate_deploy_metadata(self):
        config = {"name": "Test"}
        generate_deploy_metadata(self.output_dir, config)
        deploy_path = os.path.join(self.output_dir, "tw.deploy.json")
        self.assertTrue(os.path.isfile(deploy_path))
        with open(deploy_path, "r") as f:
            data = json.load(f)
        self.assertEqual(data["framework"], "tw")
        self.assertEqual(data["build"], "tw build")
        self.assertEqual(data["output"], "dist")
        self.assertEqual(data["runtime"], "ssr")
        self.assertIn("version", data)

    def test_detect_tw_project(self):
        # Create a fake tw.config
        config_path = os.path.join(self.tmpdir, "tw.config")
        with open(config_path, "w") as f:
            f.write("name: Test\n")
        self.assertTrue(compiler.detect_tw_project(self.tmpdir))
        # Without tw.config
        empty_dir = os.path.join(self.tmpdir, "empty")
        os.makedirs(empty_dir, exist_ok=True)
        self.assertFalse(compiler.detect_tw_project(empty_dir))

    def test_vercel_adapter_detect(self):
        meta = vercel.detect()
        self.assertEqual(meta["framework"], "tw")
        self.assertEqual(meta["buildCommand"], "tw build")
        self.assertEqual(meta["outputDirectory"], "dist")

    def test_netlify_adapter_detect(self):
        meta = netlify.detect()
        self.assertEqual(meta["framework"], "tw")
        self.assertEqual(meta["buildCommand"], "tw build")
        self.assertEqual(meta["publish"], "dist")

    def test_vercel_auto_generate_json(self):
        # Simulate generate_vercel_output with missing vercel.json
        from tw_framework.adapters.vercel import generate_vercel_output
        config = {"name": "Test"}
        # Create a minimal dist directory
        dist_dir = os.path.join(self.tmpdir, "dist")
        os.makedirs(dist_dir, exist_ok=True)
        # The function expects dist_dir to exist
        generate_vercel_output(dist_dir, config, self.tmpdir)
        vercel_json = os.path.join(self.tmpdir, "vercel.json")
        self.assertTrue(os.path.isfile(vercel_json))
        with open(vercel_json, "r") as f:
            data = json.load(f)
        self.assertEqual(data["framework"], "tw")

    def test_netlify_auto_generate_toml(self):
        from tw_framework.adapters.netlify import generate_netlify_output
        config = {"name": "Test"}
        dist_dir = os.path.join(self.tmpdir, "dist")
        os.makedirs(dist_dir, exist_ok=True)
        generate_netlify_output(dist_dir, config, self.tmpdir)
        netlify_toml = os.path.join(self.tmpdir, "netlify.toml")
        self.assertTrue(os.path.isfile(netlify_toml))
        with open(netlify_toml, "r") as f:
            content = f.read()
        self.assertIn("tw build", content)
        self.assertIn('publish = "dist"', content)

    def test_streaming_render(self):
        """Test that streaming render produces valid HTML."""
        from tw_framework.streaming import render_program_streaming
        from tw_framework.ir import IRProgram, IRText
        program = IRProgram(
            meta={"title": "Test"},
            head={},
            lets={},
            state={},
            body=[IRText("Hello World")],
        )
        chunks = list(render_program_streaming(program))
        html = "".join(chunks)
        self.assertIn("Hello World", html)
        self.assertIn("<!DOCTYPE html>", html)


if __name__ == "__main__":
    unittest.main()
