import io
import re
import sys
import pytest

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

def test_path_transformation(monkeypatch):
    """
    Test that an input in the form "org/name" (without a prefix)
    is transformed properly and that the glob pattern is correctly constructed.
    Since the GitHub filesystem is initialized with org, repo, and ref,
    the glob pattern is relative to the repository root.
    """
    fake_fs = FakeFS({})
    monkeypatch.setattr("repo_crawler.crawl.fsspec.filesystem", lambda *args, **kwargs: fake_fs)

    # Call with an input missing the 'github://' prefix.
    crawl_repo_files("repo-crawler/repo-crawler")

    # With no subdirectory provided, the glob pattern should be just "**"
    expected_pattern = "**"
    assert fake_fs.last_glob == expected_pattern

def test_valid_path_with_exclusion(monkeypatch, capsys):
    """
    Test that crawl_repo_files prints file contents with headers and line numbers
    for valid files, and that files with excluded extensions are skipped.
    """
    fake_files = {
        "github://user/repo/branch/file1.txt": ("hello\nworld\n", {'type': 'file'}),
        "github://user/repo/branch/file2.svg": ("should be excluded", {'type': 'file'}),
        "github://user/repo/branch/dir": ("", {'type': 'directory'}),
    }
    fake_fs = FakeFS(fake_files)
    monkeypatch.setattr("repo_crawler.crawl.fsspec.filesystem", lambda *args, **kwargs: fake_fs)

    crawl_repo_files("github://user/repo/branch", exclude_exts=['svg'])
    captured = capsys.readouterr().out

    assert "# github://user/repo/branch/file1.txt" in captured
    assert "00001| hello" in captured
    assert "00002| world" in captured

    assert "file2.svg" not in captured
    assert "should be excluded" not in captured

    import re
    assert re.search(r"world\n\n", captured)

def test_minimal_stdout_capture(capsys):
    print("hello world")
    captured = capsys.readouterr().out
    assert "hello world" in captured
