from setuptools import setup, find_packages

setup(
    name='repo_crawler',
    version='0.1.0',
    description='A lightweight Python tool to crawl directories or GitHub repositories and print file contents with line numbers, with support for file exclusion.',
    author='Your Name',
    author_email='repo-crawler@googlegroups.com',
    url='https://github.com/repo-crawler/repo-crawler',
    packages=find_packages(),
    install_requires=[
        'fsspec',
    ],
    entry_points={
        'console_scripts': [
            'crawl-repo=repo_crawler.crawl:main',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
    ],
)
