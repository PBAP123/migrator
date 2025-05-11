#!/usr/bin/env python3
"""
System configuration tracker for system-wide configuration files
"""

import os
import glob
import logging
from typing import List, Dict, Any, Optional, Set

from .base import ConfigTracker, ConfigFile

logger = logging.getLogger(__name__)

class SystemConfigTracker(ConfigTracker):
    """Track system-wide configuration files (e.g., in /etc)"""
    
    def __init__(self):
        super().__init__("system_config")
        self.tracked_files: Dict[str, ConfigFile] = {}
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
        
        # Expand globs and find files
        for pattern in self.important_configs:
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