import pytest
from unittest.mock import patch
import io
import re
import sys

from repo_crawler.crawl import crawl_repo_files, main

class FakeFS:
    """
    A fake filesystem to simulate fsspec's GitHubFileSystem for testing.
    """
    def __init__(self, files):
        """
        Initialize FakeFS with a dictionary mapping file paths to tuples of (file_content, info_dict).
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

@pytest.fixture
def fake_fs():
    """Fixture providing an empty FakeFS instance."""
    return FakeFS({})

@pytest.fixture
def fake_fs_with_files():
    """Fixture providing a FakeFS instance with test files."""
    files = {
        "github://user/repo/branch/file1.txt": ("hello\nworld\n", {'type': 'file'}),
        "github://user/repo/branch/file2.svg": ("should be excluded", {'type': 'file'}),
        "github://user/repo/branch/file3.py": ("print('hello')", {'type': 'file'}),
        "github://user/repo/branch/dir": ("", {'type': 'directory'}),
    }
    return FakeFS(files)

@patch("repo_crawler.crawl.fsspec.filesystem")
def test_path_transformation(mock_filesystem, fake_fs):
    """
    Test that an input in the form "org/name" (without a prefix)
    is transformed properly and that the glob pattern is correctly constructed.
    """
    mock_filesystem.return_value = fake_fs
    crawl_repo_files("repo-crawler/repo-crawler")
    expected_pattern = "**"
    assert fake_fs.last_glob == expected_pattern

@patch("repo_crawler.crawl.fsspec.filesystem")
def test_valid_path_with_exclusion(mock_filesystem, fake_fs_with_files, capsys):
    """
    Test that files with extensions in the exclusion list are skipped.
    """
    mock_filesystem.return_value = fake_fs_with_files
    crawl_repo_files("github://user/repo/branch", exclude_exts=['svg'])
    captured = capsys.readouterr()
    output = captured.out

    # Ensure file1.txt and file3.py are processed, but file2.svg is excluded.
    assert re.search(r"^# github://user/repo/branch/file1\.txt$", output, re.MULTILINE)
    assert "file2.svg" not in output
    assert "file3.py" in output

@patch("repo_crawler.crawl.fsspec.filesystem")
def test_valid_path_with_inclusion(mock_filesystem, fake_fs_with_files, capsys):
    """
    Test that only files with extensions in the inclusion list are processed.
    """
    mock_filesystem.return_value = fake_fs_with_files
    crawl_repo_files("github://user/repo/branch", include_exts=['py'])
    captured = capsys.readouterr()
    output = captured.out

    # Only file3.py should be processed.
    assert "file1.txt" not in output
    assert "file2.svg" not in output
    assert re.search(r"^# github://user/repo/branch/file3\.py$", output, re.MULTILINE)
    assert re.search(r"^00001\| print\('hello'\)$", output, re.MULTILINE)

def test_include_exclude_mutual_exclusivity(monkeypatch):
    """
    Verify that using both --include and --exclude flags results in an error.
    This test simulates command-line arguments and expects a SystemExit.
    """
    test_args = ["prog", "github://user/repo/branch", "--include", "py", "--exclude", "txt"]
    monkeypatch.setattr(sys, "argv", test_args)
    with pytest.raises(SystemExit):
        main()
