# Utils Directory (`src/migrator/utils/`) Context Primer

## Overview
The `utils` directory contains utility functions and helper classes that support the core functionality of the Migrator utility. These components handle common tasks that are needed across different parts of the application.

## Key Files

### `__init__.py`
Package initialization file that may export commonly used utilities.

### `setup_wizard.py`
Implements an interactive setup wizard that guides users through initial configuration:
- Backup content configuration selection
- Backup destination selection
- Backup retention rules setup
- Backup scheduling configuration

### `sysvar.py`
Handles system variables and path transformations:
- Detection of usernames, hostnames, and home directories
- Path variable substitution for portability
- Adaptation of paths between source and target systems

### `repositories.py`
Manages software repositories and package sources:
- Repository detection and tracking
- Repository compatibility checking between distributions
- Repository restoration on target systems
- Support for different repository formats (APT, DNF, Flatpak remotes, etc.)

### `repositories_test.py`
Test cases for the repositories module.

### `config.py`
Manages Migrator's own configuration settings:
- Reading/writing configuration files
- Default settings management
- User preference handling

### `fstab.py`
Handles filesystem table (fstab) entries:
- Scanning and parsing /etc/fstab
- Identifying portable vs. hardware-specific entries
- Backup and restoration of appropriate mount configurations

### `service.py`
Manages Migrator's service installation and configuration:
- systemd service file creation
- Service scheduling configuration
- Service status checking and management
- Timer configuration

### `progress.py`
Provides visual feedback mechanisms:
- Progress bars
- Spinners
- Status updates
- Completion summaries

### `distro.py`
Handles distribution detection and compatibility:
- Linux distribution identification
- Version detection
- Package manager compatibility mapping
- Cross-distribution package mapping

## Design Patterns
- Facade pattern to simplify complex operations
- Strategy pattern for different implementations based on detected environment
- Observer pattern for progress reporting

## Relationship to Other Parts
- Provides essential functionality used across the main implementation modules
- Supports the core backup/restore capabilities implemented in main.py
- Interfaces with system commands and external tools
- Used by the command handlers in __main__.py 