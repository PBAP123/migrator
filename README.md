# Migrator

A system migration utility for Linux that tracks installed packages and configuration files, making it easy to migrate to a new system.

## Why Migrator?

Migrator captures everything that makes your Linux system uniquely yours - from system packages to user configurations - and helps you transplant that environment to any Linux distribution.

**Tired of starting from scratch every time you set up a new Linux system?** Migrator is the all-in-one solution that tracks your entire Linux environment and recreates it anywhere with minimal effort.

### Perfect For:

- **Distro-hoppers** wanting to try new distributions without losing their setup
- **IT professionals** needing to replicate environments across multiple machines
- **System administrators** managing consistent deployments
- **Anyone** upgrading hardware who wants their familiar environment instantly

### What Sets Migrator Apart:

- **Distribution-agnostic** - Works across all major Linux distributions
- **Comprehensive tracking** - Monitors all package types (apt, snap, flatpak, AppImage)
- **User-friendly** - Intuitive command-line interface makes migration simple
- **No cloud required** - Your data stays local and private
- **Zero lock-in** - Open source and community-driven

Don't waste hours reinstalling packages and reconfiguring settings. With Migrator, your entire system profile is just one command away from being restored on any Linux machine.

## Features

- **Multi-Distribution Support**: Works on any Linux distribution by automatically detecting package managers.
- **Package Tracking**: Tracks packages from various sources:
  - Distribution-specific packages (apt, dnf, pacman, etc.)
  - Snap packages
  - Flatpak packages
  - AppImages
- **Cross-Distribution Package Mapping**: Intelligently maps packages between different package managers:
  - Finds equivalent packages when migrating between distributions (e.g., apt to dnf)
  - Uses built-in mappings for common packages
  - Applies pattern matching for package naming conventions
  - Supports user-defined custom mappings
- **Configuration Tracking**: Identifies and tracks both system and user configuration files.
- **Desktop Environment Backup**: Preserves your personalized desktop experience (included by default):
  - Gnome settings and extensions
  - KDE Plasma configurations
  - XFCE, LXDE, Cinnamon, MATE settings
  - Common window managers (i3, awesome, bspwm, etc.)
  - Hardware-independent configurations only
  - Note: .desktop files (desktop shortcuts) are not backed up as they are automatically regenerated during package installation
- **Incremental Backup**: Monitors changes to packages and configurations over time.
- **Custom Backup Destinations**: Choose where your backups are stored:
  - Define any local folder or network share as your backup location
  - Configuration persists between sessions
- **Multi-System Backup Organization**: Organize backups from multiple computers:
  - Automatically creates subdirectories based on hostname for each system
  - Prevents file conflicts when backing up multiple machines to the same location
  - Provides commands for easily listing and managing backups by host
  - Compatible with existing backup files created before this feature
- **Dynamic Path Handling**: Intelligent system-specific path handling:
  - Automatically detects usernames and home directory paths during backup
  - Adapts paths to match the target system during restoration
  - Makes configuration files portable across different systems
- **Selective Fstab Entry Backup**: Smart handling of mount entries:
  - Analyzes /etc/fstab during backup and identifies portable entries
  - Only backs up entries for network shares, special filesystems and non-hardware-specific mounts
  - Ensures hardware-dependent entries aren't transferred between systems
- **Interactive Restore Process**: When restoring without specific options, prompts you about which parts to restore:
  - Guided experience that walks through each category (packages, configs, repositories, fstab)
  - Gives you control over exactly what parts of the backup to restore
  - Provides information about what's available in the backup for each category
- **Dry Run Mode**: Preview all changes before execution:
  - See exactly what packages will be installed
  - Review configuration files that will be modified
  - Identify path transformations that will be applied
  - Examine fstab entries that will be added
  - Discover potential conflicts before they occur
  - Get confirmation before proceeding with actual changes
- **Migration Planning**: Generates a plan for installing packages on a new system.
- **Configuration Restoration**: Helps restore configuration files to their original locations.
- **Service Management**: Run as a background service with automatic checks.
  - Run as a system-wide or user service
  - Schedule service based on specific times of day
  - Configure daily, weekly, or monthly execution
  - Use advanced systemd timer scheduling
- **Interactive Progress Tracking**: Real-time visual feedback for all operations:
  - Progress bars show overall completion percentage
  - Live status updates for what's currently being processed
  - Running counts of processed items and remaining tasks
  - Spinner animations for operations with unknown duration
  - Detailed summaries upon completion
  - Graceful fallback when running in environments without visual progress support

### Package Management
- Scans system and backs up installed package information
- Detects manually installed packages vs dependencies
- Restores manually installed packages on a new system
- Supports APT, DNF, Pacman, Flatpak, Snap, and AppImage
- Maps packages between different package managers during cross-distribution migration
- Allows custom package equivalence mappings through user-editable configuration
- Restores compatible packages when switching Linux distributions
- Intelligent version handling with configurable policies

