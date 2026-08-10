import queue
import unittest

from mcp_tools.http_transport import SSESessionRegistry


class TestSSESessionRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = SSESessionRegistry()

    def test_create_returns_unique_session_ids(self):
        id1, _ = self.registry.create()
        id2, _ = self.registry.create()
        self.assertNotEqual(id1, id2)

    def test_get_returns_the_created_queue(self):
        session_id, q = self.registry.create()
        self.assertIs(self.registry.get(session_id), q)

    def test_get_unknown_session_returns_none(self):
        self.assertIsNone(self.registry.get("bilinmeyen"))

    def test_remove_forgets_session(self):
        session_id, _ = self.registry.create()
        self.registry.remove(session_id)
        self.assertIsNone(self.registry.get(session_id))

    def test_remove_unknown_session_does_not_raise(self):
        self.registry.remove("never-existed")  # must be ignored silently

    def test_queue_delivers_put_items(self):
        _, q = self.registry.create()
        q.put({"hello": "world"})
        self.assertEqual(q.get(timeout=1), {"hello": "world"})


if __name__ == "__main__":
    unittest.main()
