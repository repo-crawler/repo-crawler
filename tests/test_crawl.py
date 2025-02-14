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
        is transformed to "github://org/name/main" (default branch 'main')
        and that the glob pattern is correctly constructed.
        """
        fake_fs = FakeFS({})
        mock_filesystem.return_value = fake_fs

        # Call with an input missing the 'github://' prefix.
        crawl_repo_files("repo-crawler/repo-crawler")

        # Check that the function constructed the correct glob pattern.
        expected_pattern = "github://repo-crawler/repo-crawler/main/**"
        self.assertEqual(fake_fs.last_glob, expected_pattern)

    @patch("repo_crawler.crawl.fsspec.filesystem")
    def test_valid_path_with_exclusion(self, mock_filesystem):
        """
        Test that crawl_repo_files prints file contents with headers and line numbers
        for valid files, and that files with excluded extensions are skipped.
        """
        # Setup fake files: one valid text file, one file with an excluded extension,
        # and one directory (which should be ignored).
        fake_files = {
            "github://user/repo/branch/file1.txt": ("hello\nworld\n", {'type': 'file'}),
            "github://user/repo/branch/file2.svg": ("should be excluded", {'type': 'file'}),
            "github://user/repo/branch/dir": ("", {'type': 'directory'}),
        }
        fake_fs = FakeFS(fake_files)
        mock_filesystem.return_value = fake_fs

        # Capture printed output.
        captured_output = io.StringIO()
        original_stdout = sys.stdout
        sys.stdout = captured_output

        try:
            crawl_repo_files("github://user/repo/branch", exclude_exts=['svg'])
            output = captured_output.getvalue()
        finally:
            sys.stdout = original_stdout

        # Check that file1.txt header and its contents (with line numbers) are present.
        self.assertIn("# github://user/repo/branch/file1.txt", output)
        self.assertIn("1| hello", output)
        self.assertIn("2| world", output)

        # Ensure that file2.svg and its contents are not printed.
        self.assertNotIn("file2.svg", output)
        self.assertNotIn("should be excluded", output)

if __name__ == '__main__':
    unittest.main()
