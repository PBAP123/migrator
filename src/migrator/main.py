#!/usr/bin/env python3
"""
Main application module for Migrator - a system migration utility

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
import json
import logging
import argparse
import datetime
import time
from typing import List, Dict, Any, Optional, Set, Tuple
import shutil
import subprocess

# Import package manager modules
from .package_managers.factory import PackageManagerFactory
from .package_managers.base import Package, PackageManager

# Import config tracker modules
from .config_trackers.base import ConfigFile
from .config_trackers.system_config import SystemConfigTracker
from .config_trackers.user_config import UserConfigTracker
from .config_trackers.desktop_environment import DesktopEnvironmentTracker

# Import utilities
from .utils.distro import get_distro_info, DistroInfo
from .utils.config import config
from .utils.sysvar import system_variables, SystemVariables
from .utils.fstab import FstabManager
from .utils.progress import ProgressTracker, MultiProgressTracker, OperationType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.expanduser("~/.local/share/migrator/migrator.log"))
    ]
)

logger = logging.getLogger(__name__)

class Migrator:
    """Main application class for Migrator"""
    
    def __init__(self):
        """Initialize the application"""
        # Create data directory if it doesn't exist
        self.data_dir = os.path.expanduser("~/.local/share/migrator")
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Initialize system information
        self.distro_info = get_distro_info()
        logger.info(f"Detected distribution: {self.distro_info.name} {self.distro_info.version}")
        
        # Initialize package managers
        self.package_managers = PackageManagerFactory.create_for_system()
        logger.info(f"Initialized {len(self.package_managers)} package managers")
        
        # Initialize config trackers
        self.system_config_tracker = SystemConfigTracker()
        self.user_config_tracker = UserConfigTracker()
        self.desktop_env_tracker = DesktopEnvironmentTracker()
        logger.info("Initialized configuration trackers")
        
        # Load or initialize the system state
        self.state_file = os.path.join(self.data_dir, "system_state.json")
        self.state = self._load_state()
        
        # Ensure backup directory exists
        backup_dir = config.get_backup_dir()
        os.makedirs(backup_dir, exist_ok=True)
        logger.info(f"Using backup directory: {backup_dir}")
        
        # Initialize system variables
        self.system_variables = system_variables
        logger.info(f"Using system variables: username={self.system_variables.username}, home={self.system_variables.home_dir}")
    
    def _load_state(self) -> Dict[str, Any]:
        """Load the system state from disk or initialize a new one"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                logger.info(f"Loaded system state from {self.state_file}")
                return state
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading system state: {e}")
        
        # Initialize a new state
        return {
            "system_info": {
                "distro_name": self.distro_info.name,
                "distro_version": self.distro_info.version,
                "distro_id": self.distro_info.id,
                "last_updated": datetime.datetime.now().isoformat()
            },
            "packages": [],
            "config_files": []
        }
    
    def _save_state(self) -> None:
        """Save the current system state to disk"""
        # Update last updated timestamp
        self.state["system_info"]["last_updated"] = datetime.datetime.now().isoformat()
        
        try:
            # Create a backup of the previous state file
            if os.path.exists(self.state_file):
                backup_file = f"{self.state_file}.bak"
                shutil.copy2(self.state_file, backup_file)
            
            # Write the state file
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            
            logger.info(f"Saved system state to {self.state_file}")
        except IOError as e:
            logger.error(f"Error saving system state: {e}")
    
    def scan_packages(self, test_mode=False) -> List[Package]:
        """Scan the system for installed packages
        
        Args:
            test_mode: If True, run in test mode with limited package scanning
        """
        all_packages = []
        
        logger.info("Scanning for installed packages...")
        print("Starting package scan. This process may take several minutes depending on how many packages are installed.")
        if test_mode:
            print("Running in TEST MODE - only processing a limited number of packages")
        
        # Create a progress tracker for package scanning
        with ProgressTracker(
            operation_type=OperationType.PACKAGE_SCAN,
            desc="Scanning for installed packages",
            total=len(self.package_managers),
            unit="managers"
        ) as progress:
            for i, pm in enumerate(self.package_managers):
                try:
                    manager_name = pm.name.upper()
                    print(f"\n--- Scanning {manager_name} packages ({i+1}/{len(self.package_managers)} package managers) ---")
                    progress.update(status=f"Scanning packages with {pm.name}")
                    
                    start_time = time.time()
                    # Call list_installed_packages with test_mode if the method supports it
                    if hasattr(pm, 'list_installed_packages') and 'test_mode' in pm.list_installed_packages.__code__.co_varnames:
                        packages = pm.list_installed_packages(test_mode=test_mode)
                    else:
                        packages = pm.list_installed_packages()
                    scan_time = time.time() - start_time
                    
                    all_packages.extend(packages)
                    progress.update(1, f"Found {len(packages)} packages with {pm.name}")
                    logger.info(f"Found {len(packages)} packages with {pm.name} in {scan_time:.2f} seconds")
                    print(f"Completed {manager_name} scan: found {len(packages)} packages in {scan_time:.2f} seconds")
                except Exception as e:
                    logger.error(f"Error scanning packages with {pm.name}: {e}")
                    progress.update(1, f"Error scanning with {pm.name}")
                    print(f"Failed to scan {pm.name} packages: {str(e)}")
        
        manual_count = sum(1 for pkg in all_packages if getattr(pkg, 'manually_installed', False))
        
        total_msg = f"Total packages found: {len(all_packages)} (including {manual_count} manually installed)"
        logger.info(total_msg)
        print(f"\n{total_msg}")
        
        return all_packages
    
    def scan_config_files(self, include_desktop=True, 
                          desktop_environments=None, exclude_desktop=None) -> List[ConfigFile]:
        """Scan the system for configuration files
        
        Args:
            include_desktop: Whether to include desktop environment configs
            desktop_environments: List of specific desktop environments to include
            exclude_desktop: List of desktop environments to exclude
        """
        all_configs = []
        
        # Create a tracker for overall config scanning
        with ProgressTracker(
            operation_type=OperationType.CONFIG_SCAN,
            desc="Scanning for configuration files",
            total=3 if include_desktop else 2,
            unit="categories"
        ) as progress:
            # System configs
            progress.update(status="Scanning system configurations")
            logger.info("Scanning for system configuration files...")
            system_configs = self.system_config_tracker.find_config_files()
            all_configs.extend(system_configs)
            progress.update(1, f"Found {len(system_configs)} system config files")
            logger.info(f"Found {len(system_configs)} system configuration files")
            
            # User configs
            progress.update(status="Scanning user configurations")
            logger.info("Scanning for user configuration files...")
            user_configs = self.user_config_tracker.find_config_files()
            all_configs.extend(user_configs)
            progress.update(1, f"Found {len(user_configs)} user config files")
            logger.info(f"Found {len(user_configs)} user configuration files")
            
            # Desktop configs
            if include_desktop:
                progress.update(status="Scanning desktop environment configurations")
                logger.info("Scanning for desktop environment configuration files...")
                de_configs = self.desktop_env_tracker.find_config_files(
                    include_desktop=include_desktop,
                    desktop_environments=desktop_environments,
                    exclude_desktop=exclude_desktop
                )
                all_configs.extend(de_configs)
                progress.update(1, f"Found {len(de_configs)} desktop config files")
                logger.info(f"Found {len(de_configs)} desktop environment configuration files")
        
        logger.info(f"Total configuration files found: {len(all_configs)}")
        
        # Check if we have portable fstab entries
        if self.system_config_tracker.has_portable_fstab_entries():
            # Add the fstab data to the portable fstab config file
            for config in all_configs:
                if config.path == "/etc/fstab.portable" and config.category == "fstab_portable":
                    # Get the fstab manager and add its data to the config
                    fstab_manager = self.system_config_tracker.get_fstab_manager()
                    if fstab_manager:
                        # We'll add this data to the config file's dict when serializing
                        # Save it in the object for now
                        config.fstab_data = fstab_manager.to_dict()
                        logger.debug("Added fstab data to portable fstab config")
        
        return all_configs
    
    def update_system_state(self, include_desktop=True, 
                           desktop_environments=None, exclude_desktop=None,
                           include_fstab_portability=True, test_mode=False) -> None:
        """Update the system state with current packages and configuration files
        
        Args:
            include_desktop: Whether to include desktop environment configs
            desktop_environments: List of specific desktop environments to include
            exclude_desktop: List of desktop environments to exclude
            include_fstab_portability: Whether to include portable fstab entries
            test_mode: If True, run in test mode with limited package scanning
        """
        # Scan packages
        packages = self.scan_packages(test_mode=test_mode)
        
        # Set fstab portability flag in system config tracker
        self.system_config_tracker.include_fstab_portability = include_fstab_portability
        logger.info(f"Setting fstab portability to: {include_fstab_portability}")
        
        self.state["packages"] = [pkg.to_dict() for pkg in packages]
        
        # Scan configuration files
        config_files = self.scan_config_files(
            include_desktop=include_desktop,
            desktop_environments=desktop_environments,
            exclude_desktop=exclude_desktop
        )
        
        # Convert configs to dicts with extra data for special cases
        config_dicts = []
        fstab_found = False
        
        for cfg in config_files:
            cfg_dict = cfg.to_dict()
            
            # Add fstab data if available
            if cfg.path == "/etc/fstab.portable" and hasattr(cfg, 'fstab_data'):
                cfg_dict["fstab_data"] = cfg.fstab_data
                fstab_found = True
                logger.info(f"Found and added fstab portable data to backup")
                
            config_dicts.append(cfg_dict)
        
        if not fstab_found:
            logger.warning("No portable fstab data found in configuration files")
            # Check if the system tracker has fstab entries
            if hasattr(self.system_config_tracker, 'portable_fstab_entries'):
                logger.info(f"System tracker has {len(self.system_config_tracker.portable_fstab_entries)} portable fstab entries")
            
            # Check if regular fstab was included 
            regular_fstab = any(cfg.path == "/etc/fstab" for cfg in config_files)
            logger.info(f"Regular fstab included: {regular_fstab}")
        
        self.state["config_files"] = config_dicts
        
        # Save state
        self._save_state()
    
    def backup_state(self, backup_dir: Optional[str] = None) -> str:
        """Backup the current system state to a specified directory
        
        Args:
            backup_dir: Path to the backup directory, or None to use the configured directory
        
        Returns:
            Path to the created backup file, or empty string if failed
        """
        # Create a multi-progress tracker for the backup operation
        multi_progress = MultiProgressTracker(overall_desc="System backup", overall_total=4)
        multi_progress.start_overall()
        
        try:
            # Use configured backup directory if none is specified
            if backup_dir is None:
                backup_dir = config.get_backup_dir()
            
            os.makedirs(backup_dir, exist_ok=True)
            
            # Get the hostname for organizing backups
            hostname = self.system_variables.hostname
            # Sanitize hostname for directory name (remove invalid characters)
            safe_hostname = ''.join(c if c.isalnum() or c in '-_' else '_' for c in hostname)
            
            # Create a host-specific subdirectory for multi-system organization
            host_backup_dir = os.path.join(backup_dir, safe_hostname)
            os.makedirs(host_backup_dir, exist_ok=True)
            
            # Create a timestamped backup file with hostname
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(host_backup_dir, f"migrator_backup_{timestamp}_{safe_hostname}.json")
            
            multi_progress.update_overall(1, f"Starting backup to {host_backup_dir}")
            
            try:
                # Add system variables to the state for portability
                self.state["system_variables"] = self.system_variables.to_dict()
                
                # Add enhanced metadata about the source machine
                self.state["backup_metadata"] = {
                    "hostname": self.system_variables.hostname,
                    "distro_name": self.distro_info.name,
                    "distro_version": self.distro_info.version,
                    "distro_id": self.distro_info.id,
                    "timestamp": timestamp,
                    "backup_version": "1.2"  # Updated version of the backup format
                }
                
                # Check for fstab data and ensure it's included
                has_fstab_portable = False
                for cfg in self.state.get("config_files", []):
                    if cfg.get("path") == "/etc/fstab.portable" and "fstab_data" in cfg:
                        has_fstab_portable = True
                        logger.info(f"Verified fstab data is included in the backup")
                        portable_entries = cfg.get("fstab_data", {}).get("portable_entries", [])
                        logger.info(f"Backup includes {len(portable_entries)} portable fstab entries")
                        break
                
                if not has_fstab_portable and self.system_config_tracker.has_portable_fstab_entries():
                    logger.warning("Portable fstab entries exist but are not included in the backup")
                    # Attempt to fix this by adding them directly
                    for cfg_idx, cfg in enumerate(self.state.get("config_files", [])):
                        if cfg.get("path") == "/etc/fstab.portable":
                            if not "fstab_data" in cfg:
                                fstab_manager = self.system_config_tracker.get_fstab_manager()
                                if fstab_manager:
                                    self.state["config_files"][cfg_idx]["fstab_data"] = fstab_manager.to_dict()
                                    logger.info("Added missing fstab data to backup")
                
                # Write the state file
                with open(backup_file, 'w') as f:
                    json.dump(self.state, f, indent=2)
                
                logger.info(f"Backed up system state to {backup_file}")
                multi_progress.update_overall(1, "System state saved")
                
                # Create a directory for config files
                configs_dir = os.path.join(host_backup_dir, "config_files")
                os.makedirs(configs_dir, exist_ok=True)
                
                # Create tracker for config file copying
                config_files = self.state.get("config_files", [])
                config_tracker = multi_progress.create_tracker(
                    "config_copy", 
                    OperationType.BACKUP,
                    total=len(config_files),
                    desc="Copying configuration files",
                    unit="files"
                )
                multi_progress.activate_tracker("config_copy")
                config_tracker.start()
                
                # Copy all config files
                config_count = 0
                for i, config_file in enumerate(config_files):
                    path = config_file["path"]
                    if os.path.exists(path) and os.access(path, os.R_OK):
                        # Create relative path structure
                        relative_path = path.lstrip("/")
                        target_dir = os.path.join(configs_dir, os.path.dirname(relative_path))
                        os.makedirs(target_dir, exist_ok=True)
                        
                        # Copy the file
                        target_path = os.path.join(configs_dir, relative_path)
                        try:
                            shutil.copy2(path, target_path)
                            config_count += 1
                            config_tracker.update(1, f"Copied {path}")
                        except Exception as e:
                            logger.error(f"Error copying config file {path}: {e}")
                            config_tracker.update(1, f"Error copying {path}")
                    else:
                        config_tracker.update(1, f"Skipped {path} (not readable)")
                
                logger.info(f"Backed up {config_count} configuration files to {configs_dir}")
                multi_progress.close_tracker("config_copy", f"Copied {config_count} configuration files")
                multi_progress.update_overall(1, "Configuration files backed up")
                
                # Check if retention rules are enabled and cleanup old backups if needed
                if config.get_backup_retention_enabled():
                    deleted_count = self.cleanup_old_backups(host_backup_dir)
                    if deleted_count > 0:
                        logger.info(f"Cleaned up {deleted_count} old backups based on retention policy")
                
                multi_progress.update_overall(1, "Backup completed")
                multi_progress.close_all("Backup process completed successfully")
                return backup_file
                
            except Exception as e:
                logger.error(f"Error during backup: {e}")
                multi_progress.close_all("Backup process failed")
                return ""
                
        except Exception as e:
            logger.error(f"Error during backup setup: {e}")
            multi_progress.close_all("Backup setup failed")
            return ""

    def cleanup_old_backups(self, backup_dir: str) -> int:
        """Clean up old backups based on retention policy
        
        Args:
            backup_dir: Path to the backup directory (usually host-specific)
            
        Returns:
            Number of backups deleted
        """
        # Check if retention is enabled
        if not config.get_backup_retention_enabled():
            return 0
            
        # Get all backup files in the directory
        backup_files = []
        try:
            for item in os.listdir(backup_dir):
                item_path = os.path.join(backup_dir, item)
                if os.path.isfile(item_path) and item.startswith('migrator_backup_') and item.endswith('.json'):
                    backup_files.append(item_path)
        except (PermissionError, FileNotFoundError) as e:
            logger.error(f"Error scanning backup directory {backup_dir}: {e}")
            return 0
            
        # If there are no backups, return
        if not backup_files:
            return 0
            
        # Sort by modification time (oldest first)
        backup_files.sort(key=lambda f: os.path.getmtime(f))
        
        # Determine which files to delete based on retention policy
        files_to_delete = []
        
        retention_mode = config.get_backup_retention_mode()
        
        if retention_mode == "count":
            # Keep only the last N backups
            keep_count = config.get_backup_retention_count()
            
            # Calculate how many to delete
            if len(backup_files) > keep_count:
                # Files are sorted oldest first, so we delete the oldest ones
                files_to_delete = backup_files[:-keep_count]
                
        elif retention_mode == "age":
            # Keep backups newer than X days
            max_age_days = config.get_backup_retention_age_days()
            cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
            
            # Find files older than the cutoff
            for file_path in backup_files:
                if os.path.getmtime(file_path) < cutoff_time:
                    files_to_delete.append(file_path)
                    
        # Delete the files
        deleted_count = 0
        for file_path in files_to_delete:
            try:
                # For each backup file, check if there's a corresponding config_files directory
                filename = os.path.basename(file_path)
                backup_id = filename.replace('migrator_backup_', '').replace('.json', '')
                
                # Delete the backup file
                os.remove(file_path)
                deleted_count += 1
                logger.debug(f"Deleted old backup: {file_path}")
                
            except (PermissionError, FileNotFoundError) as e:
                logger.error(f"Error deleting backup file {file_path}: {e}")
                
        return deleted_count
    
    def get_backup_dir(self) -> str:
        """Get the configured backup directory
        
        Returns:
            Path to the configured backup directory
        """
        return config.get_backup_dir()
        
    def get_backup_retention_settings(self) -> Dict[str, Any]:
        """Get current backup retention settings
        
        Returns:
            Dictionary containing backup retention settings
        """
        return {
            "enabled": config.get_backup_retention_enabled(),
            "mode": config.get_backup_retention_mode(),
            "count": config.get_backup_retention_count(),
            "age_days": config.get_backup_retention_age_days()
        }
        
    def enable_backup_retention(self) -> bool:
        """Enable backup retention
        
        Returns:
            Whether the operation was successful
        """
        return config.set_backup_retention(enabled=True)
        
    def disable_backup_retention(self) -> bool:
        """Disable backup retention
        
        Returns:
            Whether the operation was successful
        """
        return config.set_backup_retention(enabled=False)
        
    def set_backup_retention_count(self, count: int) -> bool:
        """Set backup retention to count mode with specified count
        
        Args:
            count: Number of backups to keep
            
        Returns:
            Whether the operation was successful
        """
        return config.set_backup_retention(enabled=True, mode="count", count=count)
        
    def set_backup_retention_age(self, days: int) -> bool:
        """Set backup retention to age mode with specified days
        
        Args:
            days: Number of days to keep backups
            
        Returns:
            Whether the operation was successful
        """
        return config.set_backup_retention(enabled=True, mode="age", age_days=days)
        
    def scan_for_backups(self, search_removable: bool = True, search_network: bool = False) -> List[str]:
        """Scan common locations for Migrator backups
        
        This is particularly useful for finding backups on external media
        
        Args:
            search_removable: Whether to search removable media
            search_network: Whether to search network mounts
        
        Returns:
            List of paths to found backup files
        """
        backup_files = []
        
        # First check the configured backup directory
        backup_dir = config.get_backup_dir()
        if os.path.exists(backup_dir):
            # Check for backups directly in the backup directory (for backward compatibility)
            for f in os.listdir(backup_dir):
                item_path = os.path.join(backup_dir, f)
                if os.path.isfile(item_path) and f.startswith('migrator_backup_') and f.endswith('.json'):
                    backup_files.append(item_path)
                    
            # Check for backups in host-specific subdirectories
            for subdir in os.listdir(backup_dir):
                subdir_path = os.path.join(backup_dir, subdir)
                if os.path.isdir(subdir_path):
                    self._scan_directory_for_backups(subdir_path, backup_files, max_depth=1)
        
        # Add more search paths as needed
        search_paths = [
            os.path.expanduser("~/Documents/migrator"),
            os.path.expanduser("~/Backups/migrator")
        ]
        
        if search_removable:
            # Add common removable media mount points
            search_paths.extend([
                "/media",
                "/mnt",
                os.path.expanduser("~/media")
            ])
            
        if search_network:
            # Add network mount points
            search_paths.extend([
                "/net",
                "/srv/nfs",
                os.path.expanduser("~/network")
            ])
            
        # Search paths
        for base_path in search_paths:
            if not os.path.exists(base_path):
                continue
                
            # Look for backup files in each path
            self._scan_directory_for_backups(base_path, backup_files)
            
        return backup_files
        
    def _scan_directory_for_backups(self, directory: str, backup_files: List[str], max_depth: int = 2) -> None:
        """Scan a directory (recursively) for backup files
        
        Args:
            directory: Directory to scan
            backup_files: List to append found backup files to
            max_depth: Maximum recursion depth
        """
        if max_depth <= 0:
            return
            
        try:
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)
                
                # Check if it's a backup file
                if os.path.isfile(item_path) and item.startswith('migrator_backup_') and item.endswith('.json'):
                    backup_files.append(item_path)
                    
                # Recurse into subdirectories
                elif os.path.isdir(item_path):
                    self._scan_directory_for_backups(item_path, backup_files, max_depth - 1)
        except (PermissionError, OSError):
            # Skip directories we can't access
            pass

    def get_host_specific_backups(self, hostname: Optional[str] = None) -> List[str]:
        """Get backups for a specific host
        
        Args:
            hostname: The hostname to get backups for, or None to use current hostname
        
        Returns:
            List of paths to backup files for the specified host
        """
        if hostname is None:
            hostname = self.system_variables.hostname
        
        # Sanitize hostname for directory name (remove invalid characters)
        safe_hostname = ''.join(c if c.isalnum() or c in '-_' else '_' for c in hostname)
        
        all_backups = self.scan_for_backups(search_removable=False, search_network=False)
        
        # Filter backups by hostname
        host_backups = []
        for backup in all_backups:
            # Check if the backup is in a host-specific directory or has the hostname in the filename
            backup_dir = os.path.dirname(backup)
            if os.path.basename(backup_dir) == safe_hostname or f"_{safe_hostname}.json" in os.path.basename(backup):
                host_backups.append(backup)
        
        return host_backups

    def list_backup_hosts(self) -> List[str]:
        """List all hosts that have backups
        
        Returns:
            List of hostnames that have backups
        """
        backup_dir = config.get_backup_dir()
        if not os.path.exists(backup_dir):
            return []
        
        hosts = []
        
        # Check for host-specific subdirectories
        for item in os.listdir(backup_dir):
            item_path = os.path.join(backup_dir, item)
            if os.path.isdir(item_path):
                # Check if the directory contains backup files
                for f in os.listdir(item_path):
                    if f.startswith('migrator_backup_') and f.endswith('.json'):
                        hosts.append(item)
                        break
        
        # For backward compatibility, check for backups directly in the backup directory
        # and extract hostnames from filenames
        for item in os.listdir(backup_dir):
            if item.startswith('migrator_backup_') and item.endswith('.json'):
                filename = item.replace(".json", "")
                parts = filename.split("_")
                if len(parts) >= 4:  # migrator_backup_timestamp_hostname
                    hostname = "_".join(parts[3:])  # Join all parts after the timestamp
                    if hostname not in hosts:
                        hosts.append(hostname)
        
        return hosts

    def get_backup_metadata(self, backup_file: str) -> Dict[str, Any]:
        """Get metadata from a backup file
        
        Args:
            backup_file: Path to the backup file
        
        Returns:
            Dictionary containing metadata about the backup
        """
        try:
            # Check if file exists
            if not os.path.exists(backup_file):
                return {"error": "Backup file not found"}
            
            # Load backup file
            with open(backup_file, 'r') as f:
                backup_data = json.load(f)
            
            # Get file info
            file_size = os.path.getsize(backup_file)
            file_date = datetime.datetime.fromtimestamp(os.path.getmtime(backup_file))
            filename = os.path.basename(backup_file)
            
            # Extract metadata
            metadata = {}
            
            # Basic file info
            metadata["filename"] = filename
            metadata["file_size"] = file_size
            metadata["file_date"] = file_date.isoformat()
            
            # New backup metadata format
            if "backup_metadata" in backup_data:
                metadata.update(backup_data["backup_metadata"])
                
                # Add information about backup organization structure
                host_dir = os.path.basename(os.path.dirname(backup_file))
                if host_dir != os.path.basename(config.get_backup_dir()):
                    metadata["host_directory"] = host_dir
            else:
                # Extract from basic system info
                if "system_info" in backup_data:
                    metadata["distro_name"] = backup_data["system_info"].get("distro_name", "")
                    metadata["distro_version"] = backup_data["system_info"].get("distro_version", "")
                    metadata["distro_id"] = backup_data["system_info"].get("distro_id", "")
                
                # Extract from system variables if available
                if "system_variables" in backup_data:
                    metadata["hostname"] = backup_data["system_variables"].get("hostname", "unknown")
                    metadata["username"] = backup_data["system_variables"].get("username", "")
                
                # Parse timestamp and hostname from filename
                if "_backup_" in filename and filename.endswith(".json"):
                    # Try to parse the new format: migrator_backup_YYYYMMDD_HHMMSS_hostname.json
                    parts = filename.replace(".json", "").split("_backup_")[1].split("_")
                    if len(parts) >= 2:
                        date_part = parts[0]
                        if len(date_part) >= 8:  # YYYYMMDD
                            metadata["timestamp"] = date_part
                        
                        # If there are at least 3 parts (timestamp, time, hostname)
                        if len(parts) >= 3:
                            # Join any parts after the time as the hostname (in case hostname had underscores)
                            hostname_part = "_".join(parts[2:])
                            if "hostname" not in metadata or metadata["hostname"] == "unknown":
                                metadata["hostname"] = hostname_part
            
            # Count items
            metadata["package_count"] = len(backup_data.get("packages", []))
            metadata["config_count"] = len(backup_data.get("config_files", []))
            
            # Get package managers used
            package_sources = list(set(pkg.get("source", "") for pkg in backup_data.get("packages", [])))
            metadata["package_sources"] = package_sources
            
            return metadata
        except Exception as e:
            logger.error(f"Error getting backup metadata: {e}")
            return {"error": str(e)}
    
    def is_first_run(self) -> bool:
        """Check if this is the first run of Migrator
        
        Returns:
            True if no previous state or configuration exists
        """
        # Check if state file exists
        state_exists = os.path.exists(self.state_file)
        
        # Check if config file exists with non-default values
        config_file = os.path.join(os.path.expanduser("~/.config/migrator"), "config.json")
        config_exists = os.path.exists(config_file)
        
        # If neither exists, this is a first run
        if not state_exists and not config_exists:
            return True
            
        # If config exists but is empty/default, still consider it a first run
        if not state_exists and config_exists:
            try:
                with open(config_file, 'r') as f:
                    config_data = json.load(f)
                
                # If config only contains the default backup_dir, still consider it a first run
                if len(config_data) == 1 and "backup_dir" in config_data:
                    return True
            except (json.JSONDecodeError, IOError):
                # If config file exists but is invalid, consider it a first run
                return True
                
        return False
