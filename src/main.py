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
from package_managers.factory import PackageManagerFactory
from package_managers.base import Package, PackageManager

# Import config tracker modules
from config_trackers.base import ConfigFile
from config_trackers.system_config import SystemConfigTracker
from config_trackers.user_config import UserConfigTracker
from config_trackers.desktop_environment import DesktopEnvironmentTracker

# Import utilities
from utils.distro import get_distro_info, DistroInfo

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
    
    def scan_packages(self) -> List[Package]:
        """Scan the system for installed packages"""
        all_packages = []
        
        logger.info("Scanning for installed packages...")
        
        for pm in self.package_managers:
            try:
                logger.info(f"Scanning packages with {pm.name}...")
                packages = pm.list_installed_packages()
                all_packages.extend(packages)
                logger.info(f"Found {len(packages)} packages with {pm.name}")
            except Exception as e:
                logger.error(f"Error scanning packages with {pm.name}: {e}")
        
        logger.info(f"Total packages found: {len(all_packages)}")
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
        
        logger.info("Scanning for system configuration files...")
        system_configs = self.system_config_tracker.find_config_files()
        all_configs.extend(system_configs)
        logger.info(f"Found {len(system_configs)} system configuration files")
        
        logger.info("Scanning for user configuration files...")
        user_configs = self.user_config_tracker.find_config_files()
        all_configs.extend(user_configs)
        logger.info(f"Found {len(user_configs)} user configuration files")
        
        if include_desktop:
            logger.info("Scanning for desktop environment configuration files...")
            de_configs = self.desktop_env_tracker.find_config_files(
                include_desktop=include_desktop,
                desktop_environments=desktop_environments,
                exclude_desktop=exclude_desktop
            )
            all_configs.extend(de_configs)
            logger.info(f"Found {len(de_configs)} desktop environment configuration files")
        
        logger.info(f"Total configuration files found: {len(all_configs)}")
        return all_configs
    
    def update_system_state(self, include_desktop=True, 
                           desktop_environments=None, exclude_desktop=None) -> None:
        """Update the system state with current packages and configuration files
        
        Args:
            include_desktop: Whether to include desktop environment configs
            desktop_environments: List of specific desktop environments to include
            exclude_desktop: List of desktop environments to exclude
        """
        # Scan packages
        packages = self.scan_packages()
        self.state["packages"] = [pkg.to_dict() for pkg in packages]
        
        # Scan configuration files
        config_files = self.scan_config_files(
            include_desktop=include_desktop,
            desktop_environments=desktop_environments,
            exclude_desktop=exclude_desktop
        )
        self.state["config_files"] = [cfg.to_dict() for cfg in config_files]
        
        # Save state
        self._save_state()
    
    def backup_state(self, backup_dir: str) -> str:
        """Backup the current system state to a specified directory"""
        os.makedirs(backup_dir, exist_ok=True)
        
        # Create a timestamped backup file
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"migrator_backup_{timestamp}.json")
        
        try:
            # Write the state file
            with open(backup_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            
            logger.info(f"Backed up system state to {backup_file}")
            
            # Create a directory for config files
            configs_dir = os.path.join(backup_dir, "config_files")
            os.makedirs(configs_dir, exist_ok=True)
            
            # Copy all config files
            config_count = 0
            for config in self.state.get("config_files", []):
                path = config["path"]
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
                    except Exception as e:
                        logger.error(f"Error copying config file {path}: {e}")
            
            logger.info(f"Backed up {config_count} configuration files to {configs_dir}")
            
            return backup_file
        except IOError as e:
            logger.error(f"Error backing up system state: {e}")
            return ""
    
    def restore_from_backup(self, backup_file: str, execute_plan: bool = False) -> bool:
        """Restore system state from a backup file
        
        Args:
            backup_file: Path to the backup file
            execute_plan: Whether to automatically execute the installation plan
                          and restore configuration files
        
        Returns:
            Whether the operation was successful
        """
        if not os.path.exists(backup_file):
            logger.error(f"Backup file doesn't exist: {backup_file}")
            return False
        
        try:
            with open(backup_file, 'r') as f:
                backup_state = json.load(f)
            
            # Validate backup state format
            required_keys = ["system_info", "packages", "config_files"]
            if not all(key in backup_state for key in required_keys):
                logger.error(f"Invalid backup file format: {backup_file}")
                return False
            
            # Store backup as current state
            self.state = backup_state
            
            # Save to state file
            self._save_state()
            
            logger.info(f"Restored system state from {backup_file}")
            
            # Execute installation plan if requested
            if execute_plan:
                logger.info("Executing installation plan...")
                self.execute_installation_plan(backup_file)
                
                logger.info("Restoring configuration files...")
                self.execute_config_restoration(backup_file)
            
            return True
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error restoring from backup: {e}")
            return False
    
    def execute_installation_plan(self, backup_file: str, 
                                 version_policy: str = 'prefer-newer',
                                 allow_downgrade: bool = False) -> bool:
        """Execute the installation plan to install packages from a backup
        
        Args:
            backup_file: Path to the backup file
            version_policy: How to handle package versions:
                - 'exact': Only install the exact versions from backup
                - 'prefer-same': Try to match backup versions, accept newer if needed
                - 'prefer-newer': Prefer newer versions, accept downgrades if needed
                - 'always-newest': Always use the latest available version
            allow_downgrade: Whether to allow downgrading packages
        
        Returns:
            Whether the operation was successful
        """
        if not os.path.exists(backup_file):
            logger.error(f"Backup file doesn't exist: {backup_file}")
            return False
        
        try:
            # Generate the installation plan
            plan = self.generate_installation_plan(
                backup_file, 
                version_policy=version_policy,
                allow_downgrade=allow_downgrade
            )
            
            if not plan["installation_commands"]:
                logger.warning("No packages to install from backup")
                return True
            
            # Log version mismatches
            if plan["version_mismatches"]:
                logger.info(f"Found {len(plan['version_mismatches'])} package version differences:")
                for mismatch in plan["version_mismatches"]:
                    logger.info(f"  - {mismatch['name']}: backup={mismatch['backup_version']}, available={mismatch['available_version']}")
            
            # Execute each installation command
            for cmd in plan["installation_commands"]:
                logger.info(f"Executing: {cmd}")
                try:
                    result = subprocess.run(
                        cmd, 
                        shell=True, 
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    logger.info(f"Command completed successfully: {cmd}")
                    logger.debug(f"Output: {result.stdout}")
                except subprocess.CalledProcessError as e:
                    logger.error(f"Command failed: {cmd}")
                    logger.error(f"Error: {e.stderr}")
                    # Continue with other commands even if one fails
            
            logger.info(f"Executed {len(plan['installation_commands'])} installation commands")
            
            # Report on unavailable packages
            if plan["unavailable"]:
                logger.warning(f"{len(plan['unavailable'])} packages could not be installed:")
                for pkg in plan["unavailable"]:
                    reason = pkg.get('reason', 'Not available')
                    logger.warning(f"  - {pkg['name']} (source: {pkg['source']}, reason: {reason})")
            
            return True
        except Exception as e:
            logger.error(f"Error executing installation plan: {e}")
            return False
    
    def execute_config_restoration(self, backup_file: str) -> bool:
        """Restore configuration files from a backup
        
        Args:
            backup_file: Path to the backup file
        
        Returns:
            Whether the operation was successful
        """
        if not os.path.exists(backup_file):
            logger.error(f"Backup file doesn't exist: {backup_file}")
            return False
        
        try:
            with open(backup_file, 'r') as f:
                backup_state = json.load(f)
            
            # Get backup directory
            backup_dir = os.path.dirname(os.path.abspath(backup_file))
            configs_dir = os.path.join(backup_dir, "config_files")
            
            # Check if config directory exists
            if not os.path.exists(configs_dir):
                # Create directory structure for config files
                os.makedirs(configs_dir, exist_ok=True)
                
                # Export the config files from the backup
                for config in backup_state.get("config_files", []):
                    path = config["path"]
                    relative_path = path.lstrip("/")
                    if os.path.exists(path):
                        target_dir = os.path.join(configs_dir, os.path.dirname(relative_path))
                        os.makedirs(target_dir, exist_ok=True)
                        target_path = os.path.join(configs_dir, relative_path)
                        try:
                            shutil.copy2(path, target_path)
                            logger.info(f"Exported config file: {path} -> {target_path}")
                        except Exception as e:
                            logger.error(f"Failed to export config file {path}: {e}")
            
            # Generate restoration plan
            plan = self.generate_config_restoration_plan(backup_file)
            
            # Track results
            success_count = 0
            failed_count = 0
            
            # Restore each file
            for config in plan["restorable"]:
                path = config["path"]
                relative_path = path.lstrip("/")
                source_path = os.path.join(configs_dir, relative_path)
                
                # Create target directory if needed
                target_dir = os.path.dirname(path)
                os.makedirs(target_dir, exist_ok=True)
                
                try:
                    # Check if we have the config file in our backup
                    if os.path.exists(source_path):
                        # Copy the file to its original location
                        shutil.copy2(source_path, path)
                        logger.info(f"Restored config file: {source_path} -> {path}")
                        success_count += 1
                    else:
                        logger.warning(f"Config file not available in backup: {path}")
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Failed to restore config file {path}: {e}")
                    failed_count += 1
            
            # Report problematic configs
            if plan["problematic"]:
                logger.warning(f"{len(plan['problematic'])} config files have conflicts:")
                for config in plan["problematic"]:
                    logger.warning(f"  - {config['path']} (status: {config.get('status', 'unknown')})")
            
            # Log summary
            logger.info(f"Config restoration summary: {success_count} restored, {failed_count} failed, {len(plan['problematic'])} conflicts")
            
            return True
        except Exception as e:
            logger.error(f"Error executing config restoration: {e}")
            return False
    
    def compare_with_backup(self, backup_file: str) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict]]:
        """Compare current system state with a backup
        
        Returns:
            Tuple of (added_packages, removed_packages, added_configs, removed_configs)
        """
        if not os.path.exists(backup_file):
            logger.error(f"Backup file doesn't exist: {backup_file}")
            return [], [], [], []
        
        try:
            with open(backup_file, 'r') as f:
                backup_state = json.load(f)
            
            # Get current packages and configs
            current_packages = self.scan_packages()
            current_configs = self.scan_config_files()
            
            # Convert to comparable dictionaries
            current_pkgs_dict = {f"{pkg.name}:{pkg.source}": pkg.to_dict() for pkg in current_packages}
            backup_pkgs_dict = {f"{pkg['name']}:{pkg['source']}": pkg for pkg in backup_state.get("packages", [])}
            
            current_cfgs_dict = {cfg.path: cfg.to_dict() for cfg in current_configs}
            backup_cfgs_dict = {cfg['path']: cfg for cfg in backup_state.get("config_files", [])}
            
            # Find additions and removals
            added_packages = [pkg for key, pkg in current_pkgs_dict.items() if key not in backup_pkgs_dict]
            removed_packages = [pkg for key, pkg in backup_pkgs_dict.items() if key not in current_pkgs_dict]
            
            added_configs = [cfg for key, cfg in current_cfgs_dict.items() if key not in backup_cfgs_dict]
            removed_configs = [cfg for key, cfg in backup_cfgs_dict.items() if key not in current_cfgs_dict]
            
            return added_packages, removed_packages, added_configs, removed_configs
            
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error comparing with backup: {e}")
            return [], [], [], []
    
    def generate_installation_plan(self, backup_file: str, 
                                version_policy: str = 'prefer-newer',
                                allow_downgrade: bool = False) -> Dict[str, Any]:
        """Generate a plan for installing packages from a backup file
        
        Args:
            backup_file: Path to the backup file
            version_policy: How to handle package versions:
                - 'exact': Only install the exact versions from backup
                - 'prefer-same': Try to match backup versions, accept newer if needed
                - 'prefer-newer': Prefer newer versions, accept downgrades if needed
                - 'always-newest': Always use the latest available version
            allow_downgrade: Whether to allow downgrading packages
        
        Returns a dictionary with package installation information:
        {
            "available": list of packages available for direct installation,
            "upgradable": list of packages with newer versions available,
            "unavailable": list of packages not available on this system,
            "installation_commands": list of commands that would install the packages,
            "version_mismatches": list of packages with version mismatches
        }
        """
        if not os.path.exists(backup_file):
            logger.error(f"Backup file doesn't exist: {backup_file}")
            return {"available": [], "upgradable": [], "unavailable": [], 
                    "installation_commands": [], "version_mismatches": []}
        
        try:
            with open(backup_file, 'r') as f:
                backup_state = json.load(f)
            
            installation_plan = {
                "available": [],
                "upgradable": [],
                "unavailable": [],
                "installation_commands": [],
                "version_mismatches": []
            }
            
            # Get backup packages
            backup_packages = [Package.from_dict(pkg) for pkg in backup_state.get("packages", [])]
            
            # Filter for manually installed packages only
            manual_packages = [pkg for pkg in backup_packages if pkg.manually_installed]
            
            # Check availability of each package on current system
            for pkg in manual_packages:
                # Find appropriate package manager for this package
                pm = self._get_package_manager_for_source(pkg.source)
                
                if not pm:
                    installation_plan["unavailable"].append(pkg.to_dict())
                    continue
                
                if pm.is_package_available(pkg.name):
                    # Check if the version matches or is newer
                    latest_version = pm.get_latest_version(pkg.name)
                    
                    # Get currently installed version if any
                    current_version = pm.get_installed_version(pkg.name)
                    
                    # Skip if already installed with same or appropriate version based on policy
                    if current_version:
                        if (version_policy == 'exact' and current_version == pkg.version) or \
                           (version_policy == 'prefer-same' and current_version >= pkg.version) or \
                           (version_policy == 'prefer-newer' and current_version >= pkg.version) or \
                           (version_policy == 'always-newest' and current_version >= latest_version):
                            # Already have appropriate version installed
                            continue
                    
                    # Check version policy
                    pkg_dict = pkg.to_dict()
                    
                    if latest_version and latest_version != pkg.version:
                        pkg_dict["latest_version"] = latest_version
                        
                        # Record the version mismatch
                        mismatch = {
                            "name": pkg.name,
                            "source": pkg.source,
                            "backup_version": pkg.version,
                            "available_version": latest_version
                        }
                        installation_plan["version_mismatches"].append(mismatch)
                        
                        # Handle based on version policy
                        if version_policy == 'exact':
                            # Only accept exact version matches
                            if pm.is_version_available(pkg.name, pkg.version):
                                pkg_dict["install_version"] = pkg.version
                                installation_plan["available"].append(pkg_dict)
                            else:
                                pkg_dict["reason"] = "Exact version not available"
                                installation_plan["unavailable"].append(pkg_dict)
                        
                        elif version_policy == 'prefer-same':
                            # Try exact version, but accept newer if needed
                            if pm.is_version_available(pkg.name, pkg.version):
                                pkg_dict["install_version"] = pkg.version
                                installation_plan["available"].append(pkg_dict)
                            else:
                                pkg_dict["install_version"] = latest_version
                                installation_plan["upgradable"].append(pkg_dict)
                        
                        elif version_policy == 'prefer-newer':
                            # Prefer newer, accept downgrade if allowed
                            if latest_version > pkg.version:
                                pkg_dict["install_version"] = latest_version
                                installation_plan["upgradable"].append(pkg_dict)
                            else:
                                # Need to downgrade
                                if allow_downgrade:
                                    pkg_dict["install_version"] = pkg.version
                                    installation_plan["available"].append(pkg_dict)
                                else:
                                    pkg_dict["reason"] = "Would require downgrade"
                                    installation_plan["unavailable"].append(pkg_dict)
                        
                        elif version_policy == 'always-newest':
                            # Always use latest version
                            pkg_dict["install_version"] = latest_version
                            installation_plan["upgradable"].append(pkg_dict)
                    
                    else:
                        # Version matches or no version info available
                        pkg_dict["install_version"] = pkg.version
                        installation_plan["available"].append(pkg_dict)
                
                else:
                    installation_plan["unavailable"].append(pkg.to_dict())
            
            # Generate installation commands
            for pm in self.package_managers:
                # Get packages for this package manager
                pm_available = [pkg for pkg in installation_plan["available"] 
                                if pkg["source"] == pm.name]
                pm_upgradable = [pkg for pkg in installation_plan["upgradable"] 
                                if pkg["source"] == pm.name]
                
                # Only generate commands if we have packages to install
                if pm_available or pm_upgradable:
                    if pm.name == "apt":
                        # For APT, we can specify versions
                        pkg_specs = []
                        for pkg in pm_available + pm_upgradable:
                            if version_policy == 'exact' or \
                               (version_policy == 'prefer-same' and 'install_version' in pkg and pkg['install_version'] == pkg['version']):
                                # Specify exact version
                                pkg_specs.append(f"{pkg['name']}={pkg['install_version']}")
                            else:
                                # Just the package name for latest
                                pkg_specs.append(pkg['name'])
                        
                        if pkg_specs:
                            cmd = f"sudo apt install -y {' '.join(pkg_specs)}"
                            installation_plan["installation_commands"].append(cmd)
                    
                    elif pm.name == "snap":
                        for pkg in pm_available + pm_upgradable:
                            if version_policy == 'exact' and 'install_version' in pkg:
                                cmd = f"sudo snap install {pkg['name']} --revision={pkg['install_version']}"
                            else:
                                cmd = f"sudo snap install {pkg['name']}"
                            installation_plan["installation_commands"].append(cmd)
                    
                    elif pm.name == "flatpak":
                        for pkg in pm_available + pm_upgradable:
                            cmd = f"flatpak install -y {pkg['name']}"
                            installation_plan["installation_commands"].append(cmd)
                    
                    # Add other package managers as needed
            
            return installation_plan
            
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error generating installation plan: {e}")
            return {"available": [], "upgradable": [], "unavailable": [], 
                    "installation_commands": [], "version_mismatches": []}
    
    def _get_package_manager_for_source(self, source: str) -> Optional[PackageManager]:
        """Get the appropriate package manager for a given source"""
        for pm in self.package_managers:
            if pm.name == source:
                return pm
        return None
    
    def generate_config_restoration_plan(self, backup_file: str) -> Dict[str, Any]:
        """Generate a plan for restoring configuration files from a backup
        
        Returns a dictionary with restoration information:
        {
            "restorable": list of config files that can be restored,
            "problematic": list of config files that might have conflicts,
            "commands": list of commands to restore configs
        }
        """
        if not os.path.exists(backup_file):
            logger.error(f"Backup file doesn't exist: {backup_file}")
            return {"restorable": [], "problematic": [], "commands": []}
        
        try:
            with open(backup_file, 'r') as f:
                backup_state = json.load(f)
            
            restoration_plan = {
                "restorable": [],
                "problematic": [],
                "commands": []
            }
            
            # Get current configs for comparison
            current_configs = self.scan_config_files()
            current_paths = {cfg.path for cfg in current_configs}
            
            # Create ConfigFile objects from backup
            backup_configs = [ConfigFile.from_dict(cfg) for cfg in backup_state.get("config_files", [])]
            
            for cfg in backup_configs:
                # Check if file exists on current system
                if cfg.path in current_paths:
                    # File exists - check if it's different
                    current_cfg = next((c for c in current_configs if c.path == cfg.path), None)
                    if current_cfg and current_cfg.checksum != cfg.checksum:
                        cfg_dict = cfg.to_dict()
                        cfg_dict["status"] = "modified"
                        restoration_plan["problematic"].append(cfg_dict)
                    else:
                        # File exists and is identical - no need to restore
                        pass
                else:
                    # File doesn't exist - can be restored
                    restoration_plan["restorable"].append(cfg.to_dict())
            
            # Generate commands to restore configs
            # In a real implementation, we would include the config file content in the backup
            # and create commands to restore those files
            for cfg in restoration_plan["restorable"]:
                # Create directory if needed
                dir_path = os.path.dirname(cfg["path"])
                restoration_plan["commands"].append(f"mkdir -p '{dir_path}'")
                
                # For now, just print a message since we don't have the content
                restoration_plan["commands"].append(
                    f"# Config file '{cfg['path']}' needs to be restored"
                )
            
            return restoration_plan
            
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error generating config restoration plan: {e}")
            return {"restorable": [], "problematic": [], "commands": []}
    
    def execute_routine_check(self) -> Tuple[List[Dict], List[Dict]]:
        """Execute a routine check for changes since the last saved state
        
        Returns:
            Tuple of (changed_packages, changed_configs)
        """
        # Load current packages and config files
        current_packages = self.scan_packages()
        current_configs = self.scan_config_files()
        
        # Convert current packages to dictionary for easy lookup
        current_pkgs_dict = {f"{pkg.name}:{pkg.source}": pkg.to_dict() for pkg in current_packages}
        
        # Get saved packages from state
        saved_pkgs_dict = {f"{pkg['name']}:{pkg['source']}": pkg for pkg in self.state.get("packages", [])}
        
        # Find changes
        added_packages = [pkg for key, pkg in current_pkgs_dict.items() if key not in saved_pkgs_dict]
        removed_packages = [pkg for key, pkg in saved_pkgs_dict.items() if key not in current_pkgs_dict]
        
        # Check for changed configs
        changed_configs = []
        for config in current_configs:
            config_dict = config.to_dict()
            
            # Find saved config
            saved_config = next((cfg for cfg in self.state.get("config_files", []) 
                                if cfg["path"] == config_dict["path"]), None)
            
            if saved_config and saved_config["checksum"] != config_dict["checksum"]:
                config_dict["status"] = "changed"
                changed_configs.append(config_dict)
        
        # Also detect removed configs
        current_cfg_paths = {cfg.path for cfg in current_configs}
        for saved_cfg in self.state.get("config_files", []):
            if saved_cfg["path"] not in current_cfg_paths:
                saved_cfg["status"] = "removed"
                changed_configs.append(saved_cfg)
        
        # Update state with current information
        self.update_system_state()
        
        return added_packages + removed_packages, changed_configs
