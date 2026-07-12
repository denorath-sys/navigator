import os
import tempfile
import unittest

from mcp_tools import filesystem as fs_module
from mcp_tools.filesystem import (
    FilesystemError,
    _resolve_within_root,
    list_directory,
    read_file,
    write_file,
)


class TestResolveWithinRoot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_relative_path_resolves_inside_root(self):
        resolved = _resolve_within_root("subdir/file.txt", self.root)
        self.assertTrue(resolved.startswith(os.path.realpath(self.root)))

    def test_root_itself_resolves(self):
        resolved = _resolve_within_root(".", self.root)
        self.assertEqual(resolved, os.path.realpath(self.root))

    def test_parent_traversal_is_blocked(self):
        with self.assertRaises(FilesystemError):
            _resolve_within_root("../etc/passwd", self.root)

    def test_deep_parent_traversal_is_blocked(self):
        with self.assertRaises(FilesystemError):
            _resolve_within_root("../../../../etc/passwd", self.root)

    def test_absolute_path_outside_root_is_blocked(self):
        with self.assertRaises(FilesystemError):
            _resolve_within_root("/etc/passwd", self.root)

    def test_absolute_path_inside_root_is_allowed(self):
        abs_path = os.path.join(os.path.realpath(self.root), "file.txt")
        resolved = _resolve_within_root(abs_path, self.root)
        self.assertEqual(resolved, abs_path)


class TestReadFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        with open(os.path.join(self.root, "hello.txt"), "w") as f:
            f.write("merhaba dünya")

    def tearDown(self):
        self.tmp.cleanup()

    def test_reads_file_content(self):
        content = read_file("hello.txt", root=self.root)
        self.assertEqual(content, "merhaba dünya")

    def test_missing_file_raises(self):
        with self.assertRaises(FilesystemError):
            read_file("yok.txt", root=self.root)

    def test_path_traversal_raises(self):
        with self.assertRaises(FilesystemError):
            read_file("../../../etc/passwd", root=self.root)

    def test_directory_path_raises(self):
        os.makedirs(os.path.join(self.root, "adir"))
        with self.assertRaises(FilesystemError):
            read_file("adir", root=self.root)

    def test_too_large_file_raises(self):
        with open(os.path.join(self.root, "big.txt"), "w") as f:
            f.write("x" * 10)
        original_limit = fs_module.MAX_READ_BYTES
        fs_module.MAX_READ_BYTES = 5
        try:
            with self.assertRaises(FilesystemError):
                read_file("big.txt", root=self.root)
        finally:
            fs_module.MAX_READ_BYTES = original_limit


class TestWriteFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        with open(os.path.join(self.root, "existing.txt"), "w") as f:
            f.write("eski içerik")

    def tearDown(self):
        self.tmp.cleanup()

    def test_writes_new_file(self):
        write_file("new.txt", "merhaba dünya", root=self.root)
        with open(os.path.join(self.root, "new.txt"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "merhaba dünya")

    def test_returns_byte_count_message(self):
        result = write_file("new.txt", "abc", root=self.root)
        self.assertIn("3", result)
        self.assertIn("new.txt", result)

    def test_existing_file_without_overwrite_raises(self):
        with self.assertRaises(FilesystemError):
            write_file("existing.txt", "yeni içerik", root=self.root)
        with open(os.path.join(self.root, "existing.txt"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "eski içerik")

    def test_existing_file_with_overwrite_succeeds(self):
        write_file("existing.txt", "yeni içerik", overwrite=True, root=self.root)
        with open(os.path.join(self.root, "existing.txt"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "yeni içerik")

    def test_path_traversal_raises(self):
        with self.assertRaises(FilesystemError):
            write_file("../../../tmp/kotu.txt", "x", root=self.root)

    def test_directory_path_raises(self):
        os.makedirs(os.path.join(self.root, "adir"))
        with self.assertRaises(FilesystemError):
            write_file("adir", "x", root=self.root)

    def test_missing_parent_directory_raises(self):
        with self.assertRaises(FilesystemError):
            write_file("yok/new.txt", "x", root=self.root)

    def test_too_large_content_raises(self):
        original_limit = fs_module.MAX_WRITE_BYTES
        fs_module.MAX_WRITE_BYTES = 5
        try:
            with self.assertRaises(FilesystemError):
                write_file("new.txt", "x" * 10, root=self.root)
        finally:
            fs_module.MAX_WRITE_BYTES = original_limit


class TestListDirectory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        os.makedirs(os.path.join(self.root, "subdir"))
        with open(os.path.join(self.root, "a.txt"), "w") as f:
            f.write("aaa")

    def tearDown(self):
        self.tmp.cleanup()

    def test_lists_entries(self):
        entries = list_directory(".", root=self.root)
        names = {e["name"] for e in entries}
        self.assertEqual(names, {"a.txt", "subdir"})

    def test_marks_directories_and_sizes(self):
        entries = list_directory(".", root=self.root)
        by_name = {e["name"]: e for e in entries}
        self.assertTrue(by_name["subdir"]["is_directory"])
        self.assertIsNone(by_name["subdir"]["size_bytes"])
        self.assertFalse(by_name["a.txt"]["is_directory"])
        self.assertEqual(by_name["a.txt"]["size_bytes"], 3)

    def test_missing_directory_raises(self):
        with self.assertRaises(FilesystemError):
            list_directory("yok", root=self.root)

    def test_path_traversal_raises(self):
        with self.assertRaises(FilesystemError):
            list_directory("../../..", root=self.root)


if __name__ == "__main__":
    unittest.main()
