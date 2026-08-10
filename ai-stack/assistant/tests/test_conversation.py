import json
import subprocess
import unittest
from unittest.mock import MagicMock, patch

from assistant.conversation import (
    SYSTEM_PROMPT,
    AssistantError,
    _extract_text,
    _mcp_tools_to_claude_tools,
    _mcp_tools_to_ollama_tools,
    decide_route,
    run_cloud_turn,
    run_local_turn,
    run_turn,
)


def _fake_run(stdout: str, returncode: int = 0):
    return MagicMock(stdout=stdout, returncode=returncode)


class TestMcpToolsToClaudeTools(unittest.TestCase):
    def test_translates_schema_fields(self):
        mcp_tools = [
            {"name": "hardware_tier", "description": "...", "inputSchema": {"type": "object"}},
        ]
        claude_tools = _mcp_tools_to_claude_tools(mcp_tools)
        self.assertEqual(
            claude_tools,
            [{"name": "hardware_tier", "description": "...", "input_schema": {"type": "object"}}],
        )


class TestExtractText(unittest.TestCase):
    def test_concatenates_text_blocks_only(self):
        blocks = [
            {"type": "text", "text": "hello "},
            {"type": "tool_use", "name": "x", "input": {}},
            {"type": "text", "text": "world"},
        ]
        self.assertEqual(_extract_text(blocks), "hello world")


class TestDecideRoute(unittest.TestCase):
    @patch("assistant.conversation.subprocess.run")
    def test_calls_router_with_decide_only(self, mock_run):
        mock_run.return_value = _fake_run(json.dumps({"route": "local", "hardware_tier": "low"}))
        result = decide_route("hi", preference="privacy", router_cwd="../router")
        self.assertEqual(result["route"], "local")
        args = mock_run.call_args[0][0]
        self.assertIn("--decide-only", args)
        self.assertIn("privacy", args)
        self.assertEqual(mock_run.call_args[1]["cwd"], "../router")


class TestMcpToolsToOllamaTools(unittest.TestCase):
    def test_translates_to_openai_style_function_schema(self):
        mcp_tools = [
            {
                "name": "hardware_tier",
                "description": "...",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            }
        ]
        ollama_tools = _mcp_tools_to_ollama_tools(mcp_tools)
        self.assertEqual(
            ollama_tools,
            [
                {
                    "type": "function",
                    "function": {
                        "name": "hardware_tier",
                        "description": "...",
                        "parameters": {"type": "object", "properties": {}, "required": []},
                    },
                }
            ],
        )


