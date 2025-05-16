# Migrator Architecture Overview

## High-Level Architecture

The Migrator utility follows a modular architecture with clear separation of concerns. Here's how the components fit together:

```
┌─────────────────────┐     ┌─────────────────────┐
│  Command Interface  │     │     Setup Wizard    │
│  (__main__.py)      │────▶│  (utils/setup.py)   │
└─────────────────────┘     └─────────────────────┘
           │
           ▼
┌─────────────────────┐
│   Core Operations   │
│    (main.py)        │
└─────────────────────┘
       ┌───┴────┐
       │        │
       ▼        ▼
┌─────────┐  ┌───────────────┐
│ Package │  │ Configuration │
│Managers │  │   Trackers    │
└─────────┘  └───────────────┘
       │        │
       └────┬───┘
            ▼
     ┌─────────────┐
     │   Utility   │
     │  Functions  │
     └─────────────┘
            │
            ▼
     ┌─────────────┐
     │    System   │
     │ Interaction │
     └─────────────┘
```

## Component Interaction Flow

1. **User Interface Layer**
   - `migrator-init.sh` & `migrator.sh`: Entry points for user interaction
   - `__main__.py`: Command parsing and dispatching

2. **Core Logic Layer**
   - `main.py`: Implements the core operations like scan, backup, restore
   
3. **Domain-Specific Modules**
   - `package_managers/`: Handles package detection and management
   - `config_trackers/`: Handles configuration file tracking
   
4. **Utility Layer**
   - `utils/`: Provides support functionality used across the application

5. **System Interface Layer**
   - Various modules interact with system commands and filesystem

## Data Flow

1. **System Scanning**:
   - User initiates scan → Command interface invokes core scan operation
   - Core operation calls package managers to detect installed packages
   - Core operation calls config trackers to identify configuration files
   - Results stored in system state file

2. **Backup Creation**:
   - User initiates backup → Command interface invokes core backup operation
   - Core operation reads system state
   - Core operation serializes data to backup file
   - Config files are copied to backup location

3. **System Restoration**:
   - User initiates restore → Command interface invokes core restore operation
   - Core operation reads backup file
   - Package managers install detected packages
   - Config trackers restore configuration files

## Key Design Concepts

1. **Distribution Agnosticism**
   - Factory pattern to detect and use appropriate package managers
   - Abstract interfaces for package operations
   - Distribution detection and mapping

2. **Path Portability**
   - Path variable substitution for system-specific paths
   - Dynamic transformation during backup/restore

3. **Modular Extension**
   - Each package manager is a separate module
   - Each config tracker is a separate module
   - New package managers can be added by implementing the base interface

4. **Progressive Disclosure**
   - Simple commands for common operations
   - Advanced options available when needed
   - Dry-run capabilities for safety

## Persistent Data

- **System State**: JSON file at `~/.local/share/migrator/system_state.json`
- **User Preferences**: Config file at `~/.config/migrator/config.json`
- **Backups**: JSON and directory structure at configured backup location
- **Logs**: Log file at `~/.local/share/migrator/migrator.log`

## Core Abstractions

1. **PackageManager**: Abstract interface for package operations
2. **ConfigTracker**: Abstract interface for configuration tracking
3. **SystemState**: Representation of current system
4. **BackupFile**: Serialization format for backups 