### Configuration Files
- Identifies and backs up important system and user configuration files
- Applies path transformations during restore to adapt to new user/hostname/paths
- Includes desktop environment configurations for major desktop environments
- Supports cross-distribution transfers where configurations are compatible

### Filesystem Support
- Special handling for fstab entries with automatic adaptation to new systems
- Extracts portable mount information that can be safely transferred
- Preserves UUIDs and mount points between systems
- Automatic backup and restoration of mount options

### Software Repositories
- Backs up custom software repositories and sources (APT, DNF, PPAs, Flatpak remotes, etc.)
- Restores compatible repositories when migrating
- Provides conflict detection for repositories that aren't compatible across distributions
- Supports multiple package managers' repository formats

### Backup Management
- Organizes backups by host for multi-system management
- Retention policies to automatically manage backup storage
- Timestamps and detailed metadata for all backups
- Compatible with existing backup files created before this feature

## Quickstart Guide

### Simple Installation (Recommended)

```bash
# Clone the repository
git clone https://github.com/PBAP123/migrator.git
cd migrator

# Make sure the installer script is executable
chmod +x migrator-init.sh

# Run the interactive installer script
./migrator-init.sh
```

That's it! The interactive installer will:

1. Check for required system dependencies
2. Install missing Python packages automatically
3. Set up the virtual environment with all necessary libraries
4. Install Migrator and create wrapper scripts
5. Present you with a menu of actions to take

The installer offers these features:
- **Interactive menu** with clear status indicators
- **Automatic detection** of installation issues
- **Self-healing** capabilities to fix common problems
- **Update functionality** to easily update when you pull changes

## Using Migrator

After installation, you have several ways to use Migrator depending on your situation:

### Which Method Should I Use?

| If you want to... | Use this method |
|-------------------|-----------------|
| Install for the first time | `./migrator-init.sh` |
| Update after git pull | `./migrator-init.sh update` |
| Use Migrator day-to-day (Recommended) | `migrator` command or CLI menu |
| Fix installation issues | `./migrator-init.sh` |
| Get quick help | `./migrator-init.sh help` |

### Regular Usage (After Installation)

Once Migrator is installed, the recommended way to use it is through the CLI interface:

```bash
# Run commands directly from terminal (Recommended)
migrator scan                    # Scan your system
migrator backup                  # Create a backup
migrator restore backup.json     # Restore from a backup

# Or use the CLI menu
./migrator-init.sh               # Select option 2
```

These commands work from any directory and provide the most reliable experience for daily use.

### Using the CLI Menu

The command-line interface (CLI) menu provides access to all Migrator functions in a simple text-based format:

```
Available commands:
1) scan           - Scan system packages and configurations
2) backup         - Create a backup of your system
3) restore        - Restore from a backup
4) compare        - Compare current system with a backup
5) check          - Check for changes since last scan
6) service        - Manage Migrator service
7) help           - Show detailed help
q) quit           - Exit the menu
```

You can access it directly:
```bash
# Via the interactive menu
./migrator-init.sh
# Select option 2) Run Migrator command line
```

## Common Tasks

### Creating a Backup

To create a complete system backup:

```bash
# Step 1: Scan your system (desktop configs are included by default)
migrator scan

# Step 2: Create the backup (stores in ~/migrator_backups by default)
migrator backup

# Or specify a custom location
migrator backup /path/to/backup/directory
```

The backup will be saved as a JSON file with a timestamp, such as `migrator_backup_20230101_120000.json`.

### Restoring from a Backup

When setting up a new system:

```bash
# Step 1: Install Migrator on the new system
./migrator-init.sh

# Step 2: Find your backup file (scans drives automatically)
migrator locate-backup

# Step 3: Generate an installation plan (recommended before restoring)
migrator plan PATH_TO_YOUR_BACKUP.json

# Step 4: Preview what will be restored (recommended)
migrator restore PATH_TO_YOUR_BACKUP.json --dry-run

# Step 5: Perform the actual restoration
migrator restore PATH_TO_YOUR_BACKUP.json --execute
```

#### Using the Plan Function

The `plan` function is an essential step before performing a restoration, especially when migrating between different Linux distributions:

```bash
# Generate a detailed installation plan
migrator plan PATH_TO_YOUR_BACKUP.json
```

This command:
- Maps packages from your source distribution to the target distribution
- Intelligently finds equivalent packages across different package managers
- Uses built-in mappings and pattern matching for package equivalence detection
- Creates a detailed plan for installing compatible packages
- Identifies packages that may need to be manually handled
- Recommends equivalent packages when direct matches aren't available
- Helps you understand what will happen during the actual restoration

