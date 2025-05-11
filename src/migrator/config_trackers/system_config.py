#!/usr/bin/env python3
"""
System configuration tracker for system-wide configuration files
"""

import os
import glob
import logging
import json
from typing import List, Dict, Any, Optional, Set

from .base import ConfigTracker, ConfigFile
from ..utils.fstab import FstabManager, FstabEntry

logger = logging.getLogger(__name__)

class SystemConfigTracker(ConfigTracker):
    """Track system-wide configuration files (e.g., in /etc)"""
    
    def __init__(self):
        super().__init__("system_config")
        self.tracked_files: Dict[str, ConfigFile] = {}
        self.fstab_manager = None  # Will be initialized during scanning
        self.portable_fstab_entries = []  # Store portable fstab entries
        self.include_fstab_portability = True  # Flag to control fstab processing
        
        self.config_dirs = [
            "/etc",
            "/usr/local/etc"
        ]
        # Common important configuration files to track
        self.important_configs = [
            # Network configuration
            "/etc/hosts",
            "/etc/hostname",
            "/etc/network/interfaces",
            "/etc/NetworkManager/system-connections/*",
            "/etc/netplan/*.yaml",
            
            # System configuration
            "/etc/fstab",
            "/etc/default/grub",
            "/etc/apt/sources.list",
            "/etc/apt/sources.list.d/*.list",
            "/etc/yum.repos.d/*.repo",
            "/etc/pacman.conf",
            "/etc/pacman.d/mirrorlist",
            
            # Service configuration
            "/etc/systemd/system/*.service",
            "/etc/systemd/user/*.service",
            
            # Security and users
            "/etc/sudoers",
            "/etc/sudoers.d/*",
            "/etc/group",
            "/etc/passwd",
            "/etc/shadow",
            
            # Shell and environment
            "/etc/environment",
            "/etc/profile",
            "/etc/bash.bashrc",
            "/etc/profile.d/*.sh",
            
            # Display and graphics
            "/etc/X11/xorg.conf",
            "/etc/X11/xorg.conf.d/*.conf",
            
            # Software configuration
            "/etc/default/*",
            "/etc/cron.d/*",
            "/etc/cron.daily/*",
            "/etc/cron.hourly/*",
            "/etc/cron.weekly/*",
            "/etc/cron.monthly/*"
        ]
    
    def find_config_files(self) -> List[ConfigFile]:
        """Find system configuration files to track"""
        config_files = []
        
        # Handle fstab specially for portability
        if self.include_fstab_portability:
            self._process_fstab_entries()
        else:
            logger.info("Skipping portable fstab entries detection (disabled by user)")
            
            # Instead, track the regular fstab file
            fstab_path = "/etc/fstab"
            if os.path.isfile(fstab_path) and os.access(fstab_path, os.R_OK):
                # Create config file object
                config = self._create_config_file(fstab_path)
                if config:
                    config_files.append(config)
                    self.tracked_files[config.path] = config
        
        # Expand globs and find files
        for pattern in self.important_configs:
            # Skip fstab as we handle it separately
            if pattern == "/etc/fstab":
                continue
                
            if "*" in pattern:
                try:
                    for file_path in glob.glob(pattern):
                        if os.path.isfile(file_path) and os.access(file_path, os.R_OK):
                            # Create config file object
                            config = self._create_config_file(file_path)
                            if config:
                                config_files.append(config)
                                self.tracked_files[config.path] = config
                except Exception as e:
                    logger.error(f"Error processing glob pattern {pattern}: {e}")
            else:
                if os.path.isfile(pattern) and os.access(pattern, os.R_OK):
                    # Create config file object
                    config = self._create_config_file(pattern)
                    if config:
                        config_files.append(config)
                        self.tracked_files[config.path] = config
        
        return config_files
    
    def _process_fstab_entries(self) -> None:
        """Process fstab to extract portable entries"""
        fstab_path = "/etc/fstab"
        
        # Check if fstab exists and is readable
        if os.path.exists(fstab_path) and os.access(fstab_path, os.R_OK):
            self.fstab_manager = FstabManager(fstab_path)
            
            # Get portable entries
            self.portable_fstab_entries = self.fstab_manager.get_portable_entries()
            
            if self.portable_fstab_entries:
                # Create a special config file for portable fstab entries
                portable_fstab_path = "/etc/fstab.portable"
                
                # Store portable entries in a special format
                portable_content = "\n".join([entry.to_line() for entry in self.portable_fstab_entries])
                portable_fstab_data = {
                    "fstab_path": fstab_path,
                    "portable_entries": [entry.to_dict() for entry in self.portable_fstab_entries]
                }
                
                # Create a temporary file to get a checksum
                temp_path = os.path.join('/tmp', 'migrator_fstab_portable')
                with open(temp_path, 'w') as f:
                    json.dump(portable_fstab_data, f, indent=2)
                
                # Create a ConfigFile object with special metadata
                config = ConfigFile(
                    path=portable_fstab_path,  # Virtual path
                    description=f"Portable fstab entries ({len(self.portable_fstab_entries)} entries)",
                    category="fstab_portable",
                    is_system_config=True
                )
                
                # Set the content to the JSON data
                with open(temp_path, 'rb') as f:
                    file_contents = f.read()
                    config._calculate_checksum_from_data(file_contents)
                
                # Add to tracked files
                self.tracked_files[portable_fstab_path] = config
                
                # Remove the temporary file
                try:
                    os.unlink(temp_path)
                except:
                    pass
                
                logger.info(f"Processed fstab and found {len(self.portable_fstab_entries)} portable entries")
            else:
                logger.info("No portable fstab entries found")
        else:
            logger.info(f"Fstab file {fstab_path} does not exist or is not readable")
    
    def get_portable_fstab_entries(self) -> List[FstabEntry]:
        """Get the portable fstab entries"""
        return self.portable_fstab_entries
    
    def get_fstab_manager(self) -> Optional[FstabManager]:
        """Get the fstab manager"""
        return self.fstab_manager
    
    def has_portable_fstab_entries(self) -> bool:
        """Check if there are portable fstab entries"""
        return len(self.portable_fstab_entries) > 0
    
    def _create_config_file(self, path: str) -> Optional[ConfigFile]:
        """Create a ConfigFile object with appropriate metadata"""
        try:
            # Determine category based on path
            category = "system"
            if "network" in path.lower() or "NetworkManager" in path:
                category = "network"
            elif "apt" in path or "yum" in path or "pacman" in path:
                category = "package_manager"
            elif "systemd" in path or path.endswith(".service"):
                category = "service"
            elif "X11" in path or "xorg" in path:
                category = "display"
            elif "cron" in path:
                category = "scheduled_task"
            elif "sudoers" in path or "group" in path or "passwd" in path or "shadow" in path:
                category = "security"
            elif "profile" in path or "bash" in path or "environment" in path:
                category = "shell"
            
            # Generate a description
            description = f"System configuration file: {os.path.basename(path)}"
            
            return ConfigFile(
                path=path,
                description=description,
                category=category,
                is_system_config=True
            )
        except Exception as e:
            logger.error(f"Error creating config file for {path}: {e}")
            return None
    
    def get_config_file(self, path: str) -> Optional[ConfigFile]:
        """Get a specific configuration file by path"""
        path = os.path.abspath(os.path.expanduser(path))
        return self.tracked_files.get(path)
    
    def track_config_file(self, path: str, description: str = "", category: str = "") -> Optional[ConfigFile]:
        """Add a configuration file to be tracked"""
        path = os.path.abspath(os.path.expanduser(path))
        
        if not os.path.isfile(path):
            logger.error(f"Cannot track non-existent file: {path}")
            return None
        
        if not os.access(path, os.R_OK):
            logger.error(f"Cannot track unreadable file: {path}")
            return None
        
        # Check if it's a system file
        is_system_config = path.startswith("/etc") or path.startswith("/usr/local/etc")
        
        if not category:
            # Try to determine category based on path
            if "network" in path.lower() or "NetworkManager" in path:
                category = "network"
            elif "apt" in path or "yum" in path or "pacman" in path:
                category = "package_manager"
            elif "systemd" in path or path.endswith(".service"):
                category = "service"
            else:
                category = "system"
        
        if not description:
            description = f"System configuration file: {os.path.basename(path)}"
        
        config = ConfigFile(
            path=path,
            description=description,
            category=category,
            is_system_config=is_system_config
        )
        
        self.tracked_files[path] = config
        return config
    
    def stop_tracking_config_file(self, path: str) -> bool:
        """Stop tracking a configuration file"""
        path = os.path.abspath(os.path.expanduser(path))
        if path in self.tracked_files:
            del self.tracked_files[path]
            return True
        return False
    
    def get_changed_files(self) -> List[ConfigFile]:
        """Get list of tracked files that have changed since last check"""
        changed_files = []
        
        for path, config in self.tracked_files.items():
            if config.has_changed():
                changed_files.append(config)
        
        return changed_files
    
    def update_all(self) -> None:
        """Update checksums for all tracked files"""
        for config in self.tracked_files.values():
            config.update() 