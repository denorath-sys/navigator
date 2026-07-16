import json
import os
import subprocess
import tempfile
import unittest

from assistant.mcp_client import MCPClient

HAS_CLOUD_CREDENTIALS = bool(
    os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
)


class TestAssistantIntegration(unittest.TestCase):
    """assistant -> router -> (local-runtime | cloud-bridge) -> mcp-tools
    zincirinin GERÇEK subprocess'lerle uçtan uca çalıştığını doğrular.

    Yerel yol (Ollama kurulu/model hazır olduğundan) her zaman gerçek
    çalışır. Bulut yolu + gerçek tool-use döngüsü, ANTHROPIC_API_KEY/
    ANTHROPIC_AUTH_TOKEN ortamda yoksa (CI dahil) otomatik `skip` olur.
    """

    def _run_cli(self, prompt: str, extra_args: list[str] | None = None) -> dict:
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        result = subprocess.run(
            ["python3", "-m", "assistant", "--prompt", prompt, *(extra_args or [])],
            cwd=here,
            capture_output=True,
            text=True,
            timeout=300,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def _run_cli_until(self, prompt, predicate, extra_args=None, max_attempts=3) -> dict:
        """Yerel 3B modelin tool-use çıktısı gerçek testte doğası gereği
        stokastik olduğu gözlendi (bazen yapılandırılmış tool_calls yerine
        ham JSON metni üretiyor) — bu bir kod hatası değil, küçük modelin
        bilinen bir sınırlaması (bkz. assistant/README.md). İçerik
        kalitesine bağlı testler bu yüzden sınırlı sayıda tekrar dener;
        güvenlik testleri (yazma aracı asla gösterilmez/çalıştırılmaz)
        deterministik olduğundan bunu KULLANMAZ."""
        report = None
        for _ in range(max_attempts):
            report = self._run_cli(prompt, extra_args)
            if predicate(report):
                return report
        return report

    def test_simple_prompt_routes_local_with_real_generation(self):
        """3B model gerçek testte basit isteklerde bile ara sıra gereksiz
        araç çağırıyor (küçük modelin zayıf yönü) — bu yüzden tool_calls
        boş OLMAK ZORUNDA değil, ama ASLA yazma/silme aracı olmamalı
        (bkz. LOCAL_SAFE_TOOL_NAMES, gerçek testte yakalanan halüsinasyon
        write_file çağrısına karşı savunma)."""
        from assistant.conversation import LOCAL_SAFE_TOOL_NAMES

        report = self._run_cli("Sadece 'merhaba' kelimesiyle cevap ver.")
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["route"], "local")
        for call in report["tool_calls"]:
            self.assertIn(call["name"], LOCAL_SAFE_TOOL_NAMES)
        self.assertIsInstance(report["content"], str)
        self.assertGreater(len(report["content"]), 0)

    def test_local_tool_use_never_exposes_write_tools(self):
        """Yerel modele write_file/delete_file/rename_file'ın hiç
        gösterilmediğini doğrudan doğrular — gerçek mcp-tools + gerçek
        Ollama ile."""
        from assistant.conversation import _mcp_tools_to_ollama_tools, LOCAL_SAFE_TOOL_NAMES

        with MCPClient(cwd="../mcp-tools") as client:
            safe_tools = [t for t in client.list_tools() if t["name"] in LOCAL_SAFE_TOOL_NAMES]
            ollama_tools = _mcp_tools_to_ollama_tools(safe_tools)
        tool_names = {t["function"]["name"] for t in ollama_tools}
        self.assertNotIn("write_file", tool_names)
        self.assertNotIn("delete_file", tool_names)
        self.assertNotIn("rename_file", tool_names)
        self.assertIn("hardware_tier", tool_names)

    def test_local_prompt_that_needs_tool_gets_real_correct_answer(self):
        """Faz 4'te gerçek testte önce başarısız olan tam senaryo: kısa
        bir donanım sorusu (şema filtresi düzeltmesi sayesinde) doğru
        cevap üretir — bkz. assistant/README.md. Küçük modelin bilinen
        değişkenliği nedeniyle sınırlı tekrar denenir (bkz.
        _run_cli_until).

        Router'a eklenen 'araç gerekebilir mi' sinyali sayesinde bu
        prompt artık `balanced` tercihinde varsayılan olarak buluta
        düşüyor (bkz. router/tests/test_integration.py
        test_short_tool_prompt_decide_only_routes_cloud_on_this_low_tier_machine)
        — burada yerel tool-use'ın (gizlilik/maliyet tercih edildiğinde
        hâlâ kullanılacak yol olduğundan) doğru çalıştığını doğrulamak
        için --prefer cost ile yerel zorlanıyor."""
        prompt = "Bu makinede kaç CPU çekirdeği var? Aracı kullanarak öğren, kısa cevap ver."
        report = self._run_cli_until(
            prompt,
            predicate=lambda r: r.get("status") == "ok" and "6" in r.get("content", ""),
            extra_args=["--prefer", "cost"],
        )
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["route"], "local")
        self.assertIn("6", report["content"])

    def test_history_persists_across_separate_processes_via_history_file(self):
        """--history-file ile konuşma geçmişi AYRI süreçler arasında
        kalıcı — REPL veya --prompt bağımsız her çalıştırma önceki
        turları hatırlar. Yerel yol (kimlik bilgisi gerekmez) ile gerçek
        Ollama üretimiyle doğrulanır. İkinci turun içerik kalitesi (isim
        hatırlama) küçük modelin bilinen değişkenliği nedeniyle sınırlı
        tekrar dener — her denemeden önce geçmiş dosyası ilk turdan sonraki
        haline sıfırlanır (bkz. _run_cli_until, assistant/README.md)."""
        fd, history_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.remove(history_path)  # assistant kendisi oluştursun
        try:
            first = self._run_cli(
                "Benim adım Ahmet, bunu unutma.", ["--history-file", history_path]
            )
            self.assertEqual(first["route"], "local")
            self.assertTrue(os.path.exists(history_path))
            with open(history_path, encoding="utf-8") as f:
                history_after_first_turn = json.load(f)
            self.assertEqual(
                history_after_first_turn[0],
                {"role": "user", "content": "Benim adım Ahmet, bunu unutma."},
            )

            second = None
            for _ in range(3):
                with open(history_path, "w", encoding="utf-8") as f:
                    json.dump(history_after_first_turn, f, ensure_ascii=False)
                second = self._run_cli(
                    "Benim adım neydi? Sadece ismi söyle.", ["--history-file", history_path]
                )
                if "Ahmet" in second["content"]:
                    break

            self.assertIn("Ahmet", second["content"])
            self.assertEqual(len(second["history"]), 4)
        finally:
            if os.path.exists(history_path):
                os.remove(history_path)

    @unittest.skipUnless(
        HAS_CLOUD_CREDENTIALS, "ANTHROPIC_API_KEY/ANTHROPIC_AUTH_TOKEN ayarlı değil"
    )
    def test_complex_prompt_routes_cloud_and_uses_real_hardware_tool(self):
        long_prompt = (
            "Bu makinede kaç tane CPU çekirdeği var, toplam RAM ne kadar, ve "
            "ayrık bir grafik kartı var mı yok mu, bunların hepsini lütfen "
            "gerçek donanım tespit aracını kullanarak öğren ve bana net bir "
            "şekilde madde madde özetle, sakın tahmin etme, sadece aracın "
            "döndürdüğü gerçek verilere dayan ve kısa tut."
        )
        report = self._run_cli(long_prompt)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["route"], "cloud")
        self.assertEqual(report["tool_calls"], [{"name": "hardware_tier", "input": {}}])
        self.assertIn("6", report["content"])  # gerçek çekirdek sayısı
        self.assertIn("15", report["content"])  # gerçek RAM (~15.4 GB)

    @unittest.skipUnless(
        HAS_CLOUD_CREDENTIALS, "ANTHROPIC_API_KEY/ANTHROPIC_AUTH_TOKEN ayarlı değil"
    )
    def test_mcp_client_and_run_cloud_turn_real_end_to_end(self):
        """CLI'ı atlayıp iç API'yi doğrudan kullanarak (gerçek mcp-tools
        subprocess'i + gerçek Claude API) aynı akışı doğrular."""
        from assistant.conversation import run_cloud_turn

        with MCPClient(cwd="../mcp-tools") as client:
            result = run_cloud_turn(
                "Bu makinenin donanım tier'ı nedir? Aracı kullanarak gerçekten öğren.",
                client,
            )
        self.assertEqual(result["route"], "cloud")
        self.assertTrue(any(tc["name"] == "hardware_tier" for tc in result["tool_calls"]))
        self.assertIn("low", result["content"].lower())


if __name__ == "__main__":
    unittest.main()
