import json
import os
import subprocess
import unittest


class TestLocalRuntimeIntegration(unittest.TestCase):
    """Gerçek Ollama kurulumuna VE gerçek indirilmiş modele (llama3.2:3b)
    karşı çalışır — bu makinede tam olarak hazır (ollama_available: true,
    model_ready: true)."""

    def test_status_cli_reports_model_ready(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        result = subprocess.run(
            ["python3", "-m", "local_runtime"],
            cwd=here,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertIn(report["hardware_tier"], ("minimal", "low", "mid", "high"))
        self.assertTrue(report["ollama_available"])
        self.assertIn("llama3.2:3b", report["installed_models"])
        self.assertTrue(report["model_ready"])

    def test_prompt_cli_gets_real_generation(self):
        """Gerçek bir Ollama generate() çağrısı — model belleğe yüklenip
        CPU'da çıkarım yapabileceğinden bolca zaman aşımı payı var."""
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        result = subprocess.run(
            ["python3", "-m", "local_runtime", "--prompt", "Sadece 'merhaba' kelimesiyle cevap ver."],
            cwd=here,
            capture_output=True,
            text=True,
            timeout=300,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["model"], "llama3.2:3b")
        self.assertIsInstance(report["content"], str)
        self.assertGreater(len(report["content"]), 0)


if __name__ == "__main__":
    unittest.main()
