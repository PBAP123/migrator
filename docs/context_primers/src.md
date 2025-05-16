# Source Directory (`src/`) Context Primer

## Overview
The `src/` directory contains the actual Python package implementation of the Migrator utility. It follows the Python package standard structure with the main implementation under the `migrator` subdirectory.

## Structure

### `src/migrator/`
The main package containing all implementation code. This contains:
- Core functionality modules
- Command-line interface implementation
- Utility subpackages

### `src/migrator.egg-info/`
Generated metadata directory created during installation that contains package information. This is not meant to be modified directly.

## Relationship to Other Parts
- The `src/` directory contains the actual implementation that's executed when users run the `migrator` command
- It implements the functionality advertised in the root-level README.md
- The code here is packaged and installed through the `setup.py` script in the root directory
- When installed, this code becomes accessible through the wrapper scripts (`migrator.sh`) 