Use the plan function before restoring to ensure you have a clear understanding of how packages will be mapped and installed on your new system. This is particularly valuable when migrating between different package managers (e.g., from apt to dnf).

When using `--execute` without specific category flags, Migrator will enter interactive mode and prompt you about each category of content to restore. This gives you fine-grained control over the restore process without having to remember all the command line options.

### Comparing Systems

To see what's changed between your current system and a backup:

```bash
# Compare current system with a backup
migrator compare PATH_TO_YOUR_BACKUP.json
```

### Using Plan vs Compare

#### Understanding the Difference

Migrator offers two powerful analysis tools that serve different purposes in your migration workflow:

**Compare Function (`migrator compare`):**
- Shows differences between your current system state and a backup
- Identifies packages and config files that have been added or removed since the backup
- Best used when you want to assess how your current system has changed over time
- Helpful for identifying drift between systems or tracking changes since a backup was made
- Focuses on what changed rather than what needs to be installed

**Plan Function (`migrator plan`):**
- Generates a detailed installation plan from a backup
- Maps packages from source distribution to target distribution
- Best used before performing a restoration to understand what will happen
- Creates a roadmap for migration, especially between different Linux distributions
- Focuses specifically on installation strategy, package mapping, and compatibility

#### When to Use Each Tool

Use **Compare** when you want to:
- Audit changes between your current system and a previous state
- Find out what packages or configs were added or removed
- Identify system drift from a baseline
- Track changes over time with regular comparisons

Use **Plan** when you want to:
- Prepare for a migration or restoration
- Understand how packages will map between distributions
- See what installation commands will be run
- Identify potential compatibility issues before they occur
- Create a roadmap for migration between different systems

#### Best Practices

1. **Before a restore operation:**
   - Run `migrator plan` to get a detailed roadmap for installation
   - Review the plan to understand how packages will be mapped

2. **After a restoration:**
   - Use `migrator compare` to verify the restoration matched expectations
   - Identify any remaining differences between systems

3. **For ongoing system management:**
   - Run regular `migrator compare` operations against a baseline backup
   - Track system changes and drift over time

### Setting Up as a Service

Migrator can run regular checks as a system service:

```bash
# Install as a system service
migrator install-service

# Install as a user service (no sudo required)
migrator install-service --user

# Schedule daily checks at a specific time
migrator install-service --daily "03:00"
```

### Customizing Package Mappings

To edit the package equivalence mappings for cross-distribution migration:

```bash
# Open the package mappings file in your default editor
migrator edit-mappings
```

This allows you to customize how packages are mapped between different distributions. For example, you can add entries like:

```json
"firefox-esr": {
  "apt": "firefox-esr",
  "dnf": "firefox",
  "pacman": "firefox"
}
```

The mappings file is located at `~/.config/migrator/package_mappings.json` and can also be edited directly.

## Updating Migrator

### Updating After Code Changes

When you pull updates from the Git repository, follow these steps to update your Migrator installation:

```bash
# Step 1: Pull the latest changes
git pull origin main  # or whatever branch you're using

# Step 2: Update Migrator using the built-in update command
./migrator-init.sh update
```

The update process will:
1. Upgrade all dependencies including setuptools
2. Reinstall Migrator with the latest changes
3. Recreate wrapper scripts to ensure they're up to date
4. Check for and fix any common issues

Alternatively, you can use the interactive menu:
```bash
# Launch the interactive menu
./migrator-init.sh

# Select option 3) Update Migrator
```

If you encounter any issues after updating, you can perform a clean installation:
```bash
# Select option 4) Clean installation from the menu
./migrator-init.sh

# Or use the command line:
rm -rf ~/.venvs/migrator
./migrator-init.sh
```

## Common Issues and Solutions

If you encounter any of these issues:

- **Missing dependencies**: The installer will automatically detect and install required packages
- **Wrapper script issues**: Use `./migrator-init.sh` directly or select the "Fix PATH" option
- **Module import errors**: Try updating with `./migrator-init.sh update` or running a clean installation

## Features

- **Multi-Distribution Support**: Works on any Linux distribution by automatically detecting package managers.
- **Package Tracking**: Tracks packages from various sources:
  - Distribution-specific packages (apt, dnf, pacman, etc.)
  - Snap packages
  - Flatpak packages
  - AppImages
- **Cross-Distribution Package Mapping**: Intelligently maps packages between different package managers:
  - Finds equivalent packages when migrating between distributions (e.g., apt to dnf)
  - Uses built-in mappings for common packages
  - Applies pattern matching for package naming conventions
  - Supports user-defined custom mappings
- **Configuration Tracking**: Identifies and tracks both system and user configuration files.
- **Desktop Environment Backup**: Preserves your personalized desktop experience:
  - Gnome settings and extensions
  - KDE Plasma configurations
  - XFCE, LXDE, Cinnamon, MATE settings
  - Common window managers (i3, awesome, bspwm, etc.)
  - Hardware-independent configurations only
