import unittest
from unittest.mock import patch
import io
import sys

from repo_crawler.crawl import crawl_repo_files

class FakeFS:
    """
    A fake filesystem to simulate fsspec behavior for unit tests.
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

    def glob(self, pattern, recursive=False):
        # For testing, we ignore the pattern and return all known paths.
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
    def test_invalid_path(self):
        """Test that a non-GitHub URL (missing 'github://') raises a ValueError."""
        with self.assertRaises(ValueError):
            crawl_repo_files("repo-crawler/repo-crawler")

    @patch("repo_crawler.crawl.fsspec.filesystem")
    def test_valid_path_with_exclusion(self, mock_filesystem):
        """
        Test that crawl_repo_files correctly prints file contents (with headers and line numbers)
        for valid files and excludes files with extensions listed in exclude_exts.
        """
        # Prepare a fake filesystem with:
        # - a valid text file,
        # - a file with an excluded extension,
        # - and a directory (which should be skipped).
        fake_files = {
            "github://user/repo/branch/file1.txt": ("hello\nworld\n", {'type': 'file'}),
            "github://user/repo/branch/file2.svg": ("should be excluded", {'type': 'file'}),
            "github://user/repo/branch/dir": ("", {'type': 'directory'}),
        }
        fake_fs = FakeFS(fake_files)
        mock_filesystem.return_value = fake_fs

        # Capture printed output
        captured_output = io.StringIO()
        original_stdout = sys.stdout
        sys.stdout = captured_output

        try:
            # Call the function with an exclusion for '.svg' files.
            crawl_repo_files("github://user/repo/branch", exclude_exts=['svg'])
            output = captured_output.getvalue()
        finally:
            sys.stdout = original_stdout

        # Check that file1.txt header and content were printed with line numbers.
        self.assertIn("# github://user/repo/branch/file1.txt", output)
        self.assertIn("1| hello", output)
        self.assertIn("2| world", output)

        # Ensure that file2.svg (and its content) is not printed.
        self.assertNotIn("file2.svg", output)
        self.assertNotIn("should be excluded", output)

if __name__ == '__main__':
    unittest.main()
