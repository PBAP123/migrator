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
- **User-friendly** - Intuitive terminal UI makes migration simple
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
  - TUI interface for easy management
- **Migration Planning**: Generates a plan for installing packages on a new system.
- **Configuration Restoration**: Helps restore configuration files to their original locations.
- **Terminal User Interface (TUI)**: Comprehensive terminal-based interface for easier management.
- **Service Management**: Run as a background service with automatic checks.

## Requirements

- **Python**: Version 3.6 or higher
- **Linux OS**: Any distribution with standard package managers
- **Required Packages** (for Debian/Ubuntu):
  - `python3-venv`: Required for creating virtual environments
  - `python3-pip`: Required for installing Python packages
  - `python3-distro` or the `distro` Python package (v1.5.0 or higher)
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

### Terminal User Interface (TUI)

Migrator now includes a comprehensive TUI for easier management:

```bash
# Launch the TUI
python3 migrator-tui.py
```

The TUI provides access to all Migrator functionality through an intuitive interface:

- **Dashboard**: View system status and quick actions
- **Install/Setup**: Interactive setup wizard with distribution detection
- **Scan System**: Scan for packages and configuration files
- **Backups**: Create and manage backups
- **Compare/Restore**: Compare changes and restore from backups
- **Service Management**: Install and manage Migrator as a service

#### TUI Dependencies

To use the Terminal User Interface, you'll need additional dependencies:

```bash
# Install from requirements
pip install py_cui

# Or directly in your system (not recommended)
sudo apt install python3-py-cui  # Debian/Ubuntu
```

#### Running the TUI Without Installation

The TUI can run Migrator without a full installation. Simply clone the repository and run:

```bash
# Install the TUI dependency
pip install py_cui

# Run directly from the source directory
cd migrator
python3 migrator-tui.py
```

The TUI will automatically detect if Migrator is installed or not and run it accordingly.

### Command-Line Interface

Once installed:

```bash
# Scan the system and update the system state
migrator scan

# Backup the current system state to a directory
migrator backup ~/backups

# View or modify the default backup location
migrator config get-backup-dir  # Show current backup directory
migrator config set-backup-dir /path/to/backup  # Set a new default backup location

# Create a backup using the default location (no path needed)
migrator backup

# Restore the system state from a backup file
migrator restore ~/backups/migrator_backup_20230101_120000.json

# Restore and automatically install all packages and configuration files
migrator restore ~/backups/migrator_backup_20230101_120000.json --execute

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

# Compare the current system with a backup
migrator compare ~/backups/migrator_backup_20230101_120000.json

# Generate an installation plan from a backup
migrator plan ~/backups/migrator_backup_20230101_120000.json

# Check for changes since the last scan
migrator check

# Run as a service to check for changes periodically
migrator service
```

### Desktop Environment Configuration Backup

Migrator intelligently handles desktop environment and window manager configurations:

```bash
# Backup desktop configurations with system scan
migrator scan --include-desktop

# Specify which desktop environments to include
migrator scan --desktop-environments=gnome,kde,i3

# Exclude specific desktop configurations
migrator scan --exclude-desktop=cinnamon
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
```

The installer will:
1. Automatically detect your username and virtual environment
2. Create the appropriate systemd service file
3. Enable and start the service (with your permission)

Once installed as a service, Migrator will run completely automatically in the background with no need for manual intervention.

#### Managing the Service

The TUI provides a service management interface, or you can use these commands:

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

#### Legacy: Manual Service Setup

If you prefer to set up the service manually, you can create a systemd service file:

##### Using systemd with Virtual Environment

Create a file at `/etc/systemd/system/migrator.service`:

```ini
[Unit]
Description=Migrator System Migration Utility
After=network.target

[Service]
Type=simple
Environment="PATH=/home/yourusername/.venvs/migrator/bin:$PATH"
ExecStart=/home/yourusername/.venvs/migrator/bin/migrator service
Restart=on-failure
User=yourusername

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable migrator.service
sudo systemctl start migrator.service
```

##### Using cron with Virtual Environment

Set up a daily cron job:

```bash
# Add to crontab
crontab -e

# Add the following line to run every day at 3 AM
0 3 * * * source /home/yourusername/.venvs/migrator/bin/activate && migrator check
```

## Data Storage

Migrator stores its data in:

- `~/.local/share/migrator/`: Application data
  - `system_state.json`: The current system state
  - `migrator.log`: Log file
- `~/.config/migrator/`: Configuration files
  - `config.json`: User preferences including backup location

Backups are stored in `~/migrator_backups/` by default, but this can be customized using the command line or TUI:

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
- **flatpak**: Always installs latest version available