- **Incremental Backup**: Monitors changes to packages and configurations over time.
- **Custom Backup Destinations**: Choose where your backups are stored:
  - Define any local folder or network share as your backup location
  - Configuration persists between sessions
- **Multi-System Backup Organization**: Organize backups from multiple computers:
  - Automatically creates subdirectories based on hostname for each system
  - Prevents file conflicts when backing up multiple machines to the same location
  - Provides commands for easily listing and managing backups by host
  - Compatible with existing backup files created before this feature
- **Dynamic Path Handling**: Intelligent system-specific path handling:
  - Automatically detects usernames and home directory paths during backup
  - Adapts paths to match the target system during restoration
  - Makes configuration files portable across different systems
- **Selective Fstab Entry Backup**: Smart handling of mount entries:
  - Analyzes /etc/fstab during backup and identifies portable entries
  - Only backs up entries for network shares, special filesystems and non-hardware-specific mounts
  - Ensures hardware-dependent entries aren't transferred between systems
- **Dry Run Mode**: Preview all changes before execution:
  - See exactly what packages will be installed
  - Review configuration files that will be modified
  - Identify path transformations that will be applied
  - Examine fstab entries that will be added
  - Discover potential conflicts before they occur
  - Get confirmation before proceeding with actual changes
- **Migration Planning**: Generates a plan for installing packages on a new system.
- **Configuration Restoration**: Helps restore configuration files to their original locations.
- **Service Management**: Run as a background service with automatic checks.
  - Run as a system-wide or user service
  - Schedule service based on specific times of day
  - Configure daily, weekly, or monthly execution
  - Use advanced systemd timer scheduling
- **Interactive Progress Tracking**: Real-time visual feedback for all operations:
  - Progress bars show overall completion percentage
  - Live status updates for what's currently being processed
  - Running counts of processed items and remaining tasks
  - Spinner animations for operations with unknown duration
  - Detailed summaries upon completion
  - Graceful fallback when running in environments without visual progress support

## Requirements

- **Python**: Version 3.6 or higher
- **Linux OS**: Any distribution with standard package managers
- **Required Packages** (for Debian/Ubuntu):
  - `python3-venv`: Required for creating virtual environments
  - `python3-pip`: Required for installing Python packages
  - `python3-distro` or the `distro` Python package (v1.5.0 or higher)
  - `setuptools`: Required for package resources (installed automatically)
- **Access to package managers** for detection (apt, snap, flatpak, etc.)

## Installation

### Step 1: Install Required Dependencies

On Debian/Ubuntu systems:

```bash
# Install required system packages (use your Python version)
sudo apt install python3-venv python3-pip python3-distro

# For Python 3.12 specifically
# sudo apt install python3.12-venv
```

On Fedora/RHEL systems:

```bash
sudo dnf install python3-virtualenv python3-pip python3-distro
```

On Arch-based systems:

```bash
sudo pacman -S python-virtualenv python-pip python-distro
```

### Step 2: Clone the Repository

```bash
# Clone the repository
git clone https://github.com/PBAP123/migrator.git
cd migrator
```

### Step 3: Set Up a Virtual Environment

Modern Linux distributions (especially Debian/Ubuntu-based ones) enforce PEP 668, which prevents direct pip installations outside of virtual environments.

```bash
# Create a virtual environment
python3 -m venv ~/.venvs/migrator

# Activate the virtual environment
source ~/.venvs/migrator/bin/activate

# You should see (migrator) at the beginning of your prompt
# indicating the virtual environment is active
```

### Step 4: Install Migrator

```bash
# Make sure you're in the migrator directory with activated environment
# Install dependencies and the package
pip install -r requirements.txt
pip install -e .

# You should see a message about the wrapper script being installed
```

### Running Migrator Commands

After installation, there are two ways to run Migrator:

1. **Using the wrapper script (Recommended)**: 
   
   The installation process automatically creates a wrapper script at `~/.local/bin/migrator`. This script automatically handles virtual environment activation, so you can simply run:

   ```bash
   migrator scan
   ```

   Without having to manually activate the virtual environment. The wrapper automatically:
   - Detects and activates the Migrator virtual environment
   - Falls back to direct execution if no virtual environment is found
   - Works whether you're already in a virtual environment or not

   > **Note**: Make sure `~/.local/bin` is in your PATH. If you see a message about this during installation, follow the provided instructions.
   >
   > ```bash
   > # Add to your ~/.bashrc if needed:
   > export PATH="$HOME/.local/bin:$PATH"
   > 
   > # Then reload your profile
   > source ~/.bashrc
   > ```

2. **Manual virtual environment activation**:

   ```bash
   source ~/.venvs/migrator/bin/activate
   migrator scan
   ```

