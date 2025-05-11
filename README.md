# Linux Packages

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

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/n3o/linuxpackages.git
cd linuxpackages

# Install dependencies
pip install -r requirements.txt

# Install the package
pip install -e .
```

## Usage

### Command-Line Interface

```bash
# Scan the system and update the system state
linuxpackages scan

# Backup the current system state to a directory
linuxpackages backup ~/backups

# Restore the system state from a backup file
linuxpackages restore ~/backups/linuxpackages_backup_20230101_120000.json

# Compare the current system with a backup
linuxpackages compare ~/backups/linuxpackages_backup_20230101_120000.json

# Generate an installation plan from a backup
linuxpackages plan ~/backups/linuxpackages_backup_20230101_120000.json

# Check for changes since the last scan
linuxpackages check

# Run as a service to check for changes periodically
linuxpackages service
```

### As a Service

You can set up Linux Packages to run as a service to periodically check for changes:

```bash
# Run the service with a custom interval (in seconds)
linuxpackages service --interval 3600  # Check every hour
```

For a more permanent solution, create a systemd service or cronjob:

#### Using systemd

Create a file at `/etc/systemd/system/linuxpackages.service`:

```ini
[Unit]
Description=Linux Packages Migration Utility
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/linuxpackages service
Restart=on-failure
User=your_username

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable linuxpackages.service
sudo systemctl start linuxpackages.service
```

#### Using cron

Set up a daily cron job:

```bash
# Add to crontab
crontab -e

# Add the following line to run every day at 3 AM
0 3 * * * /usr/local/bin/linuxpackages check
```

## Data Storage

Linux Packages stores its data in `~/.local/share/linuxpackages/`:

- `system_state.json`: The current system state
- `linuxpackages.log`: Log file

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
