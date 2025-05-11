#!/usr/bin/env python3
"""
Migrator TUI - Terminal User Interface for Migrator

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import os
import sys
import shutil
import platform
import subprocess
import threading
import time
from pathlib import Path
from datetime import datetime

# Add to requirements.txt
try:
    import py_cui
    import distro
except ImportError:
    print("Required dependencies not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "py_cui", "distro"])
    import py_cui
    import distro

# Import the config module
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
try:
    from utils.config import config
except ImportError:
    print("Could not import config module, falling back to defaults")
    config = None

# Migrator paths and constants
VENV_PATH = os.path.expanduser("~/.venvs/migrator")
WRAPPER_PATH = os.path.expanduser("~/.local/bin/migrator")
DATA_DIR = os.path.expanduser("~/.local/share/migrator")
STATE_FILE = os.path.join(DATA_DIR, "system_state.json")
LOG_FILE = os.path.join(DATA_DIR, "migrator.log")

# Distribution-specific commands
INSTALL_COMMANDS = {
    # Debian/Ubuntu and derivatives
    'debian': {
        'deps': "sudo apt install python3-venv python3-pip python3-distro",
        'venv': "python3 -m venv ~/.venvs/migrator",
        'activate': "source ~/.venvs/migrator/bin/activate",
    },
    'ubuntu': {
        'deps': "sudo apt install python3-venv python3-pip python3-distro",
        'venv': "python3 -m venv ~/.venvs/migrator",
        'activate': "source ~/.venvs/migrator/bin/activate",
    },
    # RedHat/Fedora and derivatives
    'fedora': {
        'deps': "sudo dnf install python3-virtualenv python3-pip python3-distro",
        'venv': "python3 -m venv ~/.venvs/migrator",
        'activate': "source ~/.venvs/migrator/bin/activate",
    },
    'rhel': {
        'deps': "sudo dnf install python3-virtualenv python3-pip python3-distro",
        'venv': "python3 -m venv ~/.venvs/migrator",
        'activate': "source ~/.venvs/migrator/bin/activate",
    },
    'centos': {
        'deps': "sudo dnf install python3-virtualenv python3-pip python3-distro",
        'venv': "python3 -m venv ~/.venvs/migrator",
        'activate': "source ~/.venvs/migrator/bin/activate",
    },
    # Arch and derivatives
    'arch': {
        'deps': "sudo pacman -S python-virtualenv python-pip python-distro",
        'venv': "python3 -m venv ~/.venvs/migrator",
        'activate': "source ~/.venvs/migrator/bin/activate",
    },
    'manjaro': {
        'deps': "sudo pacman -S python-virtualenv python-pip python-distro",
        'venv': "python3 -m venv ~/.venvs/migrator",
        'activate': "source ~/.venvs/migrator/bin/activate",
    },
    # OpenSUSE
    'opensuse': {
        'deps': "sudo zypper install python3-virtualenv python3-pip python3-distro",
        'venv': "python3 -m venv ~/.venvs/migrator",
        'activate': "source ~/.venvs/migrator/bin/activate",
    },
    # Default fallback
    'default': {
        'deps': "Install python3-venv, python3-pip, and python3-distro packages using your distribution's package manager",
        'venv': "python3 -m venv ~/.venvs/migrator",
        'activate': "source ~/.venvs/migrator/bin/activate",
    }
}

class MigratorTui:
    """Main TUI class for Migrator"""
    
    def __init__(self, root):
        """Initialize the TUI"""
        self.root = root
        self.root.set_title("Migrator TUI")
        self.root.set_status_bar_text("Migrator - Linux System Migration Utility")
        
        # Detect the system
        self.detect_system()
        
        # Setup UI
        self.setup_ui()
        
        # Background task status
        self.running_task = None
        self.task_result = None
        
        # Initialize
        self.refresh_system_info()
        
    def detect_system(self):
        """Detect system information"""
        self.distro_id = distro.id()
        self.distro_name = distro.name(pretty=True)
        self.distro_version = distro.version(pretty=True)
        
        # Get appropriate commands for this distro
        if self.distro_id in INSTALL_COMMANDS:
            self.install_commands = INSTALL_COMMANDS[self.distro_id]
        else:
            # Try to find a match by ID_LIKE
            id_like = distro.like().lower().split()
            for distro_id in INSTALL_COMMANDS:
                if distro_id in id_like:
                    self.install_commands = INSTALL_COMMANDS[distro_id]
                    break
            else:
                self.install_commands = INSTALL_COMMANDS['default']
        
        # Check Migrator installation status
        self.is_migrator_installed = os.path.exists(WRAPPER_PATH)
        self.is_venv_created = os.path.exists(VENV_PATH)
        self.is_service_installed = self.check_service_installed()
        
    def check_service_installed(self):
        """Check if Migrator is installed as a service"""
        # Check system-wide service
        if os.path.exists("/etc/systemd/system/migrator.service"):
            return "system"
        # Check user service
        if os.path.exists(os.path.expanduser("~/.config/systemd/user/migrator.service")):
            return "user"
        return None
        
    def setup_ui(self):
        """Setup the UI layout and widgets"""
        # Create the main menu
        self.main_menu = self.root.add_scroll_menu("Main Menu", 0, 0, row_span=7, column_span=1)
        self.main_menu.add_item_list([
            "📊 Dashboard",
            "🛠️ Install/Setup",
            "🔍 Scan System",
            "💾 Backups",
            "🔄 Compare/Restore",
            "⚙️ Service Management",
            "❓ Help/About",
            "❌ Exit"
        ])
        self.main_menu.add_key_command(py_cui.keys.KEY_ENTER, self.handle_menu_selection)
        
        # Right panel for content
        self.content_panel = self.root.add_scroll_panel("Welcome to Migrator TUI", 0, 1, row_span=6, column_span=3)
        
        # Output panel for command output
        self.output_panel = self.root.add_text_block("Command Output", 6, 1, row_span=3, column_span=3)
        self.output_panel.set_text("Command output will appear here")
        
        # Default status
        self.refresh_dashboard()
        
    def handle_menu_selection(self):
        """Handle main menu selection"""
        selection = self.main_menu.get()
        
        if "Dashboard" in selection:
            self.refresh_dashboard()
        elif "Install/Setup" in selection:
            self.show_install_screen()
        elif "Scan System" in selection:
            self.show_scan_screen()
        elif "Backups" in selection:
            self.show_backup_screen()
        elif "Compare/Restore" in selection:
            self.show_compare_screen()
        elif "Service Management" in selection:
            self.show_service_screen()
        elif "Help/About" in selection:
            self.show_help_screen()
        elif "Exit" in selection:
            self.root.stop()
    
    def refresh_system_info(self):
        """Refresh system information"""
        self.detect_system()
        
        # Get Migrator info
        self.state_file_exists = os.path.exists(STATE_FILE)
        self.log_file_exists = os.path.exists(LOG_FILE)
        
        # Get backup dir from config
        self.backup_dir = self.get_backup_dir()
        
        # Get backup info
        if not os.path.exists(self.backup_dir):
            self.backup_count = 0
            self.latest_backup = None
        else:
            backups = [f for f in os.listdir(self.backup_dir) if f.startswith('migrator_backup_') and f.endswith('.json')]
            self.backup_count = len(backups)
            if backups:
                # Sort by timestamp in filename
                backups.sort(reverse=True)
                self.latest_backup = backups[0]
            else:
                self.latest_backup = None

    def refresh_dashboard(self):
        """Show dashboard with system status"""
        self.refresh_system_info()
        
        dashboard = f"""
