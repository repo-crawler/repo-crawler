import fsspec
import argparse

def crawl_repo_files(github_path, exclude_exts=None):
    """
    Recursively crawls a GitHub repository using fsspec's githubfs, printing each file's content 
    with a header and numbered lines.

    The github_path should be provided in the format:
        github://<user>/<repo>/<branch>[/optional/path]

    :param github_path: The GitHub repository path.
    :param exclude_exts: A list of file extensions to exclude (e.g., ['svg']).
    """
    if not github_path.startswith("github://"):
        raise ValueError("Only GitHub paths (starting with 'github://') are supported.")

    # Initialize GitHub filesystem using fsspec
    fs = fsspec.filesystem("github")
    
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
        if info.get('type', None) != 'file':
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
    parser.add_argument("github_path", help="The GitHub repository path to crawl (e.g., github://user/repo/branch)")
    parser.add_argument(
        "--exclude",
        nargs='*',
        default=[],
        help="List of file extensions to exclude (e.g., svg)"
    )
    args = parser.parse_args()
    
    crawl_repo_files(args.github_path, exclude_exts=args.exclude)

if __name__ == "__main__":
    main()
