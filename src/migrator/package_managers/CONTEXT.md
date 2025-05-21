# Package Managers Directory (`src/migrator/package_managers/`) Context Primer

## Overview
The `package_managers` directory contains modules that interact with various Linux package management systems. These modules handle detecting installed packages, backing them up, and restoring them on new systems, even across different distributions.

## Key Files

### `__init__.py`
Package initialization file that likely exports commonly used classes and functions, and may register available package manager implementations.

### `base.py`
Defines the base abstract class or interface for package managers:
- Common package operations interface
- Abstract methods that must be implemented by specific package manager classes
- Utility functions for package handling

### `factory.py`
Implements a factory pattern for package manager creation:
- Detects available package managers on the system
- Creates appropriate package manager instances
- Handles fallbacks and compatibility

### `package_mapper.py`
Implements cross-distribution package equivalence detection:
- Built-in mappings for common packages across apt, dnf, and pacman
- Pattern matching for common package naming conventions
- Custom user mappings through a JSON configuration file
- Intelligent search for similar packages when exact matches aren't available

### `apt.py`
Handles Debian/Ubuntu APT package management:
- apt/apt-get/dpkg command interaction
- Debian package tracking
- Repository management for APT sources
- Package installation and version handling

### `dnf.py`
Handles Fedora/RHEL DNF/YUM package management:
- dnf/yum command interaction
- RPM package tracking
- Repository management for DNF
- Package installation and dependency handling

### `pacman.py`
Handles Arch Linux Pacman package management:
- pacman command interaction
- AUR helper detection and support
- Package tracking and installation
- Repository configuration

### `snap.py`
Handles Canonical's Snap package system:
- snapd interaction
- Snap package tracking
- Channel and revision handling
- Cross-distribution Snap package restoration

### `flatpak.py`
Handles Flatpak package management:
- flatpak command interaction
- Remote repository management
- Application and runtime tracking
- User vs. system installation handling
- Optimized package availability checking with cached remotes
- Performance-focused implementation for fast planning

### `appimage.py`
Handles AppImage applications:
- AppImage discovery and tracking
- Integration file management
- Desktop entry handling
- AppImage portability support

## Design Patterns
- Factory pattern for creating appropriate package manager instances
- Strategy pattern for different package management approaches
- Adapter pattern for unified interface to different package managers
- Command pattern for executing system commands
- Caching pattern for performance optimization in Flatpak handling

## Relationship to Other Parts
- Called by the main backup and restore routines in `main.py`
- Used for package detection in system scanning
- Works alongside config trackers to provide a complete system profile
- Implements the multi-distribution support described in the README.md 