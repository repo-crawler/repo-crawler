import unittest
from unittest.mock import patch
import io
import sys

from repo_crawler.crawl import crawl_repo_files

class FakeFS:
    """
    A fake filesystem to simulate fsspec's GitHub filesystem for testing.
    """
    def __init__(self, files):
        """
        :param files: A dict mapping file paths to a tuple (content, info_dict).
                      Example:
                          {
                              "github://user/repo/branch/file1.txt": ("hello\nworld\n", {'type': 'file'}),
                              "github://user/repo/branch/file2.svg": ("should be excluded", {'type': 'file'}),
                              "github://user/repo/branch/dir": ("", {'type': 'directory'}),
                          }
        """
        self.files = files
        self.last_glob = None  # Record the last glob pattern passed

    def glob(self, pattern, recursive=False):
        self.last_glob = pattern
        # For testing, return all known paths regardless of the pattern.
        return list(self.files.keys())

    def info(self, path):
        if path in self.files:
            return self.files[path][1]
        raise FileNotFoundError(f"No such file: {path}")

    def open(self, path, mode='r'):
        if path in self.files:
            content = self.files[path][0]
            return io.StringIO(content)
        raise FileNotFoundError(f"No such file: {path}")

class TestCrawl(unittest.TestCase):
    @patch("repo_crawler.crawl.fsspec.filesystem")
    def test_path_transformation(self, mock_filesystem):
        """
        Test that an input in the form "org/name" (without a prefix)
        is transformed properly and that the glob pattern is correctly constructed.
        Since the GitHub filesystem is initialized with org, repo, and ref,
        the glob pattern is relative to the repository root.
        """
        fake_fs = FakeFS({})
        mock_filesystem.return_value = fake_fs

        # Call with an input missing the 'github://' prefix.
        crawl_repo_files("repo-crawler/repo-crawler")

        # With no subdirectory provided, the glob pattern should be just "**"
        expected_pattern = "**"
        self.assertEqual(fake_fs.last_glob, expected_pattern)

    @patch("repo_crawler.crawl.fsspec.filesystem")
    def test_valid_path_with_exclusion(self, mock_filesystem, capsys):
        fake_files = {
            "github://user/repo/branch/file1.txt": ("hello\nworld\n", {'type': 'file'}),
            "github://user/repo/branch/file2.svg": ("should be excluded", {'type': 'file'}),
            "github://user/repo/branch/dir": ("", {'type': 'directory'}),
        }
        fake_fs = FakeFS(fake_files)
        mock_filesystem.return_value = fake_fs

        crawl_repo_files("github://user/repo/branch", exclude_exts=['svg'])
        captured = capsys.readouterr().out

        self.assertIn("# github://user/repo/branch/file1.txt", captured)
        self.assertIn("00001| hello", captured)
        self.assertIn("00002| world", captured)
        self.assertNotIn("file2.svg", captured)

if __name__ == '__main__':
    unittest.main()
