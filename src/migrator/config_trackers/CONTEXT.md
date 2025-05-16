# Config Trackers Directory (`src/migrator/config_trackers/`) Context Primer

## Overview
The `config_trackers` directory contains modules responsible for tracking, backing up, and restoring various types of configuration files on Linux systems. These trackers identify important configuration files, determine their portability, and manage their backup and restoration.

## Key Files

### `__init__.py`
Initializes the config trackers package and likely provides factory methods to create appropriate config tracker instances.

### `base.py`
Defines the base abstract class or interface for configuration trackers:
- Common configuration tracking methods
- Abstract methods that must be implemented by subclasses
- Utility functions for file operations
- Path handling and transformation

### `desktop_environment.py`
Handles desktop environment-specific configurations:
- Detection of installed desktop environments (GNOME, KDE, XFCE, etc.)
- Desktop environment settings tracking
- Window manager configurations
- Hardware-independent configuration identification
- Theme and appearance settings

### `user_config.py`
Manages user-specific configuration files:
- Home directory dotfiles (.bashrc, .profile, etc.)
- Application configurations (~/.config/*)
- User-installed application settings
- Shell and terminal configurations
- Application data that should be preserved

### `system_config.py`
Handles system-wide configuration files:
- Files in /etc and other system directories
- Network configuration
- Service configuration
- System-wide application settings
- Security policies

## Design Patterns
- Strategy pattern for different tracking approaches
- Template method pattern for configuration handling
- Adapter pattern for different configuration file formats

## Relationship to Other Parts
- Called by the main backup and restore routines in `main.py`
- Uses utilities from the `utils` directory for path handling and system detection
- Works alongside package managers to provide a complete system profile
- Implements the configuration handling features described in the README.md 