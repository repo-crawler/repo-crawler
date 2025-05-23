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
def fake_fs_with_files():
    """Fixture providing a FakeFS instance with test files."""
    files = {
        "github://user/repo/branch/file1.txt": ("hello\nworld\n", {'type': 'file'}),
        "github://user/repo/branch/file2.svg": ("should be excluded", {'type': 'file'}),
        "github://user/repo/branch/file3.py": ("print('hello')", {'type': 'file'}),
        "github://user/repo/branch/dir": ("", {'type': 'directory'}),
    }
    return FakeFS(files)

@patch("repo_crawler.crawl.verify_branch_exists", return_value=None)
@patch("repo_crawler.crawl.GithubFileSystem")
def test_include_dir_filtering(mock_filesystem, mock_verify):
    """
    Test that the --include_dir flag correctly limits the crawl to the specified directory.
    """
    # Set up a fake file system with files in different directories.
    files = {
        "github://user/repo/branch/file1.txt": ("outside", {'type': 'file'}),
        "github://user/repo/branch/src/file2.txt": ("inside", {'type': 'file'}),
        "github://user/repo/branch/src/sub/file3.txt": ("inside sub", {'type': 'file'}),
        "github://user/repo/branch/dir/file4.txt": ("outside dir", {'type': 'file'}),
    }
    fake_fs = FakeFS(files)

    # Override glob to simulate filtering by the include_dir.
    def filtered_glob(pattern, recursive):
        fake_fs.last_glob = pattern
        # Assuming the pattern is like "src/**", we extract "src" and return only paths under that directory.
        subdir = pattern[:-3]  # remove '/**'
        filtered = []
        for k in fake_fs.files.keys():
            # The path format is "github://user/repo/branch/<subdir>/..."
            parts = k.split("/")
            if len(parts) > 5 and parts[5] == subdir:
                filtered.append(k)
        return filtered

    fake_fs.glob = filtered_glob
    mock_filesystem.return_value = fake_fs

    # Run the crawl with include_dir set to "src"
    output_io = io.StringIO()
    crawl_repo_files("github://user/repo/branch", include_dir="src", out=output_io)

    # Verify that the glob pattern was constructed as expected.
    assert fake_fs.last_glob == "src/**"

    output = output_io.getvalue()
    # Check that only files under the "src" directory are processed.
    assert "# github://user/repo/branch/src/file2.txt" in output
    assert "# github://user/repo/branch/src/sub/file3.txt" in output
    # Files outside the "src" directory should not appear.
    assert "file1.txt" not in output
    assert "dir/file4.txt" not in output

# For tests that need a valid branch, we patch verify_branch_exists to do nothing.
@patch("repo_crawler.crawl.verify_branch_exists", return_value=None)
@patch("repo_crawler.crawl.GithubFileSystem")
def test_path_transformation(mock_filesystem, mock_verify, fake_fs_with_files):
    """
    Test that an input in the form "org/name" (without a prefix)
    is transformed properly and that the glob pattern is correctly constructed.
    """
    mock_filesystem.return_value = fake_fs_with_files
    # "repo-crawler/repo-crawler" will default to branch "main"
    # To prevent the "no files" error, we simulate that FakeFS returns files.
    crawl_repo_files("repo-crawler/repo-crawler", out=io.StringIO())
    expected_pattern = "**"
    assert fake_fs_with_files.last_glob == expected_pattern

@patch("repo_crawler.crawl.verify_branch_exists", return_value=None)
@patch("repo_crawler.crawl.GithubFileSystem")
def test_valid_path_with_exclusion(mock_filesystem, mock_verify, fake_fs_with_files, capsys):
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

@patch("repo_crawler.crawl.verify_branch_exists", return_value=None)
@patch("repo_crawler.crawl.GithubFileSystem")
def test_valid_path_with_inclusion(mock_filesystem, mock_verify, fake_fs_with_files, capsys):
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

@patch("repo_crawler.crawl.verify_branch_exists", return_value=None)
@patch("repo_crawler.crawl.GithubFileSystem")
def test_branch_with_forward_slash_colon_syntax(mock_filesystem, mock_verify):
    """
    Test that branch names with forward slashes work correctly with colon syntax.
    """
    files = {
        "feature/new-feature": ("feature content", {'type': 'file'}),
    }
    fake_fs = FakeFS(files)
    mock_filesystem.return_value = fake_fs

    # Test branch name with forward slash using colon syntax
    output_io = io.StringIO()
    crawl_repo_files("user/repo:feature/new-feature", out=output_io)
    
    # Verify that verify_branch_exists was called with the correct branch name
    mock_verify.assert_called_with("user", "repo", "feature/new-feature", None)
    
    # Verify that GithubFileSystem was initialized with the correct parameters
    mock_filesystem.assert_called_with(
        org="user", 
        repo="repo", 
        sha="feature/new-feature", 
        token=None, 
        username=None
    )