### Alternative: Using pipx

If you prefer, you can use pipx which manages virtual environments automatically:

```bash
# Install pipx if you don't have it
sudo apt install pipx  # or equivalent for your distribution
pipx ensurepath

# Install Migrator
cd migrator
pipx install -e .

# Run commands directly
migrator scan
```

### Troubleshooting

If you encounter issues:

1. Make sure you have the required packages installed:
   ```bash
   sudo apt install python3-venv python3-pip python3-distro
   ```

2. If you get a "command not found" error when running migrator:
   ```bash
   # Add ~/.local/bin to your PATH
   echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
   source ~/.bashrc
   ```

3. If you have problems with the virtual environment:
   ```bash
   # Remove and recreate it
   rm -rf ~/.venvs/migrator
   python3 -m venv ~/.venvs/migrator
   source ~/.venvs/migrator/bin/activate
   ```

## Usage

### Command-Line Interface

Once installed:

```bash
# Scan the system and update the system state
migrator scan

# Backup with dynamic path variable handling (enabled by default)
migrator backup ~/backups

# Backup without path variable substitution
migrator backup ~/backups --no-path-variables

# Backup with selective fstab entry handling (enabled by default)
migrator backup ~/backups

# Backup without portable fstab entries
migrator backup ~/backups --no-fstab-portability

# View or modify the default backup location
migrator config get-backup-dir  # Show current backup directory
migrator config set-backup-dir /path/to/backup  # Set a new default backup location

# Create a backup using the default location (no path needed)
migrator backup

# Preview all changes a restore would make without applying them (dry run mode)
migrator restore ~/backups/migrator_backup_20230101_120000.json --dry-run

# Restore with automatic path transformation (enabled by default)
migrator restore ~/backups/migrator_backup_20230101_120000.json --execute

# Restore with interactive prompts for each category
migrator restore ~/backups/migrator_backup_20230101_120000.json --execute

# Restore without transforming paths (keep them as-is from the source system)
migrator restore ~/backups/migrator_backup_20230101_120000.json --execute --no-path-transform

# Configure backup retention rules to manage storage space
migrator config backup-retention get  # Show current retention settings
migrator config backup-retention enable  # Enable automatic backup cleanup
migrator config backup-retention disable  # Disable automatic backup cleanup
migrator config backup-retention set-count 5  # Keep only the last 5 backups
migrator config backup-retention set-age 30  # Keep backups newer than 30 days

# Preview path transformations without actually making changes
migrator restore ~/backups/migrator_backup_20230101_120000.json --path-transform-preview

# Only install packages from backup, skip config files
migrator restore ~/backups/migrator_backup_20230101_120000.json --packages-only

# Only restore configuration files, skip package installation
migrator restore ~/backups/migrator_backup_20230101_120000.json --configs-only

# Control how package versions are handled during restoration
migrator restore backup.json --execute --version-policy=prefer-newer  # Default - use newer versions when available
migrator restore backup.json --execute --version-policy=exact  # Only install exact matching versions 
migrator restore backup.json --execute --version-policy=prefer-same  # Try exact version first, accept newer if needed
migrator restore backup.json --execute --version-policy=always-newest  # Always use the latest available versions

# Allow downgrading packages if needed (when available versions are older than backup)
migrator restore backup.json --execute --allow-downgrade

# Restore with fstab entry appending (enabled by default)
migrator restore ~/backups/migrator_backup_20230101_120000.json --execute

# Restore without appending fstab entries
migrator restore ~/backups/migrator_backup_20230101_120000.json --execute --no-fstab-restore

# Preview portable fstab entries without applying them
migrator restore ~/backups/migrator_backup_20230101_120000.json --preview-fstab

# Compare the current system with a backup
migrator compare ~/backups/migrator_backup_20230101_120000.json

# Generate an installation plan from a backup
migrator plan ~/backups/migrator_backup_20230101_120000.json

# Check for changes since the last scan
migrator check

# Run as a service to check for changes periodically
migrator service
```

### Dry Run Restore Mode

The `--dry-run` option for the restore command provides a comprehensive preview of all changes that would be made to your system without actually applying them:

```bash
migrator restore ~/backups/migrator_backup_20230101_120000.json --dry-run
```

This generates a detailed report showing:

1. **Packages**: Lists packages that would be installed and any that are unavailable
2. **Configuration Files**: Shows which config files would be restored and any potential conflicts
3. **Path Transformations**: Previews how system-specific paths would be adapted
4. **Fstab Entries**: Displays portable fstab entries that would be appended
5. **Conflicts and Issues**: Highlights potential problems before they occur

After reviewing the report, you'll be prompted to confirm if you want to proceed with the actual restore operation. This gives you a clear understanding of the impact before committing to any changes.

### Interactive Restore Mode