class TestRunLocalTurn(unittest.TestCase):
    def _fake_mcp_client(self, tool_result_text="42", schema=None):
        client = MagicMock()
        client.list_tools.return_value = [
            {
                "name": "hardware_tier",
                "description": "...",
                "inputSchema": schema or {"type": "object", "properties": {}, "required": []},
            }
        ]
        client.call_tool.return_value = {
            "content": [{"type": "text", "text": tool_result_text}],
            "isError": False,
        }
        return client

    @patch("assistant.conversation._call_local_runtime_converse")
    def test_returns_content_immediately_when_no_tool_calls(self, mock_converse):
        mock_converse.return_value = {"message": {"role": "assistant", "content": "hello!"}}
        result = run_local_turn("hi", self._fake_mcp_client())
        self.assertEqual(result["content"], "hello!")
        self.assertEqual(result["tool_calls"], [])
        self.assertEqual(result["route"], "local")
        self.assertEqual(
            result["history"],
            [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello!"}],
        )
        self._fake_mcp_client().call_tool.assert_not_called()

    @patch("assistant.conversation._call_local_runtime_converse")
    def test_raises_on_unavailable(self, mock_converse):
        mock_converse.return_value = {"status": "unavailable", "reason": "ollama_not_running"}
        with self.assertRaises(AssistantError):
            run_local_turn("hi", self._fake_mcp_client())

    @patch("assistant.conversation._call_local_runtime_converse")
    def test_raises_on_error_status(self, mock_converse):
        mock_converse.return_value = {"status": "error", "error": "boom"}
        with self.assertRaises(AssistantError):
            run_local_turn("hi", self._fake_mcp_client())

    @patch("assistant.conversation._call_local_runtime_converse")
    def test_history_is_prepended_to_ollama_messages(self, mock_converse):
        captured_payloads = []

        def fake_converse(payload, cwd="../local-runtime"):
            captured_payloads.append(json.loads(json.dumps(payload)))
            return {"message": {"role": "assistant", "content": "Ahmet"}}

        mock_converse.side_effect = fake_converse
        history = [
            {"role": "user", "content": "My name is Ahmet."},
            {"role": "assistant", "content": "Hello Ahmet!"},
        ]
        run_local_turn("What was my name?", self._fake_mcp_client(), history=history)
        sent_messages = captured_payloads[0]["messages"]
        self.assertEqual(
            sent_messages,
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "My name is Ahmet."},
                {"role": "assistant", "content": "Hello Ahmet!"},
                {"role": "user", "content": "What was my name?"},
            ],
        )

    @patch("assistant.conversation._call_local_runtime_converse")
    def test_returned_history_excludes_tool_calls(self, mock_converse):
        mock_converse.side_effect = [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"function": {"name": "hardware_tier", "arguments": {}}}],
                }
            },
            {"message": {"role": "assistant", "content": "tier is low"}},
        ]
        result = run_local_turn("what is my hardware?", self._fake_mcp_client())
        self.assertEqual(
            result["history"],
            [
                {"role": "user", "content": "what is my hardware?"},
                {"role": "assistant", "content": "tier is low"},
            ],
        )

    @patch("assistant.conversation._call_local_runtime_converse")
    def test_executes_tool_call_and_feeds_result_back(self, mock_converse):
        responses = [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"function": {"name": "hardware_tier", "arguments": {}}}],
                }
            },
            {"message": {"role": "assistant", "content": "tier is low"}},
        ]
        captured_payloads = []

        def fake_converse(payload, cwd="../local-runtime"):
            captured_payloads.append(json.loads(json.dumps(payload)))
            return responses.pop(0)

        mock_converse.side_effect = fake_converse
        client = self._fake_mcp_client(tool_result_text='{"tier": "low"}')
        result = run_local_turn("what is my hardware?", client)

        self.assertEqual(result["content"], "tier is low")
        self.assertEqual(result["tool_calls"], [{"name": "hardware_tier", "input": {}}])
        client.call_tool.assert_called_once_with("hardware_tier", {})

        second_call_messages = captured_payloads[1]["messages"]
        tool_result_message = second_call_messages[-1]
        self.assertEqual(tool_result_message["role"], "tool")
        self.assertEqual(tool_result_message["content"], '{"tier": "low"}')

    @patch("assistant.conversation._call_local_runtime_converse")
    def test_hallucinated_arguments_outside_schema_are_filtered(self, mock_converse):
        """In real testing llama3.2:3b made up hallucinated arguments even
        for zero-parameter tools (e.g. {"path": "..."}) — keys not in the
        tool's inputSchema must be dropped."""
        responses = [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "hardware_tier",
                                "arguments": {"path": "/home/chief", "": "null"},
                            }
                        }
                    ],
                }
            },
            {"message": {"role": "assistant", "content": "tamam"}},
        ]
        mock_converse.side_effect = responses
        client = self._fake_mcp_client(schema={"type": "object", "properties": {}, "required": []})

        result = run_local_turn("x", client)

        self.assertEqual(result["tool_calls"], [{"name": "hardware_tier", "input": {}}])
        client.call_tool.assert_called_once_with("hardware_tier", {})

    @patch("assistant.conversation._call_local_runtime_converse")
    def test_unsafe_tool_not_shown_to_model_and_rejected_if_hallucinated(self, mock_converse):
        """In real testing the 3B model spontaneously tried to call
        write_file with overwrite=true even on a harmless 'just say hello'
        request. write_file/delete_file/rename_file are not shown to the local
        model at all (they are absent from the tools list) AND if the model
        still hallucinates a call, the defence layer rejects it — it never
        reaches mcp_client.call_tool()."""
        responses = [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "write_file",
                                "arguments": {"path": "/home/chief", "content": "x", "overwrite": True},
                            }
                        }
                    ],
                }
            },
            {"message": {"role": "assistant", "content": "tamam"}},
        ]
        mock_converse.side_effect = responses
        client = MagicMock()
        client.list_tools.return_value = [
            {"name": "hardware_tier", "description": "...", "inputSchema": {"type": "object", "properties": {}}},
            {
                "name": "write_file",
                "description": "...",
                "inputSchema": {"type": "object", "properties": {"path": {}, "content": {}}},
            },
        ]

        run_local_turn("hi", client)

        # Even though write_file is in the tools/list mock, the tools sent to
        # tools listesinde OLMAMALI:
        sent_tools = mock_converse.call_args_list[0][0][0]["tools"]
        tool_names_sent = {t["function"]["name"] for t in sent_tools}
        self.assertNotIn("write_file", tool_names_sent)
        self.assertIn("hardware_tier", tool_names_sent)
        # If the model hallucinated a call anyway, the real file tool must
        # NEVER be executed:
        client.call_tool.assert_not_called()

    @patch("assistant.conversation._call_local_runtime_converse")
    def test_allowed_arguments_within_schema_are_kept(self, mock_converse):
        responses = [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": "read_file", "arguments": {"path": "x.txt", "junk": 1}}}
                    ],
                }
            },
            {"message": {"role": "assistant", "content": "tamam"}},
        ]
        mock_converse.side_effect = responses
        schema = {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
        client = MagicMock()
        client.list_tools.return_value = [
            {"name": "read_file", "description": "...", "inputSchema": schema}
        ]
        client.call_tool.return_value = {
            "content": [{"type": "text", "text": "ok"}],
            "isError": False,
        }

        run_local_turn("x", client)

        client.call_tool.assert_called_once_with("read_file", {"path": "x.txt"})

    @patch("assistant.conversation._call_local_runtime_converse")
    def test_tool_call_exception_is_reported_as_error_result(self, mock_converse):
        responses = [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"function": {"name": "hardware_tier", "arguments": {}}}],
                }
            },
            {"message": {"role": "assistant", "content": "tamam"}},
        ]
        captured_payloads = []

        def fake_converse(payload, cwd="../local-runtime"):
            captured_payloads.append(json.loads(json.dumps(payload)))
            return responses.pop(0)

        mock_converse.side_effect = fake_converse
        client = self._fake_mcp_client()
        client.call_tool.side_effect = RuntimeError("mcp-tools crashed")

        run_local_turn("x", client)

        second_call_messages = captured_payloads[1]["messages"]
        self.assertIn("mcp-tools crashed", second_call_messages[-1]["content"])

    @patch("assistant.conversation._call_local_runtime_converse")
    def test_raises_after_max_iterations_infinite_tool_use(self, mock_converse):
        mock_converse.return_value = {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": "hardware_tier", "arguments": {}}}],
            }
        }
        client = self._fake_mcp_client()
        with self.assertRaises(AssistantError):
            run_local_turn("x", client, max_iterations=3)
        self.assertEqual(mock_converse.call_count, 3)


