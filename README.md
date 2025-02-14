# Repo Crawler

Repo Crawler is a lightweight, self-contained Python module that recursively crawls a specified directory (or local repository) and prints the contents of every file to standard output. Each file is preceded by a header showing its path, and every line in the file is prefixed with a line number. The tool also supports excluding files based on their extension (for example, SVG files).

## Features

- Recursively crawl a directory.
- Print file contents to stdout with:
  - A header displaying the file path.
  - Each line numbered.
- Option to exclude files with specific extensions.

## Installation

You can install Repo Crawler directly from GitHub using pip:

```bash
pip install git+https://github.com/repo-crawler/repo-crawler.git
```

## Usage

After installation, you can run the tool from the command line:

```bash
crawl-repo <directory> [--exclude EXTENSIONS]
```

For example, to crawl a directory while excluding SVG files:

```bash
crawl-repo ./my_repo --exclude svg
```

## Community and Administration

For discussion, support, and coordinating contributions, join our administration group at: **repo-crawler@googlegroups.com**

## License

This project is licensed under the MIT License.
