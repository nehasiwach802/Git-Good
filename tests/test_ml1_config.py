import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from labvision.config import gemini_settings, load_dotenv
from labvision.core import CandidateError


class ConfigTests(unittest.TestCase):
    def parse(self, content):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(content, encoding="utf-8-sig")
            return load_dotenv(path)

    def test_plain_and_quoted_export_settings(self):
        settings = self.parse('# comment\nexport GEMINI_API_KEY="dummy-key"\n'
                              "GEMINI_MODEL='model-id' # comment\nIGNORED=other\n")
        self.assertEqual(settings, {"GEMINI_API_KEY": "dummy-key", "GEMINI_MODEL": "model-id"})

    def test_unquoted_values_and_comments(self):
        self.assertEqual(self.parse("GEMINI_MODEL=model-id # note\n"), {"GEMINI_MODEL": "model-id"})

    def test_environment_overrides_file_without_mutation(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "environment-key"}, clear=True), \
                patch("labvision.config.load_dotenv", return_value={
                    "GEMINI_API_KEY": "file-key", "GEMINI_MODEL": "file-model"}):
            result = gemini_settings()
            self.assertEqual(result["GEMINI_API_KEY"], "environment-key")
            self.assertEqual(result["GEMINI_MODEL"], "file-model")
            self.assertNotIn("GEMINI_MODEL", os.environ)

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(load_dotenv(Path(directory) / "absent.env"), {})

    def test_invalid_line_never_echoes_secret(self):
        with self.assertRaises(CandidateError) as caught:
            self.parse('GEMINI_API_KEY="dummy-sensitive-value\n')
        self.assertNotIn("dummy-sensitive-value", str(caught.exception))

    def test_values_are_never_executed_or_expanded(self):
        self.assertEqual(self.parse("GEMINI_API_KEY='$(do-not-execute)'\n")["GEMINI_API_KEY"],
                         "$(do-not-execute)")


if __name__ == "__main__":
    unittest.main()
