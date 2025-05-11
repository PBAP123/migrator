#!/usr/bin/env python3
"""
Setup script for Linux Packages utility
"""

from setuptools import setup, find_packages

setup(
    name="linuxpackages",
    version="0.1.0",
    description="A system migration utility for Linux",
    author="n3o",
    author_email="n3o@example.com",
    url="https://github.com/n3o/linuxpackages",
    packages=find_packages(),
    package_dir={"": "src"},
    entry_points={
        "console_scripts": [
            "linuxpackages=__main__:main",
        ],
    },
    install_requires=[
        "distro",  # For better distribution detection
    ],
    python_requires=">=3.6",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: System :: Systems Administration",
    ],
) 