When restoring with the `--execute` option without specifying any category flags like `--packages-only` or `--configs-only`, Migrator enters an interactive mode:

```bash
migrator restore ~/backups/migrator_backup_20230101_120000.json --execute
```

In this mode, Migrator will:

1. Analyze the backup to identify what's available
2. Present a series of prompts about each category (packages, configuration files, repositories, fstab entries)
3. Show you how many items are in each category
4. Let you decide which parts to restore

This interactive approach gives you precise control over the restoration process without needing to remember all the command-line options. It's especially helpful when:
- You want to selectively restore only certain parts
- You're unsure what's in the backup
- You're restoring to a different system and want to be cautious

### First-Run Restore on New Systems

When restoring to a completely fresh system, Migrator provides specialized handling to help you locate your backup files:

```bash
# Automatically locate backups on connected drives
migrator locate-backup

# Include network shares in the search
migrator locate-backup --include-network

# Save the list of found backups to a file
migrator locate-backup --output backup_list.txt
```

The `locate-backup` command will:
1. Scan common locations for Migrator backup files, including:
   - Your home directory
   - External USB drives
   - Removable media
   - Network shares (if specified)
2. Display a list of found backups with their creation dates
3. Allow you to select and restore directly from the list

When you run a restore operation on a fresh system and the backup file isn't found, Migrator will automatically:
1. Detect that this is a first-run scenario
2. Offer to scan for backup files on connected drives
3. Allow you to specify a different backup file path
4. Guide you through the restore process

This eliminates friction when migrating to a new system, as Migrator will intelligently look for your backups on external media and network locations.

### Desktop Environment Configuration Backup

Migrator intelligently handles desktop environment and window manager configurations (included by default in backups):

```bash
# Desktop configurations are included by default in scan and backup operations
migrator scan
migrator backup

# Specify which desktop environments to include
migrator scan --desktop-environments=gnome,kde,i3

# Exclude specific desktop configurations
migrator scan --exclude-desktop=cinnamon

# Skip desktop environment configurations entirely
migrator backup --no-desktop
```

Desktop configuration backups include:

- **Gnome**: dconf settings, extensions, shell themes
- **KDE Plasma**: Global themes, widget layouts, panel configurations
- **XFCE/LXDE/MATE/Cinnamon**: Panel layouts, application preferences, keybindings
- **Window Managers**: i3, awesome, bspwm, dwm, xmonad configurations

Migrator automatically excludes hardware-specific settings such as:
- Display resolution and monitor configurations
- Specific device drivers and hardware acceleration settings
- Machine-specific identifiers and hardware addresses

This ensures your desktop experience remains consistent while avoiding conflicts when migrating between different hardware configurations.

### Setting Up as a System Service

Migrator provides a simple way to install itself as a systemd service that will automatically run checks on a regular schedule.

#### Automatic Installation (Recommended)

```bash
# Install as a system-wide service (requires sudo)
migrator install-service

# Or install as a user service (no sudo required)
migrator install-service --user

# Customize the check interval (e.g., every 12 hours)
migrator install-service --interval 43200

# Schedule the service to run at specific times
migrator install-service --daily "14:30"      # Run daily at 2:30 PM
migrator install-service --weekly "Mon,09:00" # Run weekly on Monday at 9:00 AM
migrator install-service --monthly "1,00:30"  # Run monthly on the 1st day at 00:30 AM

# Use advanced systemd timer syntax for custom schedules
migrator install-service --schedule "Sat,Sun *-*-* 22:00:00" # Weekends at 10 PM
```

The installer will:
1. Automatically detect your username and virtual environment
2. Create the appropriate systemd service file
3. Enable and start the service (with your permission)

Once installed as a service, Migrator will run completely automatically in the background with no need for manual intervention.

All scheduling options are available through the command line interface.

#### Managing the Service

You can use these commands to manage the service:

```bash
# Check service status
systemctl status migrator  # system service
systemctl --user status migrator  # user service

# Start the service
systemctl start migrator  # system service
systemctl --user start migrator  # user service

# Remove the service
migrator remove-service  # system service
migrator remove-service --user  # user service
```

## Data Storage

Migrator stores its data in:

- `~/.local/share/migrator/`: Application data
  - `system_state.json`: The current system state
  - `migrator.log`: Log file
- `~/.config/migrator/`: Configuration files
  - `config.json`: User preferences including backup location

Backups are stored in `~/migrator_backups/` by default, but this can be customized using the command line:

```bash
# Change the default backup location
migrator config set-backup-dir /mnt/network_share/backups

# View the current backup location
migrator config get-backup-dir
```

You can set any writable location as your backup destination, including:
- Local directories
- External drives
- Network shares
- NAS locations

## License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0) - see the LICENSE file for details. This license requires that modified versions of this software also be made available under the AGPL-3.0 license, and that you provide access to the source code when you serve users over a network.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Author

