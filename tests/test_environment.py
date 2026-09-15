import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from op02.environment import load_environment


class EnvironmentTests(unittest.TestCase):
    def test_load_without_shell_expansion_or_secret_output(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            path = Path(directory) / ".env"
            path.write_text("LLM_API_KEY='test-$(must-not-execute)'\nLLM_BASE_URL=https://example.com/v1\n")
            load_environment(path)
            self.assertEqual(os.environ["LLM_API_KEY"], "test-$(must-not-execute)")

    def test_environment_takes_precedence(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"LLM_API_KEY": "gateway"}, clear=True):
            path = Path(directory) / ".env"
            path.write_text("LLM_API_KEY=local\n")
            load_environment(path)
            self.assertEqual(os.environ["LLM_API_KEY"], "gateway")

    def test_unknown_settings_rejected_without_value(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("UNSUPPORTED=secret-value\n")
            with self.assertRaises(ValueError) as error:
                load_environment(path)
            self.assertNotIn("secret-value", str(error.exception))
