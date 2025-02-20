import fsspec
from fsspec.implementations.github import GithubFileSystem
import argparse
import sys
import os
import logging
from pathlib import Path
import requests

def verify_branch_exists(org, repo, branch, token=None):
    """
    Verifies that the branch exists in the specified GitHub repository
    by querying the GitHub API. Raises a ValueError if the branch does not exist.
    """
    url = f"https://api.github.com/repos/{org}/{repo}/branches/{branch}"
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise ValueError(f"Branch '{branch}' does not exist in repository '{org}/{repo}'.")
    # If the branch exists, continue.

def crawl_repo_files(github_path, include_exts=None, exclude_exts=None, token=None, username=None, out=None):
    """
    Recursively crawls a GitHub repository using fsspec's GithubFileSystem,
    printing each file's content with a header and numbered lines.

    The github_path can be provided in one of the following formats:
      1. github://<org>/<repo>/<branch>[/optional/path]
      2. <org>/<repo>:<branch> or <org>/<repo> (branch defaults to "main" if omitted)

    :param github_path: The GitHub repository path.
    :param include_exts: A list of file extensions to include (e.g., ['py', 'txt']).
                         If provided, ONLY these files will be processed.
    :param exclude_exts: A list of file extensions to ignore (e.g., ['svg', 'png']).
                         This parameter is ignored if include_exts is provided.
    :param token: An optional GitHub personal access token.
    :param username: The GitHub username associated with the token. Required if token is provided.
    :param out: A file-like object to write the output to. Defaults to sys.stdout.
    """
    if out is None:
        out = sys.stdout

    # Parse the input path (supports various formats)
    if github_path.startswith("github://"):
        path_without_prefix = github_path[len("github://"):]
    else:
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
    subdir = '/'.join(parts[3:]) if len(parts) > 3 else ""

    # Verify that the specified branch actually exists.
    verify_branch_exists(org, repo, ref, token)

    fs = GithubFileSystem(org=org, repo=repo, sha=ref, token=token, username=username)

    # Build the glob pattern for recursive search.
    pattern = f"{subdir}/**" if subdir else "**"
    try:
        all_paths = fs.glob(pattern, recursive=True)
    except Exception as e:
        raise ValueError(
            f"Failed to access branch '{ref}' in repository '{org}/{repo}'. "
            "Please verify that the branch exists."
        ) from e

    # If no files are found, assume the branch may be empty.
    if not all_paths:
        raise ValueError(
            f"No files found in repository '{org}/{repo}' for branch '{ref}'. "
            "This may be because the branch does not exist or is empty."
        )

    for path in all_paths:
        try:
            info = fs.info(path)
        except Exception as e:
            print(f"Could not get info for {path}: {e}", file=out)
            continue

        # Only process files (skip directories)
        if info.get('type') != 'file':
            continue

        # --- Filtering Logic ---
        # If include_exts is provided, only process files with these extensions.
        # Otherwise, if exclude_exts is provided, skip files with those extensions.
        if include_exts:
            parts_split = path.rsplit('.', 1)
            if len(parts_split) < 2 or parts_split[1] not in include_exts:
                continue  # Skip file if its extension is not in the include list
        elif exclude_exts:
            parts_split = path.rsplit('.', 1)
            if len(parts_split) == 2 and parts_split[1] in exclude_exts:
                continue  # Skip file if its extension is in the exclude list

        # Print a header line with the file path
        print(f"# {path}", file=out)

        # Open the file and print its contents with 5-digit, zero-padded line numbers
        try:
            with fs.open(path, 'r') as f:
                for i, line in enumerate(f, start=1):
                    print(f"{i:05d}| {line}", end='', file=out)
                # Print a blank line after each file
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
    # Create a mutually exclusive group for include and exclude flags.
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--include",
        nargs='*',
        default=[],
        help="List of file extensions to include (e.g., py txt). If provided, ONLY these files are processed."
    )
    group.add_argument(
        "--exclude",
        nargs='*',
        default=[],
        help="List of file extensions to exclude (e.g., svg png)."
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

    # Enforce that if a token is provided, a username must also be provided.
    if args.token and not args.username:
        parser.error("When using --token, you must also provide --username.")

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
        with open(output_path, "w", encoding="utf-8") as out_file:
            crawl_repo_files(
                args.github_path,
                include_exts=args.include,
                exclude_exts=args.exclude,
                token=args.token,
                username=args.username,
                out=out_file
            )
    else:
        crawl_repo_files(
            args.github_path,
            include_exts=args.include,
            exclude_exts=args.exclude,
            token=args.token,
            username=args.username
        )

if __name__ == "__main__":
    main()
