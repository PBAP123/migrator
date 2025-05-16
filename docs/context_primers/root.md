# Root Directory Context Primer

## Overview
The root directory contains the main project files and setup scripts for the Migrator utility, which is a system migration tool for Linux that helps backup and restore packages and configurations across different Linux distributions.

## Key Files

### `migrator-init.sh`
Unified installer script that:
- Checks for required system dependencies
- Sets up a virtual environment
- Installs Migrator and creates wrapper scripts
- Provides an interactive menu for various actions
- Handles updates and troubleshooting

### `migrator.sh`
Wrapper script that gets copied to `~/.local/bin/migrator` to provide system-wide access to the utility. It:
- Automatically activates the virtual environment
- Passes commands to the actual Migrator implementation
- Handles environment setup needed to run Migrator from anywhere

### `setup.py`
Python package installation script that:
- Defines metadata about the project
- Lists dependencies
- Installs wrapper scripts to ~/.local/bin
- Sets up console scripts for command-line interaction

### `requirements.txt`
Contains the Python package dependencies:
- distro (for distribution detection)
- setuptools (for package resources)
- tqdm (for progress bars)

### `README.md`
Comprehensive documentation including:
- Feature descriptions
- Installation instructions
- Usage examples
- Command-line interface documentation
- Migration guides
- Troubleshooting

### `.gitignore`
Specifies files and directories to be ignored by Git version control.

### `LICENSE`
Contains the GNU Affero General Public License v3.0 (AGPL-3.0) that governs the project.

## Relationship to Other Parts
- The root directory serves as the entrypoint for installation and setup
- It contains scripts that connect to the actual implementation in the `src/` directory
- Installation from here deploys scripts to the user's PATH for system-wide access 