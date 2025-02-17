import fsspec
import argparse
import sys
import os
import logging
from pathlib import Path

def crawl_repo_files(github_path, exclude_exts=None, token=None, username=None, out=None):
    """
    Recursively crawls a GitHub repository using fsspec's GitHubFileSystem,
    printing each file's content with a header and numbered lines.

    The github_path can be provided in one of the following formats:
      1. github://<org>/<repo>/<branch>[/optional/path]
      2. <org>/<repo>:<branch> or <org>/<repo> (branch defaults to "main" if omitted)

    :param github_path: The GitHub repository path.
    :param exclude_exts: A list of file extensions to exclude (e.g., ['svg']).
    :param token: Optional GitHub token for accessing private repositories.
    :param username: Optional GitHub username for accessing private repositories.
    :param out: A file-like object to write the output to (default: sys.stdout).
    """
    if out is None:
        out = sys.stdout

    # Parse the input to extract org, repo, branch (ref), and optional subdirectory.
    if github_path.startswith("github://"):
        path_without_prefix = github_path[len("github://"):]
    else:
        # Support input like "org/repo:branch" or "org/repo"
        if ':' in github_path:
            repo_part, branch = github_path.split(":", 1)
        else:
            repo_part, branch = github_path, "main"
        path_without_prefix = f"{repo_part}/{branch}"

    parts = path_without_prefix.split('/')
    if len(parts) < 2:
        raise ValueError("Invalid GitHub path: must include at least org and repo.")
    org = parts[0]
    repo = parts[1]
    ref = parts[2] if len(parts) >= 3 else "main"
    # Anything after the branch is treated as an optional subdirectory.
    subdir = '/'.join(parts[3:]) if len(parts) > 3 else ""

    # Initialize the GitHub filesystem with the required parameters.
    fs = fsspec.filesystem("github", org=org, repo=repo, ref=ref, token=token, username=username)

    # Construct the glob pattern. Note: The GitHubFileSystem works with paths
    # relative to the repository root, so we use the subdir if provided.
    pattern = f"{subdir}/**" if subdir else "**"
    all_paths = fs.glob(pattern, recursive=True)

    for path in all_paths:
        try:
            info = fs.info(path)
        except Exception as e:
            print(f"Could not get info for {path}: {e}", file=out)
            continue

        # Skip if not a file.
        if info.get('type') != 'file':
            continue

        # Check file extension against exclusions.
        if exclude_exts:
            parts_split = path.rsplit('.', 1)
            if len(parts_split) == 2 and parts_split[1] in exclude_exts:
                continue

        # Print header with file path.
        print(f'# {path}', file=out)

        # Open and print file contents with line numbers.
        try:
            with fs.open(path, 'r') as f:
                for i, line in enumerate(f, start=1):
                    # Pad the line number to 5 digits.
                    print(f'{i:05d}| {line}', end='', file=out)
            # Insert a blank line between files.
            print(file=out)
        except Exception as e:
            print(f"Error reading {path}: {e}", file=out)

def main():
    parser = argparse.ArgumentParser(
        description="Crawl a GitHub repository and print each file's contents with line numbers."
    )
    parser.add_argument(
        "github_path",
        help=("The GitHub repository path to crawl. "
              "Examples: 'org/repo:branch' or 'org/repo' (defaults to branch 'main') "
              "or the full 'github://org/repo/branch[/optional/path]' format.")
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
    parser.add_argument(
        "--username",
        help="GitHub username for accessing private repositories (required if token is provided)",
        default=None
    )
    parser.add_argument(
        "--output",
        help=("Optional full output file path to write the scan results. "
              "The path must be an absolute path to a file (not a directory) and include a file extension."),
        default=None
    )
    args = parser.parse_args()

    # Set up basic logging configuration.
    logging.basicConfig(level=logging.INFO)

    if args.output:
        output_path = args.output

        # Validate that the output path is a full absolute path.
        if not os.path.isabs(output_path):
            raise ValueError("Output path must be a full absolute path.")
        # Ensure the output path does not end with a path separator (i.e. is not a directory).
        if output_path.endswith(os.sep):
            raise ValueError("Output path must be a file, not a directory.")
        # Check that the basename has an extension.
        if not os.path.splitext(os.path.basename(output_path))[1]:
            raise ValueError("Output file must have an extension.")

        output_dir = os.path.dirname(output_path)
        if not os.path.isdir(output_dir):
            # Create missing subdirectories and log each folder as it is created.
            p = Path(output_dir)
            missing_dirs = []
            while not p.exists() and p.parent != p:
                missing_dirs.append(p)
                p = p.parent
            for d in reversed(missing_dirs):
                logging.info(f"Creating directory: {d}")
                os.mkdir(d)

        # Open the output file and pass its handle to crawl_repo_files.
        with open(output_path, "w", encoding="utf-8") as out_file:
            crawl_repo_files(args.github_path, exclude_exts=args.exclude, token=args.token, username=args.username, out=out_file)
    else:
        crawl_repo_files(args.github_path, exclude_exts=args.exclude, token=args.token, username=args.username)

    # Enforce that if a token is provided, a username must be provided.
    if args.token and not args.username:
        parser.error("When using --token, you must also provide --username.")

    crawl_repo_files(args.github_path, exclude_exts=args.exclude, token=args.token, username=args.username)

if __name__ == "__main__":
    main()
