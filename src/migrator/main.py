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
import glob
import fnmatch
import platform
from pathlib import Path
from . import __version__

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
from .utils.repositories import RepositoryManager, Repository

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
        
        # Initialize empty lists for packages and config files
        # These will be populated when system state is updated
        self.installed_packages = []
        self.config_files = []
        
        # Try to load existing data from state if available
        if 'packages' in self.state and self.state['packages']:
            # Packages in state are stored as dictionaries, so convert them to Package objects
            try:
                from .package_managers.base import Package
                self.installed_packages = [Package.from_dict(pkg) for pkg in self.state['packages']]
                logger.info(f"Loaded {len(self.installed_packages)} packages from state")
            except Exception as e:
                logger.warning(f"Could not load packages from state: {e}")
        
        if 'config_files' in self.state and self.state['config_files']:
            # Config files in state are stored as dictionaries, so convert them to ConfigFile objects
            try:
                from .config_trackers.base import ConfigFile
                self.config_files = [ConfigFile.from_dict(cfg) for cfg in self.state['config_files']]
                logger.info(f"Loaded {len(self.config_files)} config files from state")
            except Exception as e:
                logger.warning(f"Could not load config files from state: {e}")
                
        # Initialize repository data
        self.repo_sources = self.state.get('repositories', {'repositories': []})
    
    def _load_state(self) -> Dict[str, Any]:
        """Load the system state from disk or initialize a new one"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                
                # Extract include/exclude paths from the loaded state
                self.include_paths = state.get("include_paths", [])
                self.exclude_paths = state.get("exclude_paths", [])
                
                logger.info(f"Loaded system state from {self.state_file}")
                return state
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading system state: {e}")
        
        # Initialize include/exclude paths from config
        self.include_paths = config.get("include_paths", [])
        self.exclude_paths = config.get("exclude_paths", [])
        
        # Initialize a new state
        return {
            "system_info": {
                "distro_name": self.distro_info.name,
                "distro_version": self.distro_info.version,
                "distro_id": self.distro_info.id,
                "last_updated": datetime.datetime.now().isoformat()
            },
            "packages": [],
            "config_files": [],
            "include_paths": self.include_paths,
            "exclude_paths": self.exclude_paths
        }
    
    def _save_state(self) -> bool:
        """Save the current system state to disk"""
        try:
            # Update last updated timestamp
            self.state["system_info"]["last_updated"] = datetime.datetime.now().isoformat()
            
            # Ensure the packages and config_files are updated
            self.state["packages"] = [pkg.to_dict() for pkg in self.installed_packages]
            self.state["config_files"] = []
            
            # Save include_paths and exclude_paths
            self.state["include_paths"] = self.include_paths
            self.state["exclude_paths"] = self.exclude_paths
            
            # Include repository sources if available
            if hasattr(self, 'repo_sources') and self.repo_sources:
                self.state["repositories"] = self.repo_sources
            
            # Process configuration files
            for cfg in self.config_files:
                cfg_dict = cfg.to_dict()
                
                # Add special processing for certain config files
                if cfg.path == "/etc/fstab.portable" and hasattr(cfg, 'fstab_data'):
                    cfg_dict["fstab_data"] = cfg.fstab_data
                    
                self.state["config_files"].append(cfg_dict)
            
            # Create a backup of the previous state file
            if os.path.exists(self.state_file):
                backup_file = f"{self.state_file}.bak"
                shutil.copy2(self.state_file, backup_file)
            
            # Write the state file
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            
            logger.info(f"Saved system state to {self.state_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving system state: {e}")
            return False
    
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
                          desktop_environments=None, exclude_desktop=None,
                          include_paths=None, exclude_paths=None) -> List[ConfigFile]:
        """Scan the system for configuration files
        
        Args:
            include_desktop: Whether to include desktop environment configs
            desktop_environments: List of specific desktop environments to include
            exclude_desktop: List of desktop environments to exclude
            include_paths: List of additional paths to include in the scan
            exclude_paths: List of paths to exclude from the scan
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
            system_configs = self.system_config_tracker.find_config_files(
                exclude_paths=exclude_paths
            )
            all_configs.extend(system_configs)
            progress.update(1, f"Found {len(system_configs)} system config files")
            logger.info(f"Found {len(system_configs)} system configuration files")
            
            # User configs
            progress.update(status="Scanning user configurations")
            logger.info("Scanning for user configuration files...")
            user_configs = self.user_config_tracker.find_config_files(
                include_paths=include_paths,
                exclude_paths=exclude_paths
            )
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
                    exclude_desktop=exclude_desktop,
                    exclude_paths=exclude_paths
                )
                all_configs.extend(de_configs)
                progress.update(1, f"Found {len(de_configs)} desktop config files")
                logger.info(f"Found {len(de_configs)} desktop environment configuration files")
        
        logger.info(f"Total configuration files found: {len(all_configs)}")
        
        # Add any additional explicitly included paths
        if include_paths:
            additional_configs = self._add_additional_paths(include_paths, all_configs)
            if additional_configs:
                all_configs.extend(additional_configs)
                logger.info(f"Added {len(additional_configs)} user-specified config files")
        
        # Remove any explicitly excluded paths
        if exclude_paths:
            initial_count = len(all_configs)
            all_configs = self._filter_excluded_paths(all_configs, exclude_paths)
            excluded_count = initial_count - len(all_configs)
            if excluded_count > 0:
                logger.info(f"Excluded {excluded_count} config files from user-specified exclusions")
        
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
    
    def _add_additional_paths(self, include_paths: List[str], existing_configs: List[ConfigFile]) -> List[ConfigFile]:
        """Add user-specified paths to the config scan
        
        Args:
            include_paths: List of additional paths to include
            existing_configs: List of already found config files
            
        Returns:
            List of additionally found config files
        """
        additional_configs = []
        existing_paths = {config.path for config in existing_configs}
        
        for path in include_paths:
            # Expand path (handle ~ and globs)
            expanded_path = os.path.expanduser(path)
            
            # For globs, find all matching files
            if '*' in expanded_path:
                try:
                    for matching_path in glob.glob(expanded_path):
                        if os.path.isfile(matching_path) and matching_path not in existing_paths:
                            # Create a new config file object
                            if matching_path.startswith('/etc'):
                                config = self.system_config_tracker.track_config_file(matching_path)
                            else:
                                config = self.user_config_tracker.track_config_file(matching_path)
                                
                            if config:
                                additional_configs.append(config)
                                existing_paths.add(config.path)
                                logger.debug(f"Added user-specified path: {matching_path}")
                except Exception as e:
                    logger.error(f"Error processing include path pattern {path}: {e}")
            # For directories, add all files within
            elif os.path.isdir(expanded_path):
                try:
                    for root, dirs, files in os.walk(expanded_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            if os.path.isfile(file_path) and file_path not in existing_paths:
                                # Create a new config file object based on path
                                if file_path.startswith('/etc'):
                                    config = self.system_config_tracker.track_config_file(file_path)
                                else:
                                    config = self.user_config_tracker.track_config_file(file_path)
                                    
                                if config:
                                    additional_configs.append(config)
                                    existing_paths.add(config.path)
                                    logger.debug(f"Added user-specified path: {file_path}")
                except Exception as e:
                    logger.error(f"Error walking directory {expanded_path}: {e}")
            # For individual files
            elif os.path.isfile(expanded_path) and expanded_path not in existing_paths:
                # Create a new config file object based on path
                if expanded_path.startswith('/etc'):
                    config = self.system_config_tracker.track_config_file(expanded_path)
                else:
                    config = self.user_config_tracker.track_config_file(expanded_path)
                    
                if config:
                    additional_configs.append(config)
                    logger.debug(f"Added user-specified path: {expanded_path}")
        
        return additional_configs
    
    def _filter_excluded_paths(self, configs: List[ConfigFile], exclude_paths: List[str]) -> List[ConfigFile]:
        """Filter out excluded paths from the config list
        
        Args:
            configs: List of config files
            exclude_paths: List of paths to exclude
            
        Returns:
            Filtered list of config files
        """
        if not exclude_paths:
            return configs
        
        # Process exclude paths to handle globs and expansion
        expanded_exclude_patterns = []
        for path in exclude_paths:
            expanded_path = os.path.expanduser(path)
            expanded_exclude_patterns.append(expanded_path)
        
        # Filter out configs that match any exclude pattern
        filtered_configs = []
        for config in configs:
            should_exclude = False
            
            for pattern in expanded_exclude_patterns:
                # For exact file matches
                if pattern == config.path:
                    should_exclude = True
                    logger.debug(f"Excluding path (exact match): {config.path}")
                    break
                    
                # For glob matches
                elif '*' in pattern:
                    if fnmatch.fnmatch(config.path, pattern):
                        should_exclude = True
                        logger.debug(f"Excluding path (pattern match): {config.path}")
                        break
                        
                # For directory matches (exclude all files in directory)
                elif os.path.isdir(pattern) and config.path.startswith(pattern + '/'):
                    should_exclude = True
                    logger.debug(f"Excluding path (directory child): {config.path}")
                    break
            
            if not should_exclude:
                filtered_configs.append(config)
        
        return filtered_configs
    
    def update_system_state(self, include_desktop=True, 
                           desktop_environments=None, exclude_desktop=None,
                           include_paths=None, exclude_paths=None,
                           include_fstab_portability=True, include_repos=True,
                           test_mode=False) -> None:
        """Update the system state by scanning for packages and configuration files
        
        Args:
            include_desktop: Whether to include desktop environment configs
            desktop_environments: List of specific desktop environments to include
            exclude_desktop: List of desktop environments to exclude
            include_paths: List of additional paths to include in the config scan
            exclude_paths: List of paths to exclude from the config scan
            include_fstab_portability: Whether to process fstab for portable entries
            include_repos: Whether to include software repositories
            test_mode: Whether to run in test mode (reduced package scanning)
        """
        # Update fstab portability setting
        self.system_config_tracker.include_fstab_portability = include_fstab_portability
        
        # Update system variables to ensure they're current
        self.system_variables.update()
        
        # Scan for installed packages
        logger.info("Scanning for installed packages...")
        self.installed_packages = self.scan_packages(test_mode=test_mode)
        logger.info(f"Found {len(self.installed_packages)} installed packages")
        
        # Scan for configuration files
        logger.info("Scanning for configuration files...")
        self.config_files = self.scan_config_files(
            include_desktop=include_desktop,
            desktop_environments=desktop_environments,
            exclude_desktop=exclude_desktop,
            include_paths=include_paths,
            exclude_paths=exclude_paths
        )
        logger.info(f"Found {len(self.config_files)} configuration files")
        
        # Scan for software repositories if enabled
        if include_repos:
            logger.info("Scanning for software repositories...")
            self.repo_sources = self.scan_repo_sources()
            logger.info(f"Found {len(self.repo_sources['repositories'])} repository sources")
        else:
            logger.info("Software repository scanning disabled")
            self.repo_sources = []
        
        # Update last scan time
        self.last_scan_time = datetime.datetime.now()
        
        # Save system state to disk
        self._save_state()
        
        logger.info("System state updated successfully")
    
    def backup_state(self, backup_dir: Optional[str] = None) -> Optional[str]:
        """Backup the current system state to a file
        
        Args:
            backup_dir: Directory to store the backup file, or None for default
            
        Returns:
            Path to the created backup file, or None if backup failed
        """
        if not backup_dir:
            backup_dir = config.get_backup_dir()
        
        # Make sure the backup directory exists
        os.makedirs(backup_dir, exist_ok=True)
        
        # Generate a timestamp for the backup filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Check if any config files might have portability issues
        config_paths = [cfg.path for cfg in self.config_files]
        
        # Get warnings from each config tracker
        portability_warnings = {}
        
        # Check user config tracker for warnings
        if hasattr(self.user_config_tracker, 'get_path_warnings'):
            user_warnings = self.user_config_tracker.get_path_warnings(config_paths)
            if user_warnings:
                portability_warnings.update(user_warnings)
        
        # Display warnings to the user if any found
        if portability_warnings:
            print("\nPORTABILITY WARNINGS:")
            print("----------------------")
            print("The following paths in your backup may have portability issues:")
            for path, warning in portability_warnings.items():
                print(f"\n- {path}:")
                print(f"  {warning}")
            
            print("\nDo you want to continue with the backup?")
            choice = input("Continue? (y/n) [y]: ").strip().lower()
            
            if choice and choice not in ['y', 'yes']:
                print("Backup cancelled.")
                return None
        
        # Get hostname for organizing backups
        hostname = platform.node() or "unknown"
        
        # Create host-specific directory
        safe_hostname = ''.join(c if c.isalnum() or c in '-_' else '_' for c in hostname)
        host_backup_dir = os.path.join(backup_dir, safe_hostname)
        os.makedirs(host_backup_dir, exist_ok=True)
        
        # Create backup file in the host-specific directory
        backup_file = os.path.join(host_backup_dir, f"migrator_backup_{timestamp}_{hostname}.json")
        
        # Create a config_files directory for storing actual configuration files
        configs_dir = os.path.join(os.path.dirname(backup_file), "config_files")
        os.makedirs(configs_dir, exist_ok=True)
        
        # Create a backup data structure
        backup_data = {
            "timestamp": timestamp,
            "version": __version__,
            "hostname": hostname,
            "system_variables": self.system_variables.to_dict(),
            "packages": [pkg.to_dict() for pkg in self.installed_packages],
            "config_files": [],
        }
        
        # Add repo sources if available
        if self.repo_sources:
            backup_data["repositories"] = self.repo_sources
        
        # Process config files
        for cfg in self.config_files:
            cfg_dict = cfg.to_dict()
            
            # Add special processing for certain config files
            if cfg.path == "/etc/fstab.portable" and hasattr(cfg, 'fstab_data'):
                cfg_dict["fstab_data"] = cfg.fstab_data
            
            backup_data["config_files"].append(cfg_dict)
            
            # Copy the actual config file to the backup directory
            if os.path.exists(cfg.path) and os.path.isfile(cfg.path) and os.access(cfg.path, os.R_OK):
                try:
                    # Create subdirectories as needed
                    target_path = os.path.join(configs_dir, cfg.path.lstrip('/'))
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    
                    # Copy the file
                    shutil.copy2(cfg.path, target_path)
                    logger.debug(f"Backed up config file: {cfg.path}")
                except Exception as e:
                    logger.warning(f"Failed to backup config file {cfg.path}: {e}")
        
        # Write the backup file
        try:
            with open(backup_file, 'w') as f:
                json.dump(backup_data, f, indent=2)
            
            logger.info(f"System state backed up to {backup_file}")
            
            # Apply retention rules
            deleted_count = self.cleanup_old_backups(host_backup_dir)
            if deleted_count > 0:
                logger.info(f"Removed {deleted_count} old backups based on retention policy")
                
            return backup_file
        except Exception as e:
            logger.error(f"Error backing up system state: {e}")
            return None
    
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
        
    def set_backup_dir(self, backup_dir: str) -> bool:
        """Set the backup directory
        
        Args:
            backup_dir: Path to the backup directory
            
        Returns:
            Whether the operation was successful
        """
        return config.set_backup_dir(backup_dir)
        
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
        """Check if this is the first run of the application
        
        Returns:
            True if this is the first run, False otherwise
        """
        # Check if state file exists
        if not os.path.exists(self.state_file):
            return True
            
        # Check if config file exists with non-default values
        user_config_file = os.path.expanduser("~/.config/migrator/config.json")
        if not os.path.exists(user_config_file):
            return True
            
        # If config exists but is empty/default, still consider it a first run
        try:
            with open(user_config_file, 'r') as f:
                user_config = json.load(f)
                
            # If config only contains the default backup_dir, still consider it a first run
            if len(user_config) == 1 and "backup_dir" in user_config:
                return True
                
            return False
        except:
            return True
            
    def restore_from_backup(self, backup_file: str, execute_plan: bool = False) -> bool:
        """Restore system state from backup file
        
        Args:
            backup_file: Path to the backup file
            execute_plan: Whether to execute the installation plan
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if file exists
            if not os.path.exists(backup_file):
                logger.error(f"Backup file not found: {backup_file}")
                return False
                
            # Load backup file
            with open(backup_file, 'r') as f:
                backup_data = json.load(f)
                
            # Extract metadata
            metadata = backup_data.get("backup_metadata", {})
            source_distro = metadata.get("distro_name", "Unknown")
            source_distro_id = metadata.get("distro_id", "unknown")
            source_hostname = metadata.get("hostname", "unknown")
            backup_version = metadata.get("backup_version", "1.0")
            
            print(f"Loaded backup from {source_hostname} running {source_distro}")
            logger.info(f"Backup version: {backup_version}, from {source_distro} ({source_distro_id})")
            
            # Check compatibility with current system
            target_distro = self.distro_info.name
            target_distro_id = self.distro_info.id
            
            if source_distro_id != target_distro_id:
                print(f"Warning: Backup is from {source_distro}, but current system is {target_distro}")
                print("Some configurations may not be compatible across different distributions.")
                logger.warning(f"Cross-distribution restore: {source_distro_id} to {target_distro_id}")
                
            # Load packages from backup
            packages = backup_data.get("packages", [])
            logger.info(f"Found {len(packages)} packages in backup")
            print(f"Found {len(packages)} packages in backup")
            
            # Group packages by manager
            packages_by_manager = {}
            for pkg in packages:
                manager = pkg.get("source", "unknown")
                if manager not in packages_by_manager:
                    packages_by_manager[manager] = []
                packages_by_manager[manager].append(pkg)
                
            # Report package manager counts
            for manager, pkgs in packages_by_manager.items():
                logger.info(f"  - {manager}: {len(pkgs)} packages")
                manual_count = sum(1 for p in pkgs if p.get("manually_installed", False))
                print(f"  - {manager}: {len(pkgs)} packages ({manual_count} manually installed)")
                
            # Load config files from backup
            config_files = backup_data.get("config_files", [])
            logger.info(f"Found {len(config_files)} configuration files in backup")
            print(f"Found {len(config_files)} configuration files in backup")
            
            # Check for repositories in backup
            repos_info = backup_data.get("repositories", {})
            repositories = repos_info.get("repositories", [])
            if repositories:
                logger.info(f"Found {len(repositories)} software repositories in backup")
                print(f"Found {len(repositories)} software repositories in backup")
                
                # Check repository compatibility
                repo_manager = RepositoryManager()
                compatibility_issues = repo_manager.check_compatibility(repos_info)
                
                if compatibility_issues:
                    print(f"\nDetected {len(compatibility_issues)} repository compatibility issues:")
                    for issue in compatibility_issues:
                        print(f"  - {issue['name']}: {issue['issue']}")
                        logger.warning(f"Repository compatibility issue: {issue['name']} - {issue['issue']}")
                
                compatible_repos = len(repositories) - len(compatibility_issues)
                if compatible_repos > 0:
                    print(f"{compatible_repos} repositories are compatible with your system")
                
            # If execute_plan is True, restore repositories immediately if available
            if execute_plan and repositories:
                print("\nRestoring compatible software repositories...")
                repo_manager = RepositoryManager()
                successes, issues = repo_manager.restore_repositories(repos_info, dry_run=False)
                
                # Print success messages
                if successes:
                    print("\nSuccessfully restored repositories:")
                    for success in successes:
                        print(f"  - {success}")
                
                # Print issues
                if issues:
                    print("\nIssues encountered during repository restoration:")
                    for issue in issues:
                        print(f"  - {issue['message']}")
            
            # Set the state from the backup data
            self.state = backup_data
            
            # Update the current system info in the state
            self.state["system_info"] = {
                "distro_name": self.distro_info.name,
                "distro_version": self.distro_info.version,
                "distro_id": self.distro_info.id,
                "last_updated": datetime.datetime.now().isoformat()
            }
            
            # Save the state
            self._save_state()
            
            logger.info("System state restored from backup")
            return True
            
        except Exception as e:
            logger.error(f"Error restoring from backup: {e}")
            return False
            
    def generate_installation_plan(self, backup_file: str) -> Dict[str, Any]:
        """Generate a package installation plan from backup file without executing it
        
        This function analyzes a backup file and creates a detailed plan of what would be
        installed, but does not make any changes to the system.
        
        Args:
            backup_file: Path to the backup file
            
        Returns:
            Dict containing installation plan details
        """
        logger.info(f"Generating installation plan from {backup_file}")
        
        try:
            # Check if file exists
            if not os.path.exists(backup_file):
                logger.error(f"Backup file not found: {backup_file}")
                return {
                    "available": [],
                    "unavailable": [],
                    "upgradable": [],
                    "installation_commands": []
                }
                
            # Load backup file
            with open(backup_file, 'r') as f:
                backup_data = json.load(f)
                
            # Extract metadata
            metadata = backup_data.get("backup_metadata", {})
            source_distro = metadata.get("distro_name", "Unknown")
            source_distro_id = metadata.get("distro_id", "unknown")
            
            # Load packages from backup
            packages = backup_data.get("packages", [])
            if not packages:
                logger.warning("No packages found in backup")
                return {
                    "available": [],
                    "unavailable": [],
                    "upgradable": [],
                    "installation_commands": []
                }
                
            logger.info(f"Found {len(packages)} packages in backup from {source_distro}")
            
            # Initialize lists for package status
            available_packages = []
            unavailable_packages = []
            upgradable_packages = []
            installation_commands = []
            
            # Group packages by package manager
            grouped_packages = {}
            for pkg in packages:
                source = pkg.get("source", "unknown")
                if source not in grouped_packages:
                    grouped_packages[source] = []
                grouped_packages[source].append(pkg)
            
            # Create a dictionary mapping package manager names to instances
            pkg_manager_map = {pm.name: pm for pm in self.package_managers}
            
            # Process each package source in a consistent order to make output more predictable
            source_order = ['apt', 'snap', 'flatpak', 'dnf', 'pacman', 'yum']
            processed_sources = set()
            
            # First process sources in the preferred order
            for source in source_order:
                if source in grouped_packages and source in pkg_manager_map:
                    pkgs = grouped_packages[source]
                    pkg_manager = pkg_manager_map[source]
                    
                    # Add a comment indicating the source type
                    installation_commands.append(f"# {source.upper()} Packages ({len(pkgs)} packages from backup)")
                    
                    # Get list of available packages and potential installation commands
                    try:
                        # Handle different package manager return types consistently
                        result = pkg_manager.plan_installation(pkgs)
                        
                        # Snap manager returns tuple; others return dictionary
                        if isinstance(result, tuple) and len(result) == 4:
                            available, unavailable, upgrade_candidates, commands = result
                        elif isinstance(result, dict):
                            available = result.get("available", [])
                            unavailable = result.get("unavailable", [])
                            upgrade_candidates = result.get("upgradable", [])
                            commands = result.get("installation_commands", [])
                        else:
                            logger.error(f"Unexpected result type from {source} package manager: {type(result)}")
                            continue
                        
                        # Ensure all packages have source information
                        for pkg_list in [available, unavailable, upgrade_candidates]:
                            for i, pkg in enumerate(pkg_list):
                                if isinstance(pkg, str):
                                    # Convert string package names to dictionaries
                                    pkg_list[i] = {"name": pkg, "source": source}
                                elif isinstance(pkg, dict) and "source" not in pkg:
                                    # Add source to dictionaries that don't have it
                                    pkg["source"] = source
                        
                        # Add to our overall lists
                        available_packages.extend(available)
                        unavailable_packages.extend(unavailable)
                        upgradable_packages.extend(upgrade_candidates)
                        installation_commands.extend(commands)
                        
                        logger.info(f"Plan for {source}: {len(available)} available, {len(unavailable)} unavailable")
                    except Exception as e:
                        logger.error(f"Error planning for {source}: {e}")
                    
                    processed_sources.add(source)
            
            # Then process any remaining sources
            for source, pkgs in grouped_packages.items():
                if source in processed_sources:
                    continue  # Already processed
                    
                # Get the appropriate package manager instance
                if source in pkg_manager_map:
                    pkg_manager = pkg_manager_map[source]
                    logger.info(f"Checking availability of {len(pkgs)} {source} packages")
                    
                    # Add a comment indicating the source type
                    installation_commands.append(f"# {source.upper()} Packages ({len(pkgs)} packages from backup)")
                    
                    # Get list of available packages and potential installation commands
                    try:
                        # Handle different package manager return types consistently
                        result = pkg_manager.plan_installation(pkgs)
                        
                        # Snap manager returns tuple; others return dictionary
                        if isinstance(result, tuple) and len(result) == 4:
                            available, unavailable, upgrade_candidates, commands = result
                        elif isinstance(result, dict):
                            available = result.get("available", [])
                            unavailable = result.get("unavailable", [])
                            upgrade_candidates = result.get("upgradable", [])
                            commands = result.get("installation_commands", [])
                        else:
                            logger.error(f"Unexpected result type from {source} package manager: {type(result)}")
                            continue
                        
                        # Ensure all packages have source information
                        for pkg_list in [available, unavailable, upgrade_candidates]:
                            for i, pkg in enumerate(pkg_list):
                                if isinstance(pkg, str):
                                    # Convert string package names to dictionaries
                                    pkg_list[i] = {"name": pkg, "source": source}
                                elif isinstance(pkg, dict) and "source" not in pkg:
                                    # Add source to dictionaries that don't have it
                                    pkg["source"] = source
                        
                        # Add to our overall lists
                        available_packages.extend(available)
                        unavailable_packages.extend(unavailable)
                        upgradable_packages.extend(upgrade_candidates)
                        installation_commands.extend(commands)
                        
                        logger.info(f"Plan for {source}: {len(available)} available, {len(unavailable)} unavailable")
                    except Exception as e:
                        logger.error(f"Error planning for {source}: {e}")
                else:
                    # If package manager not available, all packages are unavailable
                    logger.warning(f"Package manager {source} not available on this system")
                    installation_commands.append(f"# {source.upper()} Packages - Package manager not available on this system")
                    for pkg in pkgs:
                        # Ensure pkg is a dictionary with source and reason fields
                        if isinstance(pkg, str):
                            unavailable_packages.append({
                                "name": pkg,
                                "source": source,
                                "reason": f"Package manager {source} not available on this system"
                            })
                        else:
                            pkg_dict = pkg.copy() if isinstance(pkg, dict) else {"name": str(pkg), "source": source}
                            pkg_dict["reason"] = f"Package manager {source} not available on this system"
                            unavailable_packages.append(pkg_dict)
            
            # Create and return the plan
            plan = {
                "available": available_packages,
                "unavailable": unavailable_packages,
                "upgradable": upgradable_packages,
                "installation_commands": installation_commands
            }
            
            return plan
            
        except Exception as e:
            logger.error(f"Error generating installation plan: {e}")
            return {
                "available": [],
                "unavailable": [],
                "upgradable": [],
                "installation_commands": []
            }

    def generate_config_restoration_plan(self, backup_file: str) -> Dict[str, Any]:
        """Generate a configuration file restoration plan without executing it
        
        Args:
            backup_file: Path to the backup file
            
        Returns:
            Dict containing restoration plan details
        """
        logger.info(f"Generating config restoration plan from {backup_file}")
        
        try:
            # Check if file exists
            if not os.path.exists(backup_file):
                logger.error(f"Backup file not found: {backup_file}")
                return {
                    "restorable": [],
                    "problematic": [],
                    "commands": []
                }
                
            # Load backup file
            with open(backup_file, 'r') as f:
                backup_data = json.load(f)
                
            # Get config files
            config_files = backup_data.get("config_files", [])
            if not config_files:
                logger.warning("No configuration files found in backup")
                return {
                    "restorable": [],
                    "problematic": [],
                    "commands": []
                }
                
            logger.info(f"Found {len(config_files)} configuration files to analyze")
            
            # Categorize config files
            restorable_configs = []
            problematic_configs = []
            restoration_commands = []
            
            # Check each config file
            for cfg in config_files:
                path = cfg.get("path", "")
                
                # Skip certain problematic files by default
                if self._is_problematic_config(path):
                    cfg["issue"] = "Potentially problematic configuration (permission issues, hardware-specific, etc.)"
                    problematic_configs.append(cfg)
                    continue
                
                # Check if target directory exists and is writable
                target_dir = os.path.dirname(os.path.expanduser(path))
                if not os.path.exists(target_dir):
                    # Directory doesn't exist
                    cfg["issue"] = f"Target directory does not exist: {target_dir}"
                    problematic_configs.append(cfg)
                    restoration_commands.append(f"mkdir -p {target_dir}")
                elif not os.access(target_dir, os.W_OK):
                    # Directory exists but is not writable
                    cfg["issue"] = f"Target directory not writable: {target_dir}"
                    problematic_configs.append(cfg)
                    restoration_commands.append(f"sudo chmod u+w {target_dir}")
                else:
                    # Directory exists and is writable
                    restorable_configs.append(cfg)
                    
                    # Add to restoration commands (would just be a copy operation in reality)
                    restoration_commands.append(f"cp {cfg.get('source_path', 'backup/' + path)} {path}")
            
            # Create and return the plan
            plan = {
                "restorable": restorable_configs,
                "problematic": problematic_configs,
                "commands": restoration_commands
            }
            
            return plan
            
        except Exception as e:
            logger.error(f"Error generating config restoration plan: {e}")
            return {
                "restorable": [],
                "problematic": [],
                "commands": []
            }
    
    def _is_problematic_config(self, path: str) -> bool:
        """Check if a config file path might be problematic to restore
        
        Args:
            path: Path to check
            
        Returns:
            True if potentially problematic, False otherwise
        """
        # List of potentially problematic paths or patterns
        problematic_patterns = [
            # Hardware-specific configs
            "/etc/X11/xorg.conf",
            "/etc/modprobe.d/",
            # System-critical configs that should be handled carefully
            "/etc/fstab",
            "/etc/crypttab",
            "/etc/shadow",
            "/etc/passwd",
            # Permission-sensitive files
            "/.ssh/id_",
            "/.gnupg/",
            # Cache files that shouldn't be restored
            "/.cache/",
        ]
        
        # Check if path matches any problematic pattern
        for pattern in problematic_patterns:
            if pattern in path:
                return True
                
        return False

    def execute_installation_plan(self, backup_file: str, version_policy: str = 'prefer-newer', 
                                 allow_downgrade: bool = False) -> bool:
        """Execute package installation plan from backup
        
        Args:
            backup_file: Path to the backup file
            version_policy: Policy for version selection
            allow_downgrade: Whether to allow downgrading packages
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if file exists
            if not os.path.exists(backup_file):
                logger.error(f"Backup file not found: {backup_file}")
                return False
                
            # Load backup file
            with open(backup_file, 'r') as f:
                backup_data = json.load(f)
                
            # Get manually installed packages only
            packages = [p for p in backup_data.get("packages", []) 
                        if p.get("manually_installed", False)]
                        
            if not packages:
                logger.warning("No manually installed packages found in backup")
                print("No manually installed packages found to install")
                return True
                
            logger.info(f"Found {len(packages)} manually installed packages to restore")
            print(f"Installing {len(packages)} manually installed packages...")
            
            # Group packages by manager for more efficient installation
            packages_by_manager = {}
            for pkg in packages:
                manager = pkg.get("source", "unknown")
                if manager not in packages_by_manager:
                    packages_by_manager[manager] = []
                packages_by_manager[manager].append(pkg)
                
            # Install packages for each manager
            for manager_name, pkgs in packages_by_manager.items():
                # Skip unknown package managers
                if manager_name == "unknown":
                    continue
                    
                # Find matching package manager
                manager = None
                for pm in self.package_managers:
                    if pm.name == manager_name:
                        manager = pm
                        break
                        
                if not manager:
                    logger.warning(f"Package manager '{manager_name}' not available on this system")
                    print(f"Package manager '{manager_name}' not available - skipping {len(pkgs)} packages")
                    continue
                    
                logger.info(f"Installing {len(pkgs)} packages with {manager_name}")
                print(f"\nInstalling {len(pkgs)} packages with {manager_name}...")
                
                success_count = 0
                for i, pkg in enumerate(pkgs):
                    name = pkg.get("name", "")
                    version = pkg.get("version", "")
                    
                    progress = (i + 1) / len(pkgs) * 100
                    print(f"\r  Progress: {i+1}/{len(pkgs)} ({progress:.1f}%)   ", end="", flush=True)
                    
                    # Skip if already installed with same or newer version
                    current_version = manager.get_installed_version(name)
                    if current_version:
                        if version_policy == 'prefer-newer' and current_version >= version:
                            logger.info(f"Package {name} already installed with version {current_version}")
                            success_count += 1
                            continue
                        elif version_policy == 'prefer-same' and current_version == version:
                            logger.info(f"Package {name} already installed with exact version {version}")
                            success_count += 1
                            continue
                        elif version_policy == 'always-newest':
                            # Check if a newer version is available
                            latest = manager.get_latest_version(name)
                            if latest and latest > version:
                                version = latest
                                
                    # Install the package
                    if version and version_policy == 'exact':
                        # Try to install the exact version
                        if manager.is_version_available(name, version):
                            success = manager.install_package(name, version)
                        else:
                            logger.warning(f"Exact version {version} not available for {name}")
                            success = False
                    else:
                        # Install latest available version
                        success = manager.install_package(name)
                        
                    if success:
                        success_count += 1
                        logger.info(f"Installed {name}")
                    else:
                        logger.error(f"Failed to install {name}")
                        
                print(f"\r  Installed {success_count}/{len(pkgs)} packages                ")
                
            logger.info("Package installation completed")
            print("\nPackage installation completed")
            return True
            
        except Exception as e:
            logger.error(f"Error executing installation plan: {e}")
            return False
            
    def execute_config_restoration(self, backup_file: str, transform_paths: bool = True,
                                  preview_only: bool = False, restore_fstab: bool = True,
                                  preview_fstab: bool = False, exclude_paths: List[str] = None) -> bool:
        """Execute configuration file restoration from backup
        
        Args:
            backup_file: Path to the backup file
            transform_paths: Whether to transform paths for the current system
            preview_only: Whether to only preview transformations without applying
            restore_fstab: Whether to restore portable fstab entries
            preview_fstab: Whether to only preview fstab changes
            exclude_paths: List of paths to exclude from restoration
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if file exists
            if not os.path.exists(backup_file):
                logger.error(f"Backup file not found: {backup_file}")
                return False
                
            # Load backup file
            with open(backup_file, 'r') as f:
                backup_data = json.load(f)
                
            # Get config files
            config_files = backup_data.get("config_files", [])
            if not config_files:
                logger.warning("No configuration files found in backup")
                return False
                
            logger.info(f"Found {len(config_files)} configuration files to restore")
            print(f"Restoring {len(config_files)} configuration files...")
            
            # If transforming paths, set up the source system variables
            if transform_paths:
                source_vars = backup_data.get("system_variables", {})
                if source_vars:
                    # Create a SystemVariables instance from the backup
                    from .utils.sysvar import SystemVariables
                    source_sysvar = SystemVariables.from_dict(source_vars)
                    
                    # Log the mappings
                    logger.info(f"Path transformations:")
                    logger.info(f"  Source username: {source_vars.get('username')} -> {self.system_variables.username}")
                    logger.info(f"  Source hostname: {source_vars.get('hostname')} -> {self.system_variables.hostname}")
                    logger.info(f"  Source home dir: {source_vars.get('home_dir')} -> {self.system_variables.home_dir}")
                else:
                    transform_paths = False
                    logger.warning("No system variables found in backup, path transformation disabled")
                    
            # Process fstab entries if needed
            if restore_fstab or preview_fstab:
                # Look for portable fstab config
                fstab_config = None
                for cfg in config_files:
                    if cfg.get("path") == "/etc/fstab.portable" and "fstab_data" in cfg:
                        fstab_config = cfg
                        break
                        
                if fstab_config and "fstab_data" in fstab_config:
                    fstab_data = fstab_config.get("fstab_data", {})
                    portable_entries = fstab_data.get("portable_entries", [])
                    
                    if portable_entries:
                        logger.info(f"Found {len(portable_entries)} portable fstab entries")
                        print(f"\nFound {len(portable_entries)} portable fstab entries")
                        
                        if preview_fstab:
                            print("\nPortable fstab entries (preview only):")
                            for entry in portable_entries:
                                print(f"  {entry}")
                        elif restore_fstab:
                            # Add portable entries to current fstab
                            try:
                                # First check if entries already exist
                                with open("/etc/fstab", 'r') as f:
                                    current_fstab = f.read()
                                    
                                # Add entries that don't already exist
                                entries_to_add = []
                                for entry in portable_entries:
                                    if entry not in current_fstab:
                                        entries_to_add.append(entry)
                                
                                if entries_to_add:
                                    # Make backup of current fstab
                                    backup_path = "/etc/fstab.migrator.bak"
                                    shutil.copy2("/etc/fstab", backup_path)
                                    
                                    # Append entries
                                    with open("/etc/fstab", 'a') as f:
                                        f.write("\n# Added by Migrator restoration\n")
                                        for entry in entries_to_add:
                                            f.write(f"{entry}\n")
                                            
                                    print(f"Added {len(entries_to_add)} portable fstab entries")
                                    print(f"Original fstab backed up to {backup_path}")
                                else:
                                    print("All portable fstab entries already exist in current fstab")
                            except Exception as e:
                                logger.error(f"Error restoring fstab entries: {e}")
                                print(f"Error restoring fstab entries: {str(e)}")
                else:
                    logger.info("No portable fstab entries found in backup")
            
            # Filter out excluded paths
            if exclude_paths:
                original_count = len(config_files)
                filtered_config_files = []
                
                for cfg in config_files:
                    path = cfg.get("path", "")
                    should_exclude = False
                    
                    for exclude_pattern in exclude_paths:
                        if fnmatch.fnmatch(path, exclude_pattern):
                            logger.info(f"Excluding high-risk config file: {path}")
                            should_exclude = True
                            break
                    
                    if not should_exclude:
                        filtered_config_files.append(cfg)
                
                excluded_count = original_count - len(filtered_config_files)
                if excluded_count > 0:
                    print(f"\nExcluded {excluded_count} high-risk configuration files based on user preferences")
                    config_files = filtered_config_files
            
            # Restore configuration files
            configs_dir = os.path.join(os.path.dirname(backup_file), "config_files")
            transformed_count = 0
            restored_count = 0
            
            if os.path.exists(configs_dir):
                for cfg in config_files:
                    path = cfg.get("path", "")
                    category = cfg.get("category", "")
                    
                    # Skip special cases
                    if path == "/etc/fstab.portable":
                        continue
                        
                    # Check if file exists in backup
                    source_path = os.path.join(configs_dir, path.lstrip("/"))
                    if not os.path.exists(source_path):
                        logger.warning(f"Config file not found in backup: {path}")
                        continue
                        
                    # Check if paths need to be transformed
                    if transform_paths and category in ['user_config', 'desktop_config']:
                        if preview_only:
                            # Just show preview of transformations
                            try:
                                with open(source_path, 'r') as f:
                                    content = f.read()
                                    
                                # Count replacements without modifying
                                from .utils.sysvar import count_replacements
                                num_replacements = count_replacements(source_sysvar, content)
                                
                                if num_replacements > 0:
                                    transformed_count += 1
                                    print(f"Would transform {num_replacements} paths in {path}")
                            except Exception as e:
                                logger.error(f"Error analyzing {path}: {e}")
                        else:
                            # Transform and restore
                            try:
                                # Create target directory if needed
                                target_dir = os.path.dirname(path)
                                os.makedirs(target_dir, exist_ok=True)
                                
                                # Read source file
                                with open(source_path, 'r') as f:
                                    content = f.read()
                                    
                                # Transform paths
                                from .utils.sysvar import transform_content
                                new_content, num_replacements = transform_content(source_sysvar, content)
                                
                                if num_replacements > 0:
                                    transformed_count += 1
                                    logger.info(f"Transformed {num_replacements} paths in {path}")
                                    
                                # Write to target path
                                with open(path, 'w') as f:
                                    f.write(new_content)
                                    
                                restored_count += 1
                                logger.info(f"Restored config file: {path}")
                            except Exception as e:
                                logger.error(f"Error restoring {path}: {e}")
                    else:
                        # Direct restoration without transformation
                        try:
                            # Create target directory if needed
                            target_dir = os.path.dirname(path)
                            os.makedirs(target_dir, exist_ok=True)
                            
                            # Copy file
                            shutil.copy2(source_path, path)
                            
                            restored_count += 1
                            logger.info(f"Restored config file: {path}")
                        except Exception as e:
                            logger.error(f"Error restoring {path}: {e}")
                
                if preview_only and transformed_count > 0:
                    print(f"\nWould transform paths in {transformed_count} config files")
                    print("No files were modified (preview mode)")
                elif transform_paths:
                    print(f"\nTransformed paths in {transformed_count} config files")
                    
                print(f"Restored {restored_count} configuration files")
            else:
                logger.warning(f"Config files directory not found: {configs_dir}")
                print(f"Config files directory not found: {configs_dir}")
                print("Configuration files were loaded into state but not copied to system")
            
            logger.info("Configuration restoration completed")
            return True
            
        except Exception as e:
            logger.error(f"Error executing config restoration: {e}")
            return False
    
    def generate_dry_run_report(self, backup_file: str, version_policy: str = 'prefer-newer',
                               allow_downgrade: bool = False, transform_paths: bool = True) -> Dict[str, Any]:
        """Generate a dry run report for restore operation
        
        Args:
            backup_file: Path to the backup file
            version_policy: Policy for version selection
            allow_downgrade: Whether to allow downgrading packages
            transform_paths: Whether to transform paths
            
        Returns:
            Dictionary with report information
        """
        report = {
            "packages": {
                "to_install": 0,
                "unavailable": 0,
                "installation_commands": []
            },
            "config_files": {
                "to_restore": 0,
                "conflicts": 0,
                "paths": []
            },
            "path_transformations": {},
            "fstab_entries": [],
            "repositories": {
                "to_restore": 0,
                "compatibility_issues": 0,
                "repos": []
            },
            "conflicts": []
        }
        
        try:
            # Check if file exists
            if not os.path.exists(backup_file):
                logger.error(f"Backup file not found: {backup_file}")
                return report
                
            # Load backup file
            with open(backup_file, 'r') as f:
                backup_data = json.load(f)
                
            # Get metadata
            metadata = backup_data.get("backup_metadata", {})
            source_distro = metadata.get("distro_name", "Unknown")
            source_distro_id = metadata.get("distro_id", "unknown")
            source_hostname = metadata.get("hostname", "unknown")
            backup_version = metadata.get("backup_version", "1.0")
            
            # Check compatibility with current system
            if source_distro_id != self.distro_info.id:
                report["conflicts"].append({
                    "type": "system_compatibility",
                    "name": "Distribution mismatch",
                    "source": source_distro,
                    "target": self.distro_info.name,
                    "reason": f"Backup is from {source_distro}, but current system is {self.distro_info.name}"
                })
                
            # Get manually installed packages only
            packages = [p for p in backup_data.get("packages", []) 
                        if p.get("manually_installed", False)]
                        
            report["packages"]["total"] = len(packages)
            
            # Check each package
            for pkg in packages:
                name = pkg.get("name", "")
                version = pkg.get("version", "")
                source = pkg.get("source", "unknown")
                
                # Find matching package manager
                manager = None
                for pm in self.package_managers:
                    if pm.name == source:
                        manager = pm
                        break
                        
                if not manager:
                    report["conflicts"].append({
                        "type": "package_manager_unavailable",
                        "name": source,
                        "reason": f"Package manager '{source}' not available on this system"
                    })
                    continue
                    
                # Check if package is available
                if not manager.is_package_available(name):
                    report["packages"]["unavailable"] += 1
                    report["conflicts"].append({
                        "type": "package_unavailable",
                        "name": name,
                        "source": source,
                        "reason": f"Package '{name}' not available in current repositories"
                    })
                    continue
                    
                # Check for version issues
                current_version = manager.get_installed_version(name)
                if current_version:
                    if version_policy == 'exact' and current_version != version:
                        # Check if exact version is available
                        if not manager.is_version_available(name, version):
                            report["conflicts"].append({
                                "type": "version_unavailable",
                                "name": name,
                                "source": source,
                                "backup_version": version,
                                "available_version": current_version,
                                "reason": f"Exact version {version} not available for {name}"
                            })
                            
                    elif current_version > version and not allow_downgrade:
                        report["conflicts"].append({
                            "type": "version_downgrade_required",
                            "name": name,
                            "source": source,
                            "backup_version": version,
                            "available_version": current_version,
                            "reason": f"Would require downgrade from {current_version} to {version}"
                        })
                else:
                    # Package not installed, add to install list
                    report["packages"]["to_install"] += 1
                    report["packages"]["installation_commands"].append(
                        f"Install {name} ({source}) version {version}"
                    )
                    
            # Check configuration files
            config_files = backup_data.get("config_files", [])
            report["config_files"]["total"] = len(config_files)
            
            for cfg in config_files:
                path = cfg.get("path", "")
                report["config_files"]["to_restore"] += 1
                report["config_files"]["paths"].append(path)
                
                # Check if file exists and would be overwritten
                if os.path.exists(path):
                    report["config_files"]["conflicts"] += 1
                    report["conflicts"].append({
                        "type": "config_conflict",
                        "path": path,
                        "status": "File already exists and would be overwritten"
                    })
                    
            # If transforming paths, check path transformations
            if transform_paths:
                source_vars = backup_data.get("system_variables", {})
                if source_vars:
                    report["path_transformations"] = {
                        source_vars.get("username", ""): self.system_variables.username,
                        source_vars.get("hostname", ""): self.system_variables.hostname,
                        source_vars.get("home_dir", ""): self.system_variables.home_dir
                    }
                    
            # Check fstab entries
            for cfg in config_files:
                if cfg.get("path") == "/etc/fstab.portable" and "fstab_data" in cfg:
                    fstab_data = cfg.get("fstab_data", {})
                    portable_entries = fstab_data.get("portable_entries", [])
                    
                    if portable_entries:
                        report["fstab_entries"] = portable_entries
                        
                        # Check for conflicts with current fstab
                        try:
                            with open("/etc/fstab", 'r') as f:
                                current_fstab = f.read()
                                
                            for entry in portable_entries:
                                if entry in current_fstab:
                                    report["conflicts"].append({
                                        "type": "fstab_conflict",
                                        "entry": entry,
                                        "status": "Entry already exists in fstab"
                                    })
                        except Exception:
                            pass
                            
            # Check repositories
            repos_info = backup_data.get("repositories", {})
            repositories = repos_info.get("repositories", [])
            if repositories:
                report["repositories"]["total"] = len(repositories)
                
                # Check repository compatibility
                repo_manager = RepositoryManager()
                compatibility_issues = repo_manager.check_compatibility(repos_info)
                
                report["repositories"]["to_restore"] = len(repositories) - len(compatibility_issues)
                report["repositories"]["compatibility_issues"] = len(compatibility_issues)
                
                for issue in compatibility_issues:
                    report["conflicts"].append({
                        "type": "repository_compatibility",
                        "name": issue["name"],
                        "repo_type": issue["repo_type"],
                        "distro_type": issue["distro_type"],
                        "reason": issue["issue"]
                    })
                    
                for repo in repositories:
                    report["repositories"]["repos"].append({
                        "name": repo.get("name", ""),
                        "type": repo.get("repo_type", ""),
                        "distro": repo.get("distro_type", "")
                    })
                    
            return report
                
        except Exception as e:
            logger.error(f"Error generating dry run report: {e}")
            return report

    def scan_repo_sources(self) -> Dict[str, Any]:
        """Scan the system for software repository sources
        
        Returns:
            Dictionary of repository information
        """
        logger.info("Scanning for software repositories...")
        
        try:
            # Initialize the repository manager
            repo_manager = RepositoryManager()
            
            # Scan for repositories
            repos = repo_manager.scan_repositories()
            
            # Convert repositories to a dictionary for serialization
            repo_dict = {
                "repositories": [repo.to_dict() for repo in repos],
                "distro_id": self.distro_info.id.lower(),
                "distro_name": self.distro_info.name,
                "distro_version": self.distro_info.version
            }
            
            logger.info(f"Found {len(repos)} repository sources")
            return repo_dict
        except Exception as e:
            logger.error(f"Error scanning repositories: {e}")
            return {"repositories": [], "error": str(e)}

    def compare_with_backup(self, backup_file: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Compare the current system with a backup file

        Args:
            backup_file: Path to the backup file to compare with

        Returns:
            Tuple containing (added_packages, removed_packages, added_configs, removed_configs)
        """
        logger.info(f"Comparing current system with backup {backup_file}")
        
        # Ensure we have current system data by checking if required attributes exist
        if not hasattr(self, 'installed_packages') or not hasattr(self, 'config_files'):
            logger.info("No current system scan data found, running a scan first...")
            print("No current system scan data found, running a scan first...")
            # Run a scan to initialize necessary attributes
            self.update_system_state()
        
        # Load backup data
        try:
            with open(backup_file, 'r') as f:
                backup_data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading backup file: {e}")
            raise ValueError(f"Could not load backup file: {e}")
            
        # Extract package and config data from backup
        backup_packages = backup_data.get('packages', [])
        backup_configs = backup_data.get('config_files', [])
        
        # Convert to sets of identifiers for efficient comparison
        # For packages, we create a set of (name, source) tuples
        current_pkg_ids = {(pkg.name, pkg.source) for pkg in self.installed_packages}
        backup_pkg_ids = {(pkg['name'], pkg['source']) for pkg in backup_packages}
        
        # For configs, we use the path as identifier
        current_cfg_paths = {cfg.path for cfg in self.config_files}
        backup_cfg_paths = {cfg['path'] for cfg in backup_configs}
        
        # Find differences
        added_pkg_ids = current_pkg_ids - backup_pkg_ids
        removed_pkg_ids = backup_pkg_ids - current_pkg_ids
        
        added_cfg_paths = current_cfg_paths - backup_cfg_paths
        removed_cfg_paths = backup_cfg_paths - current_cfg_paths
        
        # Prepare detailed result lists
        added_packages = []
        for pkg in self.installed_packages:
            if (pkg.name, pkg.source) in added_pkg_ids:
                added_packages.append(pkg.to_dict())
                
        removed_packages = []
        for pkg in backup_packages:
            if (pkg['name'], pkg['source']) in removed_pkg_ids:
                removed_packages.append(pkg)
                
        added_configs = []
        for cfg in self.config_files:
            if cfg.path in added_cfg_paths:
                added_configs.append(cfg.to_dict())
                
        removed_configs = []
        for cfg in backup_configs:
            if cfg['path'] in removed_cfg_paths:
                removed_configs.append(cfg)
                
        logger.info(f"Found {len(added_packages)} added packages, {len(removed_packages)} removed packages")
        logger.info(f"Found {len(added_configs)} added config files, {len(removed_configs)} removed config files")
        
        return added_packages, removed_packages, added_configs, removed_configs

    def execute_routine_check(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Execute a routine check for changes since the last scan
        
        Returns:
            Tuple containing (changed_packages, changed_configs)
        """
        logger.info("Executing routine check for system changes")
        
        # Ensure we have current system data
        if not hasattr(self, 'installed_packages') or not hasattr(self, 'config_files') or not self.installed_packages:
            logger.info("No previous scan data found, running a scan first...")
            # Run a scan to initialize necessary attributes
            self.update_system_state()
            # If this is the first scan, there are no changes to report
            return [], []
            
        # Store the current packages and configs for comparison
        old_packages = self.installed_packages
        old_configs = self.config_files
        
        # Get the current packages and configs
        logger.info("Scanning for current system state...")
        current_packages = self.scan_packages()
        current_configs = self.scan_config_files()
        
        # Compare packages
        old_pkg_ids = {(pkg.name, pkg.source, pkg.version) for pkg in old_packages}
        current_pkg_ids = {(pkg.name, pkg.source, pkg.version) for pkg in current_packages}
        
        changed_pkg_tuples = current_pkg_ids.symmetric_difference(old_pkg_ids)
        
        # Prepare detailed package changes
        changed_packages = []
        for pkg in current_packages:
            if (pkg.name, pkg.source, pkg.version) in changed_pkg_tuples:
                # Check if it's an upgrade
                old_versions = [old_pkg.version for old_pkg in old_packages 
                               if old_pkg.name == pkg.name and old_pkg.source == pkg.source]
                
                if old_versions:
                    status = "upgraded" if pkg.version > old_versions[0] else "downgraded"
                    old_version = old_versions[0]
                else:
                    status = "added"
                    old_version = ""
                
                changed_packages.append({
                    "name": pkg.name,
                    "source": pkg.source,
                    "version": pkg.version,
                    "old_version": old_version,
                    "status": status
                })
        
        # Add removed packages
        for pkg in old_packages:
            if all((current_pkg.name != pkg.name or current_pkg.source != pkg.source)
                  for current_pkg in current_packages):
                changed_packages.append({
                    "name": pkg.name,
                    "source": pkg.source,
                    "version": pkg.version,
                    "status": "removed"
                })
        
        # Compare config files
        changed_configs = []
        for cfg in current_configs:
            # Find matching config in old_configs
            old_cfg = next((old for old in old_configs if old.path == cfg.path), None)
            
            if old_cfg is None:
                # New config file
                changed_configs.append({
                    "path": cfg.path,
                    "status": "added"
                })
            elif cfg.checksum != old_cfg.checksum:
                # Modified config file
                changed_configs.append({
                    "path": cfg.path,
                    "status": "modified"
                })
        
        # Look for removed config files
        for old_cfg in old_configs:
            if all(current_cfg.path != old_cfg.path for current_cfg in current_configs):
                changed_configs.append({
                    "path": old_cfg.path,
                    "status": "removed"
                })
        
        # Update the stored state with the current values
        self.installed_packages = current_packages
        self.config_files = current_configs
        self._save_state()
        
        logger.info(f"Routine check complete: found {len(changed_packages)} changed packages and {len(changed_configs)} changed configs")
        
        return changed_packages, changed_configs
