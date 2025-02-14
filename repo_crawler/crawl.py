import fsspec
import argparse

def crawl_repo_files(github_path, exclude_exts=None, token=None):
    """
    Recursively crawls a GitHub repository using fsspec's githubfs, printing each file's content 
    with a header and numbered lines.

    The github_path can be provided in one of the following formats:
      1. github://<user>/<repo>/<branch>[/optional/path]
      2. <org>/<name>:<branch> or <org>/<name> (branch defaults to "main" if omitted)

    :param github_path: The GitHub repository path.
    :param exclude_exts: A list of file extensions to exclude (e.g., ['svg']).
    :param token: Optional GitHub token for accessing private repositories.
    """
    # Allow input in org/name:branch or org/name format by defaulting to main branch if not provided.
    if not github_path.startswith("github://"):
        if ':' in github_path:
            repo_part, branch = github_path.split(":", 1)
        else:
            repo_part, branch = github_path, "main"
        github_path = f"github://{repo_part}/{branch}"

    # Initialize GitHub filesystem using fsspec (pass token if provided)
    fs = fsspec.filesystem("github", token=token) if token else fsspec.filesystem("github")
    
    # Construct a glob pattern for recursive file search
    pattern = github_path.rstrip('/') + '/**'
    all_paths = fs.glob(pattern, recursive=True)
    
    for path in all_paths:
        try:
            info = fs.info(path)
        except Exception as e:
            print(f"Could not get info for {path}: {e}")
            continue
        
        # Skip if not a file
        if info.get('type') != 'file':
            continue
        
        # Check file extension against exclusions
        if exclude_exts:
            parts = path.rsplit('.', 1)
            if len(parts) == 2 and parts[1] in exclude_exts:
                continue
        
        # Print header with file path
        print(f'# {path}')
        
        # Open and print file contents with line numbers
        try:
            with fs.open(path, 'r') as f:
                for i, line in enumerate(f, start=1):
                    print(f'{i}| {line}', end='')
        except Exception as e:
            print(f"Error reading {path}: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Crawl a GitHub repository and print each file's contents with line numbers."
    )
    parser.add_argument(
        "github_path",
        help=("The GitHub repository path to crawl. "
              "Examples: 'org/name:branch' or 'org/name' (defaults to branch 'main') "
              "or the full 'github://org/name/branch' format.")
    )
    parser.add_argument(
        "--exclude",
        nargs='*',
        default=[],
        help="List of file extensions to exclude (e.g., svg)"
    )
    parser.add_argument(
        "--token",
        help="GitHub token for accessing private repositories",
        default=None
    )
    args = parser.parse_args()
    
    crawl_repo_files(args.github_path, exclude_exts=args.exclude, token=args.token)

if __name__ == "__main__":
    main()