╭────────────────── MIGRATOR DASHBOARD ──────────────────╮
│                                                        │
│  System Information:                                   │
│  • Distribution: {self.distro_name} {self.distro_version}                 │
│                                                        │
│  Migrator Status:                                      │
│  • Installation: {"Installed" if self.is_migrator_installed else "Not installed"}                             │
│  • Virtual Environment: {"Created" if self.is_venv_created else "Not created"}                       │
│  • Service: {"System-wide" if self.is_service_installed == "system" else "User service" if self.is_service_installed == "user" else "Not installed"}                                │
│                                                        │
│  Data:                                                 │
│  • State file: {"Exists" if self.state_file_exists else "Not created yet"}                               │
│  • Backups: {self.backup_count} {"(Latest: " + self.latest_backup + ")" if self.latest_backup else ""}                                    │
│                                                        │
│  Quick Actions:                                         │
│  1. [1] Run first-time setup                            │
│  2. [2] Scan system for packages and configs            │
│  3. [3] Create backup                                   │
│  4. [4] Install as a service                            │
│                                                        │
╰────────────────────────────────────────────────────────╯

Press the corresponding number key for quick actions, or
use the main menu on the left to navigate.
"""
        self.content_panel.set_title("Dashboard")
        self.content_panel.set_text(dashboard)
        
        # Set up key bindings for quick actions
        self.root.add_key_command(ord('1'), self.show_install_screen)
        self.root.add_key_command(ord('2'), lambda: self.run_migrator_command("scan"))
        self.root.add_key_command(ord('3'), self.prompt_backup)
        self.root.add_key_command(ord('4'), self.show_service_screen)
    
    def show_install_screen(self):
        """Show installation screen"""
        install_text = f"""