Developed by Ali Price (ali.price@pantheritservices.co.uk).
GitHub: https://github.com/PBAP123/migrator

# Package Manager Version Support
Different package managers handle versions in different ways:
- **apt**: Full version control with specific version installation
- **dnf/yum**: Version specification using package-version syntax
- **pacman**: Limited to latest available version in repositories
- **snap**: Control via revision numbers or channels
- **flatpak**: Always installs latest version available in remotes, with optimized detection for efficient planning

## Performance Optimizations

Migrator has been optimized in several key areas to ensure efficient operation, especially when handling large system migrations:

### Flatpak Package Processing
- Cached remote repository detection avoids redundant system calls
- Prioritizes Flathub as the primary package source when available
- Implements smart early-exit strategies to minimize processing time
- Application ID lookup caching for faster display name resolution
- Direct remote checking that significantly reduces planning time
- Efficient handling of large Flatpak application lists

### General Optimizations
- Intelligent caching of common system information
- Parallelized operations where appropriate
- Early termination of searches when results are found
- Memory-efficient processing of large configuration files

These optimizations ensure Migrator remains responsive even with large system profiles containing hundreds of packages and configuration files.

## Frequently Asked Questions

### General Usage Questions

**Q: What's the difference between `migrator` and `./migrator-init.sh`?**  
A: The `migrator` command is a wrapper script installed in your PATH that allows you to run Migrator from anywhere. The `./migrator-init.sh` script is the unified installer/launcher that must be run from the repository directory. Use `migrator` for day-to-day tasks and `./migrator-init.sh` for installation, updates, or troubleshooting.

**Q: Do I need to run the installer script every time I use Migrator?**  
A: No. After installation, you should use the wrapper script (`migrator`) for daily use. Only use the installer script when updating Migrator or fixing installation issues.

**Q: How do I know if Migrator is installed correctly?**  
A: Run `./migrator-init.sh` and check the status indicators at the top of the menu. If all indicators show a green checkmark (✓), Migrator is installed correctly.

### Installation and Updates

**Q: What if the wrapper scripts don't work?**  
A: This usually means either your PATH isn't set up correctly or the scripts weren't created. Run `./migrator-init.sh` and select the option to fix your PATH or update Migrator.

**Q: How do I completely reinstall Migrator?**  
A: Run `./migrator-init.sh`, then select option 4 for a "Clean installation." This will remove the virtual environment and reinstall everything from scratch.

**Q: What happens when I update Migrator?**  
A: When you run `./migrator-init.sh update`, the script:
1. Upgrades all dependencies
2. Reinstalls Migrator with the latest code
3. Recreates the wrapper scripts
4. Fixes common issues automatically

**Q: Can I have multiple installations of Migrator?**  
A: Yes, but they'll share the same wrapper scripts. If you need multiple installations, consider using different virtual environment paths and running directly from the source directories.

## Interactive Setup Wizard

Migrator includes an interactive CLI setup wizard to help you quickly configure the essential settings. The wizard will guide you through:

1. **Backup Content Configuration**: Choose what types of data to include in backups (desktop environments, fstab entries)
2. **Backup Destination**: Select where your backups should be stored
3. **Backup Retention Rules**: Configure automated cleanup of old backups to manage storage space
4. **Backup Scheduling**: Optionally set up automated backups on a schedule

To run the setup wizard:

```bash
migrator setup
```

The wizard will be automatically triggered on the first run of Migrator, but you can run it any time to reconfigure your settings.

Setup options are saved to Migrator's configuration file (`~/.config/migrator/config.json`), and if you enable scheduled backups, a systemd service will be created for you automatically.

### Backup Retention Rules

Migrator's backup retention feature automatically cleans up old backups based on user-defined rules to manage storage space efficiently:

```bash
# Get current retention settings
migrator config backup-retention get

# Enable automatic cleanup of old backups
migrator config backup-retention enable

# Disable automatic cleanup (keep all backups)
migrator config backup-retention disable

# Count-based retention: Keep only the N most recent backups
migrator config backup-retention set-count 5  # Keep the last 5 backups

# Age-based retention: Delete backups older than X days
migrator config backup-retention set-age 30  # Keep backups newer than 30 days
```

When retention is enabled, Migrator automatically applies the cleanup rules after each new backup is created, ensuring your backup storage is kept manageable without requiring manual intervention.

During the setup wizard, you'll be guided through configuring these retention settings in a user-friendly way.

### Multi-System Backup Organization

When managing backups across multiple systems:

```bash
# List all hosts that have backups
migrator config list-hosts

# Show backups for a specific host
migrator config get-host-backups hostname
migrator config get-host-backups hostname --show-detail

# List all backups with host organization
migrator list-backups --by-host

# Show backups for a specific host only
migrator list-backups --host hostname

# Detailed backup listing
migrator list-backups --show-detail
```

