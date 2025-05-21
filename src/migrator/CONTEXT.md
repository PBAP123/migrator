# Migrator Package (`src/migrator/`) Context Primer

## Overview
The `src/migrator` directory contains the core implementation of the Migrator utility. This is the main package where all the functionality of tracking, backing up, and restoring system packages and configurations is implemented.

## Key Files

### `__init__.py`
Simple initialization file that defines the package version.

### `__main__.py`
Entry point for running the Migrator as a module. It contains:
- Command-line argument parsing 
- Dispatching to appropriate functions based on user commands
- Interactive CLI menu implementation
- Main application flow control

### `main.py`
Core functionality implementation including:
- System scanning logic
- Backup creation and management
- Restoration functionality
- System state tracking
- Comparison logic between current system and backups
- Cross-distribution package equivalence detection during restore

## Subdirectories

### `utils/`
Contains utility functions and helper classes used throughout the application:
- Configuration handling
- System variable management
- Repository management utilities
- Progress tracking and display
- Distribution detection
- System service management
- File system handling
- Setup wizard implementation

### `config_trackers/`
Contains modules for tracking different types of configurations:
- Base classes for configuration tracking
- Desktop environment configuration handlers
- User configuration trackers
- System configuration trackers

### `package_managers/`
Contains modules for interacting with different package managers:
- Base package manager interface
- Implementation for various package managers (apt, dnf, pacman, etc.)
- Snap package support
- Flatpak support
- AppImage tracking
- Factory for detecting and creating appropriate package manager instances
- Package mapper for cross-distribution package equivalence detection

## Architectural Patterns
The codebase follows these design patterns:
- Factory pattern for package manager creation
- Strategy pattern for different configuration tracking approaches
- Command pattern for CLI operations
- Adapter pattern for cross-package-manager compatibility

## Relationship to Other Parts
- The implementation here is accessed through the root-level wrapper scripts
- It uses the dependencies specified in requirements.txt
- It implements the functionality described in the README.md
- The package is installed by setup.py 