╭────────────── MIGRATOR INSTALLATION ──────────────╮
│                                                   │
│  System Information:                              │
│  • Distribution: {self.distro_name}                │
│                                                   │
│  Installation Status:                             │
│  • Virtual Environment: {"✅" if self.is_venv_created else "❌"}                      │
│  • Migrator: {"✅" if self.is_migrator_installed else "❌"}                             │
│                                                   │
│  Available Installation Options:                   │
│  1. [1] Install dependencies                       │
│     {self.install_commands['deps']}                │
│                                                   │
│  2. [2] Create virtual environment                 │
│     {self.install_commands['venv']}                │
│                                                   │
│  3. [3] Install Migrator                           │
│     (Will guide you through the process)          │
│                                                   │
│  4. [4] Full automatic installation               │
│     (All steps at once - recommended)             │
│                                                   │
╰───────────────────────────────────────────────────╯

Press the corresponding number key to start the installation step.
"""
        self.content_panel.set_title("Installation")
        self.content_panel.set_text(install_text)
        
        # Set up key bindings for installation actions
        self.root.add_key_command(ord('1'), lambda: self.run_command(self.install_commands['deps']))
        self.root.add_key_command(ord('2'), lambda: self.run_command(self.install_commands['venv']))
        self.root.add_key_command(ord('3'), self.install_migrator)
        self.root.add_key_command(ord('4'), self.full_install)
    
    def show_scan_screen(self):
        """Show scan options"""
        scan_text = """
╭────────────── MIGRATOR SCAN OPTIONS ───────────────╮
│                                                    │
│  Available Scan Options:                           │
│                                                    │
│  1. [1] Scan system                                │
│     Performs a full scan of all packages and       │
│     configuration files                            │
│                                                    │
│  2. [2] Check for changes                          │
│     Checks for changes since the last scan         │
│                                                    │
│  3. [3] View scan results                          │
│     Shows summary of the latest scan               │
│                                                    │
│  4. [4] View detailed scan logs                    │
│     Opens the migrator log file                    │
│                                                    │
╰────────────────────────────────────────────────────╯

Press the corresponding number key to select an option.
"""
        self.content_panel.set_title("Scan Options")
        self.content_panel.set_text(scan_text)
        
        # Set up key bindings
        self.root.add_key_command(ord('1'), lambda: self.run_migrator_command("scan"))
        self.root.add_key_command(ord('2'), lambda: self.run_migrator_command("check"))
        self.root.add_key_command(ord('3'), self.view_state_file)
        self.root.add_key_command(ord('4'), self.view_log_file)
    
    def show_backup_screen(self):
        """Show backup options"""
        # Ensure backup directory exists
        backup_dir = self.get_backup_dir()
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir, exist_ok=True)
            
        # Get backup list
        backups = []
        if os.path.exists(backup_dir):
            backups = [f for f in os.listdir(backup_dir) if f.startswith('migrator_backup_') and f.endswith('.json')]
            backups.sort(reverse=True)  # Most recent first
        
        backup_list = "\n".join(backups) if backups else "No backups found"
        
        backup_text = f"""
╭────────────── MIGRATOR BACKUP OPTIONS ───────────────╮
│                                                      │
│  Backup Status:                                      │
│  • Total backups: {len(backups)}                                    │
│  • Backup location: {backup_dir}              │
│                                                      │
│  Available Backup Options:                           │
│                                                      │
│  1. [1] Create a new backup                          │
│     Backup current system state                      │
│                                                      │
│  2. [2] View backups                                 │
│     List and manage existing backups                 │
│                                                      │
│  3. [3] Delete all backups                           │
│     Clear the backup directory                       │
│                                                      │
│  4. [4] Change backup location                       │
│     Set a different backup directory                 │
│                                                      │
│  Recent Backups:                                     │
│  {backup_list[:200] + '...' if len(backup_list) > 200 else backup_list}    │
│                                                      │
╰──────────────────────────────────────────────────────╯

Press the corresponding number key to select an option.
"""
        self.content_panel.set_title("Backup Options")
        self.content_panel.set_text(backup_text)
        
        # Set up key bindings
        self.root.add_key_command(ord('1'), self.prompt_backup)
        self.root.add_key_command(ord('2'), self.show_backup_list)
        self.root.add_key_command(ord('3'), self.confirm_delete_backups)
        self.root.add_key_command(ord('4'), self.prompt_change_backup_dir)
    
    def show_compare_screen(self):
        """Show compare and restore options"""
        # Get backup list
        backup_dir = self.get_backup_dir()
        backups = []
        if os.path.exists(backup_dir):
            backups = [f for f in os.listdir(backup_dir) if f.startswith('migrator_backup_') and f.endswith('.json')]
            backups.sort(reverse=True)  # Most recent first
        
        if not backups:
            compare_text = """
╭────────────── MIGRATOR COMPARE OPTIONS ───────────────╮
│                                                       │
│  No backups found!                                    │
│                                                       │
│  You need to create a backup before you can compare   │
│  or restore.                                          │
│                                                       │
│  1. [1] Create a backup now                           │
│                                                       │
╰───────────────────────────────────────────────────────╯
"""
            self.root.add_key_command(ord('1'), self.prompt_backup)
        else:
            compare_text = f"""