class TestRunCloudTurn(unittest.TestCase):
    def _fake_mcp_client(self, tool_result_text="42"):
        client = MagicMock()
        client.list_tools.return_value = [
            {"name": "hardware_tier", "description": "...", "inputSchema": {"type": "object"}}
        ]
        client.call_tool.return_value = {
            "content": [{"type": "text", "text": tool_result_text}],
            "isError": False,
        }
        return client

    @patch("assistant.conversation._call_cloud_bridge_converse")
    def test_returns_text_immediately_when_no_tool_use(self, mock_converse):
        mock_converse.return_value = {
            "content": [{"type": "text", "text": "hello"}],
            "stop_reason": "end_turn",
        }
        client = self._fake_mcp_client()
        result = run_cloud_turn("hi", client)
        self.assertEqual(result["content"], "hello")
        self.assertEqual(result["tool_calls"], [])
        self.assertEqual(result["route"], "cloud")
        self.assertEqual(
            result["history"],
            [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
        )
        client.call_tool.assert_not_called()

    @patch("assistant.conversation._call_cloud_bridge_converse")
    def test_history_is_prepended_to_claude_messages(self, mock_converse):
        captured_payloads = []

        def fake_converse(payload, cwd="../cloud-bridge"):
            captured_payloads.append(json.loads(json.dumps(payload)))
            return {"content": [{"type": "text", "text": "Ahmet"}], "stop_reason": "end_turn"}

        mock_converse.side_effect = fake_converse
        history = [
            {"role": "user", "content": "My name is Ahmet."},
            {"role": "assistant", "content": "Hello Ahmet!"},
        ]
        run_cloud_turn("What was my name?", self._fake_mcp_client(), history=history)
        sent_payload = captured_payloads[0]
        self.assertEqual(
            sent_payload["messages"],
            [
                {"role": "user", "content": "My name is Ahmet."},
                {"role": "assistant", "content": "Hello Ahmet!"},
                {"role": "user", "content": "What was my name?"},
            ],
        )

    @patch("assistant.conversation._call_cloud_bridge_converse")
    def test_returned_history_excludes_tool_blocks(self, mock_converse):
        """The returned history must be plain text — Claude's
        tool_use/tool_result blocks must not leak into later turns (so that it
        stays portable even if the route changes, see the module docstring)."""
        mock_converse.side_effect = [
            {
                "content": [
                    {"type": "tool_use", "id": "toolu_1", "name": "hardware_tier", "input": {}}
                ],
                "stop_reason": "tool_use",
            },
            {"content": [{"type": "text", "text": "tier is low"}], "stop_reason": "end_turn"},
        ]
        result = run_cloud_turn("what is my hardware?", self._fake_mcp_client())
        self.assertEqual(
            result["history"],
            [
                {"role": "user", "content": "what is my hardware?"},
                {"role": "assistant", "content": "tier is low"},
            ],
        )

    @patch("assistant.conversation._call_cloud_bridge_converse")
    def test_executes_tool_call_and_feeds_result_back(self, mock_converse):
        responses = [
            {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "hardware_tier",
                        "input": {},
                    }
                ],
                "stop_reason": "tool_use",
            },
            {
                "content": [{"type": "text", "text": "tier is low"}],
                "stop_reason": "end_turn",
            },
        ]
        captured_payloads = []

        def fake_converse(payload, cwd="../cloud-bridge"):
            captured_payloads.append(json.loads(json.dumps(payload)))  # a copy of the state at that moment
            return responses.pop(0)

        mock_converse.side_effect = fake_converse
        client = self._fake_mcp_client(tool_result_text='{"tier": "low"}')
        result = run_cloud_turn("what is my hardware?", client)

        self.assertEqual(result["content"], "tier is low")
        self.assertEqual(result["tool_calls"], [{"name": "hardware_tier", "input": {}}])
        client.call_tool.assert_called_once_with("hardware_tier", {})

        second_call_messages = captured_payloads[1]["messages"]
        tool_result_message = second_call_messages[-1]
        self.assertEqual(tool_result_message["role"], "user")
        self.assertEqual(tool_result_message["content"][0]["tool_use_id"], "toolu_1")
        self.assertEqual(tool_result_message["content"][0]["content"], '{"tier": "low"}')
        self.assertFalse(tool_result_message["content"][0]["is_error"])

    @patch("assistant.conversation._call_cloud_bridge_converse")
    def test_tool_call_exception_is_reported_as_error_result(self, mock_converse):
        responses = [
            {
                "content": [
                    {"type": "tool_use", "id": "toolu_1", "name": "hardware_tier", "input": {}}
                ],
                "stop_reason": "tool_use",
            },
            {"content": [{"type": "text", "text": "tamam"}], "stop_reason": "end_turn"},
        ]
        captured_payloads = []

        def fake_converse(payload, cwd="../cloud-bridge"):
            captured_payloads.append(json.loads(json.dumps(payload)))
            return responses.pop(0)

        mock_converse.side_effect = fake_converse
        client = self._fake_mcp_client()
        client.call_tool.side_effect = RuntimeError("mcp-tools crashed")

        run_cloud_turn("x", client)

        second_call_messages = captured_payloads[1]["messages"]
        tool_result = second_call_messages[-1]["content"][0]
        self.assertTrue(tool_result["is_error"])
        self.assertIn("mcp-tools crashed", tool_result["content"])

    @patch("assistant.conversation._call_cloud_bridge_converse")
    def test_raises_on_unavailable(self, mock_converse):
        mock_converse.return_value = {"status": "unavailable", "reason": "credentials_not_configured"}
        with self.assertRaises(AssistantError):
            run_cloud_turn("x", self._fake_mcp_client())

    @patch("assistant.conversation._call_cloud_bridge_converse")
    def test_raises_on_error_status(self, mock_converse):
        mock_converse.return_value = {"status": "error", "error": "boom"}
        with self.assertRaises(AssistantError):
            run_cloud_turn("x", self._fake_mcp_client())

    @patch("assistant.conversation._call_cloud_bridge_converse")
    def test_raises_after_max_iterations_infinite_tool_use(self, mock_converse):
        mock_converse.return_value = {
            "content": [
                {"type": "tool_use", "id": "toolu_1", "name": "hardware_tier", "input": {}}
            ],
            "stop_reason": "tool_use",
        }
        client = self._fake_mcp_client()
        with self.assertRaises(AssistantError):
            run_cloud_turn("x", client, max_iterations=3)
        self.assertEqual(mock_converse.call_count, 3)


