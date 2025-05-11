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

2. **Manual virtual environment activation**:

   ```bash
   source ~/.venvs/migrator/bin/activate
   migrator scan
   ```

### Alternative: Run Without Installing

If you prefer not to install, you can run Migrator directly:

```bash
cd migrator
python3 -m src.__main__ scan
```

## Usage

### Command-Line Interface

Once installed:

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

#### Manual Removal

To remove the service:

```bash
# Remove a system-wide service
migrator remove-service

# Remove a user service
migrator remove-service --user
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

Migrator stores its data in `~/.local/share/migrator/`:

- `system_state.json`: The current system state
- `migrator.log`: Log file

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