╭────────────── MIGRATOR COMPARE OPTIONS ───────────────╮
│                                                       │
│  Available backups: {len(backups)}                                  │
│                                                       │
│  1. [1] Compare current system with a backup          │
│     Shows added/removed packages and config files     │
│                                                       │
│  2. [2] Generate installation plan                    │
│     Create plan for reinstalling packages             │
│                                                       │
│  3. [3] Restore from backup                           │
│     Load a backup state file                          │
│                                                       │
│  Latest backup: {backups[0] if backups else "None"}            │
│                                                       │
╰───────────────────────────────────────────────────────╯

Press the corresponding number key to select an option.
"""
            # Set up key bindings
            self.root.add_key_command(ord('1'), lambda: self.select_backup_for("compare"))
            self.root.add_key_command(ord('2'), lambda: self.select_backup_for("plan"))
            self.root.add_key_command(ord('3'), lambda: self.select_backup_for("restore"))
        
        self.content_panel.set_title("Compare & Restore Options")
        self.content_panel.set_text(compare_text)
    
    def show_service_screen(self):
        """Show service management options"""
        service_status = "System-wide" if self.is_service_installed == "system" else \
                         "User service" if self.is_service_installed == "user" else \
                         "Not installed"
        
        service_text = f"""
╭────────────── MIGRATOR SERVICE OPTIONS ───────────────╮
│                                                       │
│  Service Status: {service_status}                          │
│                                                       │
│  Available Service Options:                           │
│                                                       │
│  1. [1] Install as system service                     │
│     Requires sudo, runs for all users                 │
│                                                       │
│  2. [2] Install as user service                       │
│     No sudo needed, runs for current user only        │
│                                                       │
│  3. [3] Install with advanced scheduling              │
│     Set specific times for service to run             │
│                                                       │
│  4. [4] Remove existing service                       │
│     Uninstall the current service                     │
│                                                       │
│  5. [5] View service status                           │
│     Check if the service is running                   │
│                                                       │
│  6. [6] Start/restart service                         │
│     Start or restart the service                      │
│                                                       │
╰───────────────────────────────────────────────────────╯

Press the corresponding number key to select an option.
"""
        self.content_panel.set_title("Service Management")
        self.content_panel.set_text(service_text)
        
        # Set up key bindings
        self.root.add_key_command(ord('1'), lambda: self.install_service(user=False))
        self.root.add_key_command(ord('2'), lambda: self.install_service(user=True))
        self.root.add_key_command(ord('3'), self.show_service_scheduling)
        self.root.add_key_command(ord('4'), self.remove_service)
        self.root.add_key_command(ord('5'), self.check_service_status)
        self.root.add_key_command(ord('6'), self.restart_service)
    
    def show_help_screen(self):
        """Show help and about information"""
        help_text = """