The multi-system backup structure organizes your backups into subdirectories based on hostname:

```
backup_directory/
├── hostname1/
│   ├── migrator_backup_20230101_120000_hostname1.json
│   └── config_files/
│       └── ... 
├── hostname2/
│   ├── migrator_backup_20230201_143000_hostname2.json
│   └── config_files/
│       └── ...
└── ... (other hosts)
```

This organization prevents file conflicts and makes it easy to find backups for a specific system.

## Restore Options

When restoring from a backup, Migrator provides several options to control the restoration process:

```
  --execute, -e         Automatically install packages and restore config files
  --packages-only       Only install packages, skip config files
  --configs-only        Only restore config files, skip packages
  --dry-run             Perform a dry run showing all changes that would be made without actually applying them
```

### Version Handling Options

```
  --version-policy {exact,prefer-same,prefer-newer,always-newest}
                        Package version policy: exact=only install exact versions, 
                        prefer-same=try exact version first but allow newer if needed, 
                        prefer-newer=prefer newer versions but allow downgrade if needed, 
                        always-newest=always use newest available version
  --allow-downgrade     Allow downgrading packages if newer versions are installed
```

### Path Handling Options

```
  --no-path-transform   Disable automatic transformation of paths in config files
  --path-transform-preview
                        Show what paths would be transformed without making changes
```

### Fstab Options

```
  --no-fstab-restore    Skip restoration of portable fstab entries
  --preview-fstab       Preview portable fstab entries without applying changes
```

### Repository Options

```
  --no-repo-restore     Skip restoration of software repositories
  --preview-repos       Preview repository restoration without applying changes
  --force-incompatible-repos
                        Attempt to restore incompatible repositories (may cause system issues)
```

### Dry Run Mode

The `--dry-run` option for the restore command provides a comprehensive preview of all changes that would be made to your system without actually applying them:

```bash
migrator restore ~/backups/migrator_backup_20230101_120000.json --dry-run
```

This generates a detailed report showing:

1. **Packages**: Lists packages that would be installed and any that are unavailable
2. **Configuration Files**: Shows which config files would be restored and any potential conflicts
3. **Path Transformations**: Previews how system-specific paths would be adapted
4. **Fstab Entries**: Displays portable fstab entries that would be appended
5. **Conflicts and Issues**: Highlights potential problems before they occur

After reviewing the report, you'll be prompted to confirm if you want to proceed with the actual restore operation. This gives you a clear understanding of the impact before committing to any changes.

# Enhanced Configuration Management

Migrator provides powerful ways to customize which configuration files are included in your backups:

## Advanced Configuration Scanning

Migrator automatically scans and backs up configuration from:

- System-wide locations (`/etc`, `/usr/local/etc`)  
- User-specific settings (`~/.config`, dotfiles in home directory)
- Important directories in `~/.local/share` (applications, fonts, themes, etc.)
- Desktop environment and window manager settings
- Application-specific directories (`~/.mozilla`, `~/.thunderbird`, `~/.gnupg`, etc.)
- User script directories (`~/bin`, `~/.local/bin`)

## Customizing Config Backup Scope

```bash
# Include specific additional paths
migrator backup --include-paths=~/custom/configs,~/projects/settings

# Exclude specific paths from backup
migrator backup --exclude-paths=~/.config/large-app,~/.local/share/big-data

# Create a minimal backup (essential preferences only)
migrator backup --minimal
```

The `--minimal` option creates a focused backup containing only essential user preferences while excluding application data directories. This results in smaller, more portable backups.

## Smart Warnings for Non-Portable Configs

Migrator provides warnings when backing up configuration files that might have portability issues:

- Keyring files that are encrypted with your login password
- Browser profiles that may contain large caches
- Hardware-specific configurations
- Security-sensitive files that might need special handling

```
PORTABILITY WARNINGS:
----------------------
The following paths in your backup may have portability issues:

- ~/.local/share/keyrings:
  WARNING: Keyring files are encrypted with your login password and may not be usable
  on a different system if your password changes...

Do you want to continue with the backup?
Continue? (y/n) [y]:
```

## Granular Control over ~/.local/share

Migrator provides intelligent filtering of the `~/.local/share` directory:

- Automatically includes high-value, typically small configuration directories
  - `~/.local/share/applications` - Desktop entries
  - `~/.local/share/fonts` - User fonts
  - `~/.local/share/icons` - Icon themes
  - `~/.local/share/themes` - GTK themes
  - `~/.local/share/mime` - MIME type definitions
  - Various DE-specific settings directories

- Automatically excludes large data directories
  - `~/.local/share/Steam` - Game installations
  - `~/.local/share/Trash` - Deleted files
  - `~/.local/share/flatpak` - Flatpak runtime data
  - Cache directories and other large data
