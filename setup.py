#!/usr/bin/env python3
"""
Setup script for Migrator utility

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

from setuptools import setup, find_namespace_packages
import os
import shutil
from pathlib import Path

# Copy wrapper scripts to a bin directory
def install_wrapper_scripts():
    """Install the wrapper scripts to a location in PATH"""
    # Get the current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    wrapper_script = os.path.join(current_dir, 'migrator.sh')
    
    # Default target locations
    user_bin_dir = os.path.expanduser('~/.local/bin')
    
    # Ensure target directory exists
    os.makedirs(user_bin_dir, exist_ok=True)
    
    # Copy the main script
    main_target_path = os.path.join(user_bin_dir, 'migrator')
    shutil.copy2(wrapper_script, main_target_path)
    os.chmod(main_target_path, 0o755)  # Make executable
    
    # Create TUI wrapper script
    tui_content = """#!/bin/bash
# Wrapper script for migrator-tui

# Path to the unified installer
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
UNIFIED_SCRIPT="${SCRIPT_DIR}/../migrator-init.sh"

# If the unified script exists and is executable, use it
if [ -f "$UNIFIED_SCRIPT" ] && [ -x "$UNIFIED_SCRIPT" ]; then
    exec "$UNIFIED_SCRIPT" tui "$@"
else
    # Otherwise, find the migrator-tui.py file
    # Directory of the original repository
    REPO_DIR="$(cd "$(dirname "$(dirname "$(readlink -f "$0")")")"/.. && pwd)"
    TUI_SCRIPT="${REPO_DIR}/migrator-tui.py"
    
    # Check if we're in a virtual environment
    if [ -z "$VIRTUAL_ENV" ]; then
        # Try to find and activate the migrator virtual environment
        VENV_PATH="$HOME/.venvs/migrator"
        if [ -d "$VENV_PATH" ] && [ -f "$VENV_PATH/bin/activate" ]; then
            source "$VENV_PATH/bin/activate"
        else
            echo "Error: Not in a virtual environment and couldn't find the Migrator virtual environment."
            echo "Please run the migrator-init.sh script first to set up the environment."
            exit 1
        fi
    fi
    
    # Run the TUI script
    if [ -f "$TUI_SCRIPT" ]; then
        exec python3 "$TUI_SCRIPT" "$@"
    else
        echo "Error: Could not find the migrator-tui.py script."
        echo "Please run the migrator-init.sh script to set up Migrator properly."
        exit 1
    fi
fi
"""
    
    # Write and install the TUI wrapper
    tui_target_path = os.path.join(user_bin_dir, 'migrator-tui')
    with open(tui_target_path, 'w') as f:
        f.write(tui_content)
    os.chmod(tui_target_path, 0o755)  # Make executable
    
    # Create a symlink to the unified script if it exists
    unified_script = os.path.join(current_dir, 'migrator-init.sh')
    if os.path.exists(unified_script):
        unified_target_path = os.path.join(user_bin_dir, 'migrator-init')
        try:
            if os.path.exists(unified_target_path):
                os.remove(unified_target_path)
            os.symlink(unified_script, unified_target_path)
        except Exception as e:
            print(f"Warning: Could not create symlink to unified script: {e}")
    
    print(f"Wrapper scripts installed to {user_bin_dir}")
    
    # Check if the directory is in PATH
    if user_bin_dir not in os.environ.get('PATH', '').split(os.pathsep):
        shell_profile = os.path.expanduser('~/.bashrc')
        print(f"\nNOTE: {user_bin_dir} is not in your PATH.")
        print(f"You may need to add this line to your {shell_profile}:")
        print(f"    export PATH=\"{user_bin_dir}:$PATH\"")
        print("Then restart your terminal or run:")
        print(f"    source {shell_profile}")

# Run the installation if this is being installed (not just built)
if not os.environ.get('READTHEDOCS') and any(arg.startswith('install') for arg in os.sys.argv[1:]):
    try:
        install_wrapper_scripts()
    except Exception as e:
        print(f"Warning: Failed to install wrapper scripts: {e}")

setup(
    name="migrator",
    version="0.1.0",
    description="A system migration utility for Linux",
    author="Ali Price",
    author_email="ali.price@pantheritservices.co.uk",
    url="https://github.com/PBAP123/migrator",
    package_dir={"": "src"},
    packages=find_namespace_packages(where="src"),
    entry_points={
        "console_scripts": [
            "migrator=migrator.__main__:main",
        ],
    },
    install_requires=[
        "distro>=1.5.0",  # For better distribution detection
        "setuptools>=42.0.0",  # For pkg_resources
        "tqdm>=4.60.0",   # For progress bars
    ],
    extras_require={},  # We'll handle optional dependencies separately
    python_requires=">=3.6",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: System :: Systems Administration",
    ],
    scripts=['migrator.sh', 'migrator-tui.py'],
) 