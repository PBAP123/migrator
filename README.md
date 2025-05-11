# Migrator

A system migration utility for Linux that tracks installed packages and configuration files, making it easy to migrate to a new system.

## Features

- **Multi-Distribution Support**: Works on any Linux distribution by automatically detecting package managers.
- **Package Tracking**: Tracks packages from various sources:
  - Distribution-specific packages (apt, yum, pacman, etc.)
  - Snap packages
  - Flatpak packages
  - AppImages
- **Configuration Tracking**: Identifies and tracks both system and user configuration files.
- **Incremental Backup**: Monitors changes to packages and configurations over time.
- **Migration Planning**: Generates a plan for installing packages on a new system.
- **Configuration Restoration**: Helps restore configuration files to their original locations.

## Requirements

- **Python**: Version 3.6 or higher
- **Linux OS**: Any distribution with standard package managers
- **Dependencies**: 
  - `distro` Python package (v1.5.0 or higher)
  - Access to package manager executables for detection (apt, snap, flatpak, etc.)

## Installation

### Recommended: Using a Virtual Environment

Modern Linux distributions (especially Debian/Ubuntu-based ones) enforce PEP 668, which prevents direct pip installations outside of virtual environments. Using a virtual environment is the recommended approach:

```bash
# Clone the repository
git clone https://github.com/PBAP123/migrator.git
cd migrator

# Make sure you have Python 3.6+ installed
python3 --version

# Install virtualenv if you don't have it
# For Debian/Ubuntu:
sudo apt install python3-venv

# Create a virtual environment
python3 -m venv ~/.venvs/migrator

# Activate the virtual environment
source ~/.venvs/migrator/bin/activate

# Install dependencies and the package
pip install -r requirements.txt
pip install -e .

# Now you can run migrator commands
migrator scan
```

Remember to activate the virtual environment whenever you want to use Migrator:

```bash
source ~/.venvs/migrator/bin/activate
```

### Alternative: Run Without Installing

If you prefer not to install, you can run Migrator directly:

```bash
cd migrator
python3 -m src.__main__ scan
```

## Usage

### Command-Line Interface

Once installed and your virtual environment is activated:

```bash
# Scan the system and update the system state
migrator scan

# Backup the current system state to a directory
migrator backup ~/backups

# Restore the system state from a backup file
migrator restore ~/backups/migrator_backup_20230101_120000.json

# Compare the current system with a backup
migrator compare ~/backups/migrator_backup_20230101_120000.json

# Generate an installation plan from a backup
migrator plan ~/backups/migrator_backup_20230101_120000.json

# Check for changes since the last scan
migrator check

# Run as a service to check for changes periodically
migrator service
```

### As a Service

You can set up Migrator to run as a service to periodically check for changes.

#### Using systemd with Virtual Environment

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

#### Using cron with Virtual Environment

Set up a daily cron job:

```bash
# Add to crontab
crontab -e

# Add the following line to run every day at 3 AM
0 3 * * * source /home/yourusername/.venvs/migrator/bin/activate && migrator check
```

## Data Storage

Migrator stores its data in `~/.local/share/migrator/`:

- `system_state.json`: The current system state
- `migrator.log`: Log file

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
