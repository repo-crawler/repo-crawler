import pytest
from repo_crawler.crawl import crawl_repo_files

def test_invalid_github_path():
    with pytest.raises(ValueError):
        crawl_repo_files("not_github://invalid")
