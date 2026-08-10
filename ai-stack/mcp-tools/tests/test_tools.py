import json
import unittest

from mcp_tools.tools import hardware_tier_tool, route_request_tool


class TestToolsAgainstRealModules(unittest.TestCase):
    """Runs against the real hardware-probe and router modules (subprocess)."""

    def test_hardware_tier_tool_returns_valid_json(self):
        output = hardware_tier_tool()
        report = json.loads(output)
        self.assertIn(report["tier"], ("minimal", "low", "mid", "high"))

    def test_route_request_tool_returns_valid_json(self):
        output = route_request_tool("test request", prefer="balanced")
        report = json.loads(output)
        self.assertIn(report["route"], ("local", "cloud"))


if __name__ == "__main__":
    unittest.main()