@patch("repo_crawler.crawl.verify_branch_exists", return_value=None)
@patch("repo_crawler.crawl.GithubFileSystem")
def test_branch_with_forward_slash_github_syntax_limitation(mock_filesystem, mock_verify):
    """
    Test that github:// syntax with forward slashes in branch names still works
    but the forward slash is interpreted as part of the path, not the branch name.
    This demonstrates the limitation of github:// syntax.
    """
    files = {
        "feature": ("feature content", {'type': 'file'}),
    }
    fake_fs = FakeFS(files)
    mock_filesystem.return_value = fake_fs

    # Test github:// syntax - the "new-feature" part will be treated as a subdir
    output_io = io.StringIO()
    crawl_repo_files("github://user/repo/feature/new-feature", out=output_io)
    
    # Verify that the branch is interpreted as "feature" and subdir as "new-feature"
    mock_verify.assert_called_with("user", "repo", "feature", None)
    
    # Verify the glob pattern includes the subdir
    assert fake_fs.last_glob == "new-feature/**"

@patch("repo_crawler.crawl.verify_branch_exists", return_value=None)
@patch("repo_crawler.crawl.GithubFileSystem")
def test_default_main_branch(mock_filesystem, mock_verify, fake_fs_with_files):
    """
    Test that the default branch "main" is used when no branch is specified.
    """
    mock_filesystem.return_value = fake_fs_with_files
    
    output_io = io.StringIO()
    crawl_repo_files("user/repo", out=output_io)
    
    # Verify that the default branch "main" is used
    mock_verify.assert_called_with("user", "repo", "main", None)
    mock_filesystem.assert_called_with(
        org="user", 
        repo="repo", 
        sha="main", 
        token=None, 
        username=None
    )

@patch("repo_crawler.crawl.verify_branch_exists", return_value=None)
@patch("repo_crawler.crawl.GithubFileSystem")
def test_complex_branch_name_with_multiple_slashes(mock_filesystem, mock_verify):
    """
    Test that branch names with multiple forward slashes work correctly.
    """
    files = {
        "complex": ("complex content", {'type': 'file'}),
    }
    fake_fs = FakeFS(files)
    mock_filesystem.return_value = fake_fs

    # Test branch name with multiple forward slashes
    output_io = io.StringIO()
    crawl_repo_files("user/repo:feature/sub-feature/final-name", out=output_io)
    
    # Verify that the entire branch name is preserved
    mock_verify.assert_called_with("user", "repo", "feature/sub-feature/final-name", None)
    mock_filesystem.assert_called_with(
        org="user", 
        repo="repo", 
        sha="feature/sub-feature/final-name", 
        token=None, 
        username=None
    )

def test_invalid_path_format():
    """
    Test that invalid path formats raise appropriate errors.
    """
    # Test path without org/repo structure
    with pytest.raises(ValueError, match="must be in format 'org/repo'"):
        crawl_repo_files("invalid-path")
    
    # Test path with too many components in org/repo part
    with pytest.raises(ValueError, match="must be in format 'org/repo'"):
        crawl_repo_files("org/repo/extra:branch")

def test_include_exclude_mutual_exclusivity(monkeypatch):
    """
    Verify that using both --include and --exclude flags results in an error.
    This test simulates command-line arguments and expects a SystemExit.
    """
    test_args = ["prog", "github://user/repo/branch", "--include", "py", "--exclude", "txt"]
    monkeypatch.setattr(sys, "argv", test_args)
    with pytest.raises(SystemExit):
        main()

@patch("repo_crawler.crawl.verify_branch_exists", side_effect=ValueError("Branch 'invalidbranch' does not exist in repository 'user/repo'."))
def test_invalid_branch_error(mock_verify):
    """
    Test that a ValueError with an appropriate message is raised
    when the branch verification fails due to an invalid branch.
    """
    invalid_path = "github://user/repo/invalidbranch"
    with pytest.raises(ValueError, match=r"Branch 'invalidbranch' does not exist in repository 'user/repo'."):
        crawl_repo_files(invalid_path)

@patch("repo_crawler.crawl.verify_branch_exists", side_effect=ValueError("Branch 'feature/non-existent' does not exist in repository 'user/repo'."))
def test_invalid_branch_with_slash_error(mock_verify):
    """
    Test that branch validation works correctly for branch names with forward slashes.
    """
    invalid_path = "user/repo:feature/non-existent"
    with pytest.raises(ValueError, match=r"Branch 'feature/non-existent' does not exist in repository 'user/repo'."):
        crawl_repo_files(invalid_path)
