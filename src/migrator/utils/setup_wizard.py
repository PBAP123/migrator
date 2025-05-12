#!/usr/bin/env python3
"""
Setup Wizard for Migrator - Interactive CLI configuration

This module provides an interactive setup wizard that guides users through
the initial configuration of the Migrator tool.

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
import logging
import getpass
from typing import Dict, Any, Optional, List, Tuple

from .config import config
from .service import create_systemd_service, remove_systemd_service

# Configure logging
logger = logging.getLogger(__name__)

class SetupWizard:
    """Interactive CLI setup wizard for Migrator"""
    
    def __init__(self):
        """Initialize the setup wizard"""
        self.config = config
        
        # Default configuration values
        self.user_config = {
            "backup_dir": config.get_backup_dir(),
            "include_desktop_configs": True,
            "include_fstab_portability": True,
            "include_repos": True,
            "include_paths": [],
            "exclude_paths": [],
            "schedule_backups": False,
            "backup_schedule": "daily",
            "backup_time": "03:00",
            "backup_retention": {
                "enabled": config.get_backup_retention_enabled(),
                "mode": config.get_backup_retention_mode(),
                "count": config.get_backup_retention_count(),
                "age_days": config.get_backup_retention_age_days()
            }
        }
    
    def _get_input(self, prompt: str, default: Optional[str] = None) -> str:
        """Get user input with prompt and optional default value
        
        Args:
            prompt: The prompt to display to the user
            default: Default value to use if user enters nothing
            
        Returns:
            User input or default value
        """
        if default is not None:
            full_prompt = f"{prompt} [{default}]: "
        else:
            full_prompt = f"{prompt}: "
            
        user_input = input(full_prompt).strip()
        
        if not user_input and default is not None:
            return default
        return user_input
    
    def _get_int_input(self, prompt: str, default: int, min_value: int, max_value: Optional[int] = None) -> int:
        """Get integer input with validation
        
        Args:
            prompt: The prompt to display to the user
            default: Default value to use if user enters nothing
            min_value: Minimum acceptable value
            max_value: Maximum acceptable value (optional)
            
        Returns:
            Valid integer input
        """
        while True:
            input_str = self._get_input(prompt, str(default))
            
            try:
                value = int(input_str)
                
                if value < min_value:
                    print(f"Error: Value must be at least {min_value}.")
                    continue
                    
                if max_value is not None and value > max_value:
                    print(f"Error: Value must not exceed {max_value}.")
                    continue
                    
                return value
            except ValueError:
                print(f"Error: Please enter a valid integer.")
    
    def _get_yes_no(self, prompt: str, default: bool = False) -> bool:
        """Get yes/no input with prompt
        
        Args:
            prompt: The prompt to display to the user
            default: Default value to use if user enters nothing
            
        Returns:
            Boolean result (True for yes, False for no)
        """
        default_str = "y" if default else "n"
        
        while True:
            full_prompt = f"{prompt} (y/n) [{default_str}]: "
            user_input = input(full_prompt).strip().lower()
            
            if not user_input:
                return default
                
            if user_input in ["y", "yes"]:
                return True
            elif user_input in ["n", "no"]:
                return False
            else:
                print("Error: Please enter 'y' or 'n'.")
    
    def _print_header(self, title: str) -> None:
        """Print a formatted header
        
        Args:
            title: Title of the header
        """
        print("\n" + "=" * 60)
        print(f"  {title}")
        print("=" * 60 + "\n")
    
    def _print_section(self, title: str) -> None:
        """Print a formatted section title
        
        Args:
            title: Title of the section
        """
        print(f"\n--- {title} ---")
    
    def run_wizard(self) -> Dict[str, Any]:
        """Run the interactive setup wizard
        
        Returns:
            Dictionary of configuration options set by the user
        """
        self._print_header("Migrator Setup Wizard")
        print("Welcome to the Migrator setup wizard.")
        print("This wizard will guide you through the initial configuration of Migrator.")
        print("Press Ctrl+C at any time to cancel the setup.\n")
        
        try:
            # Section 1: Backup Content
            self._print_section("Backup Content Configuration")
            print("First, let's configure what content to include in your backups.\n")
            
            # Ask about desktop environment configurations
            self.user_config["include_desktop_configs"] = self._get_yes_no(
                "Include desktop environment configurations?",
                default=True
            )
            
            # Ask about fstab entries
            self.user_config["include_fstab_portability"] = self._get_yes_no(
                "Include portable fstab entries (network shares)?",
                default=True
            )
            
            # Ask about including software repositories
            self.user_config["include_repos"] = self._get_yes_no(
                "Include software repositories (APT, DNF, PPAs, etc.)?",
                default=True
            )
            
            # Section 1.1: Custom Path Configuration
            self._print_section("Custom Path Configuration")
            print("You can specify additional paths to include or exclude from backups.\n")
            
            # Ask about including custom paths
            include_custom_paths = self._get_yes_no(
                "Would you like to specify custom paths to include in backups?",
                default=False
            )
            
            if include_custom_paths:
                print("\nEnter paths separated by commas. You can use:")
                print("- Absolute paths (e.g., /home/user/Documents/notes.txt)")
                print("- Home directory paths (e.g., ~/projects/configs)")
                print("- Glob patterns (e.g., ~/.config/app/*.conf)")
                
                include_paths_input = self._get_input(
                    "\nPaths to include",
                    default=""
                )
                
                if include_paths_input:
                    # Split by comma and strip whitespace
                    self.user_config["include_paths"] = [
                        path.strip() for path in include_paths_input.split(",") if path.strip()
                    ]
                    print(f"Added {len(self.user_config['include_paths'])} paths to include list")
            
            # Ask about excluding custom paths
            exclude_custom_paths = self._get_yes_no(
                "Would you like to specify paths to exclude from backups?",
                default=False
            )
            
            if exclude_custom_paths:
                print("\nEnter paths separated by commas. You can use:")
                print("- Absolute paths (e.g., /home/user/Downloads)")
                print("- Home directory paths (e.g., ~/.local/share/Steam)")
                print("- Glob patterns (e.g., ~/.config/chrome/*/Cache)")
                
                exclude_paths_input = self._get_input(
                    "\nPaths to exclude",
                    default=""
                )
                
                if exclude_paths_input:
                    # Split by comma and strip whitespace
                    self.user_config["exclude_paths"] = [
                        path.strip() for path in exclude_paths_input.split(",") if path.strip()
                    ]
                    print(f"Added {len(self.user_config['exclude_paths'])} paths to exclude list")
            
            # Section 2: Backup Destination
            self._print_section("Backup Destination")
            print("Next, let's set the destination path for your backups.\n")
            
            # Get backup directory
            default_backup_dir = self.user_config["backup_dir"]
            while True:
                backup_dir = self._get_input(
                    "Enter path for backup storage",
                    default=default_backup_dir
                )
                
                # Expand user directory if needed
                backup_dir = os.path.expanduser(backup_dir)
                
                # Validate the directory
                try:
                    # Try to create it if it doesn't exist
                    os.makedirs(backup_dir, exist_ok=True)
                    
                    # Check if it's writable
                    if os.access(backup_dir, os.W_OK):
                        self.user_config["backup_dir"] = backup_dir
                        break
                    else:
                        print(f"Error: Directory '{backup_dir}' is not writable.")
                except Exception as e:
                    print(f"Error: Could not create directory '{backup_dir}': {e}")
            
            # Section 3: Backup Retention Rules
            self._print_section("Backup Retention Rules")
            print("Configure automatic cleanup of old backups to manage storage space.\n")
            
            # Ask about enabling backup retention
            self.user_config["backup_retention"]["enabled"] = self._get_yes_no(
                "Enable automatic cleanup of old backups?",
                default=False
            )
            
            if self.user_config["backup_retention"]["enabled"]:
                # Ask about retention mode
                print("\nSelect how to determine which backups to keep:")
                print("1. Keep the most recent N backups")
                print("2. Keep backups newer than X days")
                
                mode_choice = ""
                while mode_choice not in ["1", "2"]:
                    mode_choice = self._get_input("Select retention mode (1-2)", default="1")
                
                if mode_choice == "1":
                    # Count-based retention
                    self.user_config["backup_retention"]["mode"] = "count"
                    self.user_config["backup_retention"]["count"] = self._get_int_input(
                        "How many recent backups to keep?", 
                        default=5, 
                        min_value=1
                    )
                else:
                    # Age-based retention
                    self.user_config["backup_retention"]["mode"] = "age"
                    self.user_config["backup_retention"]["age_days"] = self._get_int_input(
                        "Keep backups newer than how many days?", 
                        default=30, 
                        min_value=1
                    )
            
            # Section 4: Scheduling
            self._print_section("Backup Scheduling")
            print("Finally, let's configure automated backup scheduling.\n")
            
            # Ask about scheduling backups
            self.user_config["schedule_backups"] = self._get_yes_no(
                "Set up automated scheduled backups?",
                default=False
            )
            
            if self.user_config["schedule_backups"]:
                # Ask about schedule frequency
                print("\nSelect backup frequency:")
                print("1. Daily")
                print("2. Weekly")
                print("3. Monthly")
                
                while True:
                    choice = self._get_input("Enter your choice (1-3)", default="1")
                    
                    if choice == "1":
                        self.user_config["backup_schedule"] = "daily"
                        
                        # Ask for time
                        while True:
                            time_input = self._get_input(
                                "Enter daily backup time (HH:MM, 24-hour format)",
                                default="03:00"
                            )
                            
                            # Validate time format
                            if self._validate_time_format(time_input):
                                self.user_config["backup_time"] = time_input
                                break
                            else:
                                print("Error: Invalid time format. Please use HH:MM format (e.g., 03:00).")
                        
                        break
                    elif choice == "2":
                        self.user_config["backup_schedule"] = "weekly"
                        
                        # Ask for day of week
                        print("\nSelect day of week:")
                        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                        for i, day in enumerate(days, 1):
                            print(f"{i}. {day}")
                            
                        while True:
                            day_choice = self._get_input("Enter your choice (1-7)", default="1")
                            
                            try:
                                day_idx = int(day_choice) - 1
                                if 0 <= day_idx < len(days):
                                    self.user_config["backup_day"] = days[day_idx]
                                    break
                                else:
                                    print("Error: Please enter a number between 1 and 7.")
                            except ValueError:
                                print("Error: Please enter a number between 1 and 7.")
                        
                        # Ask for time
                        while True:
                            time_input = self._get_input(
                                "Enter backup time (HH:MM, 24-hour format)",
                                default="03:00"
                            )
                            
                            # Validate time format
                            if self._validate_time_format(time_input):
                                self.user_config["backup_time"] = time_input
                                break
                            else:
                                print("Error: Invalid time format. Please use HH:MM format (e.g., 03:00).")
                        
                        break
                    elif choice == "3":
                        self.user_config["backup_schedule"] = "monthly"
                        
                        # Ask for day of month
                        while True:
                            day_input = self._get_input("Enter day of month (1-28)", default="1")
                            
                            try:
                                day = int(day_input)
                                if 1 <= day <= 28:
                                    self.user_config["backup_day"] = day
                                    break
                                else:
                                    print("Error: Please enter a number between 1 and 28.")
                            except ValueError:
                                print("Error: Please enter a number between 1 and 28.")
                        
                        # Ask for time
                        while True:
                            time_input = self._get_input(
                                "Enter backup time (HH:MM, 24-hour format)",
                                default="03:00"
                            )
                            
                            # Validate time format
                            if self._validate_time_format(time_input):
                                self.user_config["backup_time"] = time_input
                                break
                            else:
                                print("Error: Invalid time format. Please use HH:MM format (e.g., 03:00).")
                        
                        break
                    else:
                        print("Error: Invalid choice. Please enter a number between 1 and 3.")
            
            # Confirm settings
            self._print_section("Configuration Summary")
            print("Please review your configuration:")
            print(f"• Backup directory: {self.user_config['backup_dir']}")
            print(f"• Include desktop configurations: {'Yes' if self.user_config['include_desktop_configs'] else 'No'}")
            print(f"• Include portable fstab entries: {'Yes' if self.user_config['include_fstab_portability'] else 'No'}")
            print(f"• Include software repositories: {'Yes' if self.user_config['include_repos'] else 'No'}")
            
            # Show custom include/exclude paths
            if self.user_config["include_paths"]:
                if len(self.user_config["include_paths"]) <= 3:
                    # Show all paths if there are just a few
                    print(f"• Custom include paths: {', '.join(self.user_config['include_paths'])}")
                else:
                    # Show a summary for larger lists
                    print(f"• Custom include paths: {len(self.user_config['include_paths'])} paths")
                    for i, path in enumerate(self.user_config["include_paths"][:3]):
                        print(f"  - {path}")
                    print(f"  - ... and {len(self.user_config['include_paths']) - 3} more")

            if self.user_config["exclude_paths"]:
                if len(self.user_config["exclude_paths"]) <= 3:
                    # Show all paths if there are just a few
                    print(f"• Custom exclude paths: {', '.join(self.user_config['exclude_paths'])}")
                else:
                    # Show a summary for larger lists
                    print(f"• Custom exclude paths: {len(self.user_config['exclude_paths'])} paths")
                    for i, path in enumerate(self.user_config["exclude_paths"][:3]):
                        print(f"  - {path}")
                    print(f"  - ... and {len(self.user_config['exclude_paths']) - 3} more")
            
            # Show retention settings
            if self.user_config["backup_retention"]["enabled"]:
                retention_config = self.user_config["backup_retention"]
                if retention_config["mode"] == "count":
                    print(f"• Backup retention: Keep the last {retention_config['count']} backups")
                else:
                    print(f"• Backup retention: Keep backups newer than {retention_config['age_days']} days")
            else:
                print("• Backup retention: Disabled (backups kept indefinitely)")
            
            # Show scheduling settings
            if self.user_config["schedule_backups"]:
                if self.user_config["backup_schedule"] == "daily":
                    print(f"• Automated backups: Daily at {self.user_config['backup_time']}")
                elif self.user_config["backup_schedule"] == "weekly":
                    print(f"• Automated backups: Weekly on {self.user_config['backup_day']} at {self.user_config['backup_time']}")
                elif self.user_config["backup_schedule"] == "monthly":
                    print(f"• Automated backups: Monthly on day {self.user_config['backup_day']} at {self.user_config['backup_time']}")
            else:
                print("• Automated backups: Disabled")
            
            print("\nIs this configuration correct?")
            confirm = self._get_yes_no("Save this configuration", default=True)
            
            if confirm:
                # Save configuration
                self._save_configuration()
                
                print("\nConfiguration saved successfully!")
                return self.user_config
            else:
                print("\nSetup cancelled. No changes were made.")
                return {}
        except KeyboardInterrupt:
            print("\n\nSetup cancelled. No changes were made.")
            return {}
    
    def _validate_time_format(self, time_str: str) -> bool:
        """Validate time format (HH:MM)
        
        Args:
            time_str: Time string to validate
            
        Returns:
            Whether the time format is valid
        """
        try:
            hour, minute = time_str.split(":")
            hour = int(hour)
            minute = int(minute)
            
            return 0 <= hour < 24 and 0 <= minute < 60
        except (ValueError, TypeError):
            return False
    
    def _save_configuration(self) -> None:
        """Save the configuration
        
        This method saves the user configuration to the config file
        and sets up the systemd service if requested.
        """
        # Save backup directory
        self.config.set_backup_dir(self.user_config["backup_dir"])
        
        # Save other configuration values
        self.config.set("include_desktop_configs", self.user_config["include_desktop_configs"])
        self.config.set("include_fstab_portability", self.user_config["include_fstab_portability"])
        self.config.set("include_repos", self.user_config["include_repos"])
        
        # Save include/exclude paths
        self.config.set("include_paths", self.user_config["include_paths"])
        self.config.set("exclude_paths", self.user_config["exclude_paths"])
        
        # Save backup retention settings
        retention_config = self.user_config["backup_retention"]
        self.config.set_backup_retention(
            enabled=retention_config["enabled"],
            mode=retention_config["mode"],
            count=retention_config["count"],
            age_days=retention_config["age_days"]
        )
        
        # Setup systemd service if enabled
        if self.user_config["schedule_backups"]:
            # Set schedule configuration
            self.config.set("schedule_backups", True)
            self.config.set("backup_schedule", self.user_config["backup_schedule"])
            self.config.set("backup_time", self.user_config["backup_time"])
            
            if "backup_day" in self.user_config:
                self.config.set("backup_day", self.user_config["backup_day"])
            
            # Create the systemd service
            self._setup_systemd_service()
    
    def _setup_systemd_service(self) -> None:
        """Set up the systemd service based on user configuration
        
        This creates a systemd service and timer for automated backups
        with the schedule defined by the user.
        """
        # Remove existing service if any (to avoid conflicts)
        try:
            remove_systemd_service(user_unit=True)
        except Exception as e:
            logger.warning(f"Failed to remove existing service: {e}")
        
        # Schedule string for systemd timer
        schedule = ""
        
        if self.user_config["backup_schedule"] == "daily":
            # Format: "OnCalendar=*-*-* HH:MM:00"
            schedule = f"*-*-* {self.user_config['backup_time']}:00"
        elif self.user_config["backup_schedule"] == "weekly":
            # Format: "OnCalendar=Mon *-*-* HH:MM:00" (or the day specified)
            day = self.user_config.get("backup_day", "Monday")[:3]  # First 3 letters
            schedule = f"{day} *-*-* {self.user_config['backup_time']}:00"
        elif self.user_config["backup_schedule"] == "monthly":
            # Format: "OnCalendar=*-*-01 HH:MM:00" (or the day specified)
            day = str(self.user_config.get("backup_day", 1)).zfill(2)
            schedule = f"*-*-{day} {self.user_config['backup_time']}:00"
        
        # Create the systemd service with the custom schedule
        try:
            create_systemd_service(
                user_unit=True,
                schedule=schedule
            )
            logger.info(f"Created systemd service with schedule: {schedule}")
        except Exception as e:
            logger.error(f"Failed to create systemd service: {e}")
            print(f"Error: Failed to create systemd service: {e}")


# Create instance for easy access
wizard = SetupWizard()

def run_setup_wizard() -> Dict[str, Any]:
    """Run the interactive setup wizard
    
    Returns:
        Dictionary of configuration options set by the user
    """
    return wizard.run_wizard() 