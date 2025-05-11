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

### From Source

```bash
# Clone the repository
git clone https://github.com/PBAP123/migrator.git
cd migrator

# Make sure you have Python 3.6+ installed
python3 --version

# Install dependencies
pip3 install -r requirements.txt

# Install the package
pip3 install -e .
```

## Usage

### Command-Line Interface

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

You can set up Migrator to run as a service to periodically check for changes:

```bash
# Run the service with a custom interval (in seconds)
migrator service --interval 3600  # Check every hour
```

For a more permanent solution, create a systemd service or cronjob:

#### Using systemd

Create a file at `/etc/systemd/system/migrator.service`:

```ini
[Unit]
Description=Migrator System Migration Utility
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/migrator service
Restart=on-failure
User=your_username

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable migrator.service
sudo systemctl start migrator.service
```

#### Using cron

Set up a daily cron job:

```bash
# Add to crontab
crontab -e

# Add the following line to run every day at 3 AM
0 3 * * * /usr/local/bin/migrator check
```

## Data Storage

Migrator stores its data in `~/.local/share/migrator/`:

- `system_state.json`: The current system state
- `migrator.log`: Log file

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