╭────────────── MIGRATOR HELP & ABOUT ───────────────────╮
│                                                        │
│  Migrator - Linux System Migration Utility             │
│                                                        │
│  Author: Ali Price                                     │
│  Email: ali.price@pantheritservices.co.uk              │
│  URL: https://github.com/PBAP123/migrator               │
│                                                        │
│  Description:                                          │
│  Migrator is a system migration utility for Linux that │
│  tracks installed packages and configuration files,    │
│  making it easy to migrate to a new system.            │
│                                                        │
│  Key Features:                                         │
│  • Works on any Linux distribution                     │
│  • Tracks packages from various sources (apt, snap,    │
│    flatpak, AppImage, etc.)                           │
│  • Identifies and tracks configuration files           │
│  • Generates installation plans for new systems        │
│  • Can run as a background service                     │
│                                                        │
│  Quick Help:                                           │
│  • Use the menu on the left to navigate               │
│  • Follow the numbered options to perform actions      │
│  • Check the Dashboard for system status               │
│                                                        │
╰────────────────────────────────────────────────────────╯
"""
        self.content_panel.set_title("Help & About")
        self.content_panel.set_text(help_text)
    
    def prompt_backup(self):
        """Prompt for backup location"""
        self.root.show_text_box_popup(
            "Backup Directory",
            f"Enter backup directory (default: {self.get_backup_dir()}):",
            self.create_backup
        )
    
    def create_backup(self, backup_dir):
        """Create a backup"""
        if not backup_dir.strip():
            backup_dir = self.get_backup_dir()
        
        os.makedirs(backup_dir, exist_ok=True)
        self.run_migrator_command(f"backup {backup_dir}")
    
    def prompt_change_backup_dir(self):
        """Prompt for changing the default backup directory"""
        self.root.show_text_box_popup(
            "Change Backup Directory",
            f"Enter new default backup directory (current: {self.get_backup_dir()}):",
            self.change_backup_dir
        )
    
    def change_backup_dir(self, new_backup_dir):
        """Change the default backup directory"""
        if not new_backup_dir.strip():
            self.output_panel.set_text("No directory specified. Keeping current backup directory.")
            return
            
        new_backup_dir = os.path.expanduser(new_backup_dir)
        self.run_migrator_command(f"config set-backup-dir {new_backup_dir}")
        
        # Refresh to show the new backup directory
        self.refresh_system_info()
        self.show_backup_screen()
    
    def get_backup_dir(self) -> str:
        """Get the configured backup directory"""
        # Try to use config module if available
        if config:
            return config.get_backup_dir()
        else:
            # Fallback to hardcoded default
            return os.path.expanduser("~/migrator_backups")
    
    def select_backup_for(self, action):
        """Show backup selection popup for an action"""
        # Get backup list
        backup_dir = self.get_backup_dir()
        backups = []
        if os.path.exists(backup_dir):
            backups = [f for f in os.listdir(backup_dir) if f.startswith('migrator_backup_') and f.endswith('.json')]
            backups.sort(reverse=True)  # Most recent first
        
        if not backups:
            self.output_panel.set_text("No backups found. Please create a backup first.")
            return
        
        # Create a popup menu
        popup = self.root.create_popup('Select Backup', 5, 70)
        menu = popup.add_scroll_menu('Available Backups', 0, 0, row_span=5, column_span=1)
        menu.add_item_list(backups)
        
        # Set action handler
        if action == "compare":
            menu.add_key_command(py_cui.keys.KEY_ENTER, 
                                lambda: self.run_compare(os.path.join(backup_dir, menu.get())))
        elif action == "plan":
            menu.add_key_command(py_cui.keys.KEY_ENTER, 
                                lambda: self.run_plan(os.path.join(backup_dir, menu.get())))
        elif action == "restore":
            menu.add_key_command(py_cui.keys.KEY_ENTER, 
                                lambda: self.run_restore(os.path.join(backup_dir, menu.get())))
        
        self.root.show_popup(popup)
    
    def show_backup_list(self):
        """Show list of backups"""
        # Get backup list
        backup_dir = self.get_backup_dir()
        backups = []
        if os.path.exists(backup_dir):
            backups = [f for f in os.listdir(backup_dir) if f.startswith('migrator_backup_') and f.endswith('.json')]
            backups.sort(reverse=True)  # Most recent first
        
        if not backups:
            self.output_panel.set_text("No backups found.")
            return
        
        # Create a popup menu
        popup = self.root.create_popup('Manage Backups', 6, 70)
        menu = popup.add_scroll_menu('Available Backups', 0, 0, row_span=6, column_span=1)
        menu.add_item_list(backups)
        
        # Add buttons/help text
        info = popup.add_text_block('Options', 0, 1, row_span=6, column_span=1)
        info.set_text("""
Select a backup and press:

[Enter] - Show backup details
[c] - Compare with current system
[r] - Restore from this backup 
[p] - Generate installation plan
[d] - Delete this backup
[Esc] - Close this menu
""")
        
        # Set handlers
        menu.add_key_command(py_cui.keys.KEY_ENTER, 
                            lambda: self.view_backup_details(os.path.join(backup_dir, menu.get())))
        menu.add_key_command(ord('c'), 
                            lambda: self.run_compare(os.path.join(backup_dir, menu.get())))
        menu.add_key_command(ord('r'), 
                            lambda: self.run_restore(os.path.join(backup_dir, menu.get())))
        menu.add_key_command(ord('p'), 
                            lambda: self.run_plan(os.path.join(backup_dir, menu.get())))
        menu.add_key_command(ord('d'), 
                            lambda: self.delete_backup(os.path.join(backup_dir, menu.get())))
        
        self.root.show_popup(popup)
    
    def confirm_delete_backups(self):
        """Confirm deletion of all backups"""
        self.root.show_yes_no_popup(
            "Confirm Delete",
            f"Are you sure you want to delete ALL backups in {self.get_backup_dir()}?",
            self.delete_all_backups
        )
    
    def delete_all_backups(self, confirmed):
        """Delete all backups"""
        if confirmed:
            backup_dir = self.get_backup_dir()
            if os.path.exists(backup_dir):
                backups = [f for f in os.listdir(backup_dir) if f.startswith('migrator_backup_') and f.endswith('.json')]
                for backup in backups:
                    os.remove(os.path.join(backup_dir, backup))
                self.output_panel.set_text(f"Deleted {len(backups)} backups.")
                self.refresh_dashboard()
            else:
                self.output_panel.set_text("No backups found.")
    
    def delete_backup(self, backup_path):
        """Delete a specific backup"""
        if os.path.exists(backup_path):
            os.remove(backup_path)
            self.output_panel.set_text(f"Deleted {os.path.basename(backup_path)}")
            self.refresh_dashboard()
            self.root.stop_popup()
        else:
            self.output_panel.set_text(f"Backup not found: {backup_path}")
    
    def view_backup_details(self, backup_path):
        """View details of a backup"""
        try:
            import json
            if os.path.exists(backup_path):
                with open(backup_path, 'r') as f:
                    data = json.load(f)
                
                # Extract basic info
                system_info = data.get('system_info', {})
                packages = data.get('packages', [])
                configs = data.get('config_files', [])
                
                # Create a summary
                summary = f"""