class TestRunTurn(unittest.TestCase):
    @patch("assistant.conversation.run_local_turn")
    @patch("assistant.conversation.run_cloud_turn")
    @patch("assistant.conversation.decide_route")
    def test_dispatches_to_local_and_merges_decision_fields(
        self, mock_decide, mock_cloud, mock_local
    ):
        mock_decide.return_value = {
            "route": "local",
            "hardware_tier": "high",
            "reasoning": "model ready",
        }
        mock_local.return_value = {"content": "hello", "tool_calls": [], "route": "local"}

        result = run_turn("hi", MagicMock())

        mock_local.assert_called_once()
        mock_cloud.assert_not_called()
        self.assertEqual(result["hardware_tier"], "high")
        self.assertEqual(result["reasoning"], "model ready")

    @patch("assistant.conversation.run_local_turn")
    @patch("assistant.conversation.run_cloud_turn")
    @patch("assistant.conversation.decide_route")
    def test_dispatches_to_cloud(self, mock_decide, mock_cloud, mock_local):
        mock_decide.return_value = {"route": "cloud", "hardware_tier": "low", "reasoning": "complex"}
        mock_cloud.return_value = {"content": "ok", "tool_calls": [], "route": "cloud"}

        result = run_turn("a long and complex request", MagicMock())

        mock_cloud.assert_called_once()
        mock_local.assert_not_called()
        self.assertEqual(result["route"], "cloud")

    @patch("assistant.conversation.run_local_turn")
    @patch("assistant.conversation.decide_route")
    def test_passes_history_through_to_route_handler(self, mock_decide, mock_local):
        mock_decide.return_value = {"route": "local", "hardware_tier": "low", "reasoning": "x"}
        mock_local.return_value = {"content": "ok", "tool_calls": [], "route": "local"}
        history = [{"role": "user", "content": "previous question"}]

        run_turn("yeni soru", MagicMock(), history=history)

        self.assertEqual(mock_local.call_args.kwargs["history"], history)

    @patch("assistant.conversation.run_local_turn")
    @patch("assistant.conversation.decide_route")
    def test_trims_history_to_max_messages(self, mock_decide, mock_local):
        from assistant.conversation import MAX_HISTORY_MESSAGES

        mock_decide.return_value = {"route": "local", "hardware_tier": "low", "reasoning": "x"}
        mock_local.return_value = {"content": "ok", "tool_calls": [], "route": "local"}
        long_history = [{"role": "user", "content": str(i)} for i in range(MAX_HISTORY_MESSAGES + 10)]

        run_turn("yeni soru", MagicMock(), history=long_history)

        passed_history = mock_local.call_args.kwargs["history"]
        self.assertEqual(len(passed_history), MAX_HISTORY_MESSAGES)
        self.assertEqual(passed_history, long_history[-MAX_HISTORY_MESSAGES:])


if __name__ == "__main__":
    unittest.main()