Backup: {os.path.basename(backup_path)}
Path: {backup_path}

System Information:
- Distribution: {system_info.get('distro_name', 'Unknown')} {system_info.get('distro_version', '')}
- Last Updated: {system_info.get('last_updated', 'Unknown')}

Summary:
- Total Packages: {len(packages)}
- Total Config Files: {len(configs)}

Package Sources:
"""
                # Count package sources
                sources = {}
                for pkg in packages:
                    source = pkg.get('source', 'unknown')
                    sources[source] = sources.get(source, 0) + 1
                
                for source, count in sources.items():
                    summary += f"- {source}: {count}\n"
                
                self.root.stop_popup()
                # Show the summary
                popup = self.root.create_popup('Backup Details', 8, 70)
                text = popup.add_text_block('Details', 0, 0, row_span=8, column_span=1)
                text.set_text(summary)
                self.root.show_popup(popup)
                
            else:
                self.output_panel.set_text(f"Backup not found: {backup_path}")
        except Exception as e:
            self.output_panel.set_text(f"Error reading backup: {str(e)}")
    
    def view_state_file(self):
        """View the state file"""
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, 'r') as f:
                    content = f.read()
                
                # Truncate if too long
                if len(content) > 10000:
                    content = content[:10000] + "...\n[Content truncated, file too large]"
                
                popup = self.root.create_popup('State File Contents', 10, 90)
                text = popup.add_text_block('Contents', 0, 0, row_span=10, column_span=1)
                text.set_text(content)
                self.root.show_popup(popup)
            else:
                self.output_panel.set_text("State file does not exist. Run a scan first.")
        except Exception as e:
            self.output_panel.set_text(f"Error reading state file: {str(e)}")
    
    def view_log_file(self):
        """View the log file"""
        try:
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, 'r') as f:
                    content = f.read()
                
                # Get last 50 lines if file is large
                lines = content.splitlines()
                if len(lines) > 50:
                    content = "\n".join(lines[-50:])
                    content = "[Showing last 50 lines...]\n\n" + content
                
                popup = self.root.create_popup('Log File Contents', 10, 90)
                text = popup.add_text_block('Contents', 0, 0, row_span=10, column_span=1)
                text.set_text(content)
                self.root.show_popup(popup)
            else:
                self.output_panel.set_text("Log file does not exist.")
        except Exception as e:
            self.output_panel.set_text(f"Error reading log file: {str(e)}")
    
    def run_compare(self, backup_path):
        """Run comparison with backup"""
        self.root.stop_popup()
        self.run_migrator_command(f"compare {backup_path}")
    
    def run_plan(self, backup_path):
        """Generate installation plan"""
        self.root.stop_popup()
        self.run_migrator_command(f"plan {backup_path}")
    
    def run_restore(self, backup_path):
        """Restore from backup"""
        self.root.stop_popup()
        
        # Show restore options popup
        popup = self.root.create_popup('Restore Options', 12, 70)
        text = popup.add_text_block('Options', 0, 0, row_span=2, column_span=2)
        text.set_text("""Select restoration options:""")
        
        # Restoration type options
        rest_group = popup.add_checkbox_group('Restore Selection', 2, 0, row_span=4, column_span=1)
        rest_group.add_item("State only (no installation)", checked=True)
        rest_group.add_item("Install packages", checked=False)
        rest_group.add_item("Restore config files", checked=False)
        
        # Version policy options 
        ver_group = popup.add_radio_button_group('Version Policy', 2, 1, row_span=4, column_span=1)
        ver_group.add_item("Exact versions only", value=0)
        ver_group.add_item("Prefer same version, accept newer", value=1)
        ver_group.add_item("Prefer newer versions", value=2, selected=True)
        ver_group.add_item("Always use newest available", value=3)
        
        # Downgrade option
        downgrade_box = popup.add_checkbox("Allow package downgrades", 6, 0, checked=False)
        
        # Button row
        restore_btn = popup.add_button('Restore', 7, 0, column_span=2)
        
        # Set handler
        restore_btn.command = lambda: self._execute_restore_with_options(
            backup_path, 
            rest_group.get_checked_indices(),
            ver_group.get_selected_item_index(),
            downgrade_box.is_checked()
        )
        
        # Show popup
        self.root.show_popup(popup)
    
    def _execute_restore_with_options(self, backup_path, restore_options, version_policy_idx, allow_downgrade):
        """Execute restoration with selected options"""
        self.root.stop_popup()
        
        # Build command based on selected options
        cmd = f"restore {backup_path}"
        
        # Check what to restore
        state_only = 0 in restore_options and 1 not in restore_options and 2 not in restore_options
        packages = 1 in restore_options
        configs = 2 in restore_options
        
        if not state_only:
            if packages and configs:
                cmd += " --execute"
            elif packages:
                cmd += " --packages-only"
            elif configs:
                cmd += " --configs-only"
        
        # Add version policy
        version_policies = ["exact", "prefer-same", "prefer-newer", "always-newest"]
        selected_policy = version_policies[version_policy_idx]
        cmd += f" --version-policy={selected_policy}"
        
        # Add downgrade option
        if allow_downgrade:
            cmd += " --allow-downgrade"
        
        # Run the command
        self.run_migrator_command(cmd)
    
    def install_migrator(self):
        """Install Migrator"""
        if not self.is_venv_created:
            self.output_panel.set_text("Virtual environment not created. Create it first.")
            return
        
        # Installation commands
        commands = [
            f"{self.install_commands['activate']} && cd $PWD && pip install -r requirements.txt",
            f"{self.install_commands['activate']} && cd $PWD && pip install -e ."
        ]
        
        for cmd in commands:
            result = self.run_command(cmd)
            if not result:
                return
        
        self.output_panel.set_text("Migrator installed successfully!")
        self.refresh_system_info()
    
    def full_install(self):
        """Perform full installation"""
        # Check that migrator isn't already installed
        if self.is_migrator_installed:
            self.output_panel.set_text("Migrator is already installed.")
            return
        
        # Full installation commands
        commands = [
            self.install_commands['deps'],
            self.install_commands['venv'],
            f"{self.install_commands['activate']} && cd $PWD && pip install -r requirements.txt",
            f"{self.install_commands['activate']} && cd $PWD && pip install -e ."
        ]
        
        for cmd in commands:
            result = self.run_command(cmd)
            if not result:
                self.output_panel.set_text(f"Installation failed at step: {cmd}")
                return
        
        self.output_panel.set_text("Migrator installed successfully! You can now use the migrator command.")
        self.refresh_system_info()
    
    def show_service_scheduling(self):
        """Show advanced service scheduling options"""
        popup = self.root.create_popup('Service Scheduling', 10, 70)
        
        # Information text
        text = popup.add_text_block('Info', 0, 0, row_span=2, column_span=2)
        text.set_text("""
Select when you want the Migrator service to run:
        """)
        
        # Scheduling type selection
        schedule_group = popup.add_radio_button_group('Schedule Type', 2, 0, row_span=4, column_span=1)
        schedule_group.add_item("Once per day (default)", value=0, selected=True)
        schedule_group.add_item("Daily at specific time", value=1)
        schedule_group.add_item("Weekly at specific time", value=2)
        schedule_group.add_item("Monthly on specific day", value=3)
        
        # Options panel
        options_panel = popup.add_form('Options', 2, 1, row_span=4, column_span=1)
        
        # Daily time input
        options_panel.add_field('Daily time (HH:MM):', 1)
        
        # Weekly options input
        options_panel.add_field('Weekly day (Mon,Tue,Wed,Thu,Fri,Sat,Sun):', 2)
        options_panel.add_field('Weekly time (HH:MM):', 3)
        
        # Monthly options input
        options_panel.add_field('Monthly day (1-28):', 4)
        options_panel.add_field('Monthly time (HH:MM):', 5)
        
        # Set default values
        options_panel.set_field_value(1, "03:00")  # 3 AM default
        options_panel.set_field_value(2, "Sun")    # Sunday default
        options_panel.set_field_value(3, "03:00")  # 3 AM default
        options_panel.set_field_value(4, "1")      # 1st of month default
        options_panel.set_field_value(5, "03:00")  # 3 AM default
        
        # User or system service checkbox
        user_checkbox = popup.add_checkbox("Install as user service (no sudo needed)", 7, 0, column_span=2, checked=True)
        
        # Create buttons
        install_btn = popup.add_button('Install Service', 8, 0, column_span=1)
        cancel_btn = popup.add_button('Cancel', 8, 1, column_span=1)
        
        # Set handlers
        def on_install():
            schedule_type = schedule_group.get_selected_item_index()
            user_service = user_checkbox.is_checked()
            
            # Build command based on selected options
            cmd = "migrator install-service"
            
            if user_service:
                cmd += " --user"
            
            if schedule_type == 0:
                # Default daily, no additional arguments needed
                pass
            elif schedule_type == 1:
                # Daily at specific time
                daily_time = options_panel.get_field_value(1)
                cmd += f" --daily \"{daily_time}\""
            elif schedule_type == 2:
                # Weekly
                weekly_day = options_panel.get_field_value(2)
                weekly_time = options_panel.get_field_value(3)
                cmd += f" --weekly \"{weekly_day},{weekly_time}\""
            elif schedule_type == 3:
                # Monthly
                monthly_day = options_panel.get_field_value(4)
                monthly_time = options_panel.get_field_value(5)
                cmd += f" --monthly \"{monthly_day},{monthly_time}\""
            
            # Run the command
            self.root.stop_popup()
            self.run_command(cmd)
            self.refresh_system_info()
        
        install_btn.command = on_install
        cancel_btn.command = lambda: self.root.stop_popup()
        
        # Show the popup
        self.root.show_popup(popup)
    
    def install_service(self, user=False):
        """Install Migrator as a service"""
        if not self.is_migrator_installed:
            self.output_panel.set_text("Migrator is not installed. Install it first.")
            return
        
        # Service installation command
        if user:
            cmd = "migrator install-service --user"
        else:
            cmd = "migrator install-service"
        
        self.run_migrator_command(cmd)
        self.refresh_system_info()
    
    def remove_service(self):
        """Remove Migrator service"""
        if not self.is_service_installed:
            self.output_panel.set_text("No Migrator service is installed.")
            return
        
        # Service removal command
        if self.is_service_installed == "user":
            cmd = "migrator remove-service --user"
        else:
            cmd = "migrator remove-service"
        
        self.run_migrator_command(cmd)
        self.refresh_system_info()
    
    def check_service_status(self):
        """Check service status"""
        if not self.is_service_installed:
            self.output_panel.set_text("No Migrator service is installed.")
            return
        
        # Status command
        if self.is_service_installed == "user":
            cmd = "systemctl --user status migrator.service"
        else:
            cmd = "sudo systemctl status migrator.service"
        
        self.run_command(cmd)
    
    def restart_service(self):
        """Restart the service"""
        if not self.is_service_installed:
            self.output_panel.set_text("No Migrator service is installed.")
            return
        
        # Restart command
        if self.is_service_installed == "user":
            cmd = "systemctl --user restart migrator.service"
        else:
            cmd = "sudo systemctl restart migrator.service"
        
        self.run_command(cmd)
        self.output_panel.set_text(f"Service restart command sent: {cmd}")
    
    def run_command(self, command):
        """Run a shell command"""
        if self.running_task:
            self.output_panel.set_text("A command is already running. Please wait.")
            return False
        
        self.output_panel.set_text(f"Running: {command}\n")
        
        def run_in_thread():
            try:
                process = subprocess.Popen(
                    command, 
                    shell=True, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                output = []
                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    if line:
                        output.append(line.strip())
                        # Update UI from time to time
                        if len(output) % 5 == 0:
                            text = "\n".join(output[-10:])  # Show last 10 lines
                            self.output_panel.set_text(f"Running: {command}\n\n{text}")
                
                # Get any remaining output
                stdout, stderr = process.communicate()
                if stdout:
                    output.extend(stdout.splitlines())
                
                # Show final output
                self.task_result = process.returncode == 0
                if process.returncode == 0:
                    status = "Command completed successfully."
                else:
                    status = f"Command failed with exit code {process.returncode}."
                    if stderr:
                        status += "\nError: " + stderr
                
                # Show output
                text = "\n".join(output[-20:])  # Last 20 lines
                if len(output) > 20:
                    text = f"[{len(output)} lines, showing last 20]\n\n" + text
                
                self.output_panel.set_text(f"{status}\n\n{text}")
                
            except Exception as e:
                self.task_result = False
                self.output_panel.set_text(f"Error executing command: {str(e)}")
            
            finally:
                self.running_task = None
        
        # Start the command in a thread
        self.running_task = threading.Thread(target=run_in_thread)
        self.running_task.daemon = True
        self.running_task.start()
        
        # Wait for the task to complete or timeout
        start_time = time.time()
        while self.running_task and time.time() - start_time < 120:  # 2 minute timeout
            time.sleep(0.1)  # Brief pause to avoid CPU spinning
        
        if self.running_task:
            self.output_panel.set_text("Command is taking a long time. Continue in background.")
            return None  # Still running
        
        return self.task_result
    
    def run_migrator_command(self, command):
        """Run a migrator command"""
        # Use the wrapper script if it exists
        if os.path.exists(WRAPPER_PATH):
            cmd = f"{WRAPPER_PATH} {command}"
        # If in a virtualenv, use that
        elif "VIRTUAL_ENV" in os.environ:
            cmd = f"migrator {command}"
        # Try with python module
        else:
            cmd = f"python3 -m src.__main__ {command}"
        
        return self.run_command(cmd)


def main():
    """Main entry point for the TUI"""
    # Set up the CUI with 9 rows, 4 columns
    root = py_cui.PyCUI(9, 4)
    
    # Create our app
    app = MigratorTui(root)
    
    # Start the CUI
    root.start()


if __name__ == "__main__":
    main() 