#!/usr/bin/env python3
"""
Snap package manager implementation
"""

import subprocess
import json
import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from .base import PackageManager, Package

logger = logging.getLogger(__name__)

class SnapPackageManager(PackageManager):
    """Package manager for Snap packages"""
    
    def __init__(self):
        super().__init__('snap')
    
    def list_installed_packages(self) -> List[Package]:
        """List all installed snap packages"""
        if not self.available:
            logger.warning("Snap package manager not available")
            return []
        
        packages = []
        
        try:
            # Get list of installed snaps in JSON format
            cmd = ['snap', 'list', '--json']
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            
            # Parse JSON output
            snaps_data = json.loads(result.stdout)
            
            for snap in snaps_data:
                name = snap.get('name', '')
                version = snap.get('version', '')
                
                # Get more detailed info
                pkg_info = self.get_package_info(name)
                if pkg_info:
                    packages.append(pkg_info)
                else:
                    # Basic info only
                    packages.append(Package(
                        name=name,
                        version=version,
                        source='snap'
                    ))
            
            return packages
            
        except (subprocess.SubprocessError, json.JSONDecodeError) as e:
            logger.error(f"Error listing installed snap packages: {e}")
            return []
    
    def is_package_available(self, package_name: str) -> bool:
        """Check if a snap package is available in the snap store"""
        if not self.available:
            return False
        
        try:
            cmd = ['snap', 'info', package_name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            return result.returncode == 0 and 'publisher:' in result.stdout
        except subprocess.SubprocessError:
            return False
    
    def get_package_info(self, package_name: str) -> Optional[Package]:
        """Get detailed information about a snap package"""
        if not self.available:
            return None
        
        try:
            # Get snap info
            cmd = ['snap', 'info', package_name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            
            # Parse snap info output
            info_lines = result.stdout.splitlines()
            
            # Initialize with defaults
            version = ''
            description = ''
            install_date_str = ''
            
            for line in info_lines:
                line = line.strip()
                
                if line.startswith('installed:'):
                    version = line.split('installed:', 1)[1].strip()
                    # Some versions include additional info in parentheses
                    if ' (' in version:
                        version = version.split(' (', 1)[0].strip()
                
                elif line.startswith('summary:'):
                    description = line.split('summary:', 1)[1].strip()
                
                elif line.startswith('refreshed:'):
                    install_date_str = line.split('refreshed:', 1)[1].strip()
            
            # Parse install date (format: 2023-01-01T00:00:00+00:00)
            install_date = None
            if install_date_str:
                try:
                    # Remove timezone info for simplicity
                    install_date_str = install_date_str.split('+', 1)[0].split('Z', 1)[0]
                    install_date = datetime.fromisoformat(install_date_str)
                except (ValueError, IndexError) as e:
                    logger.warning(f"Could not parse snap install date: {install_date_str}, error: {e}")
            
            # All snap packages are considered manually installed
            return Package(
                name=package_name,
                version=version,
                description=description,
                source='snap',
                install_date=install_date,
                manually_installed=True  # Snaps are typically installed manually
            )
            
        except subprocess.SubprocessError as e:
            logger.error(f"Error getting snap package info for {package_name}: {e}")
            return None
    
    def get_installed_version(self, package_name: str) -> Optional[str]:
        """Get the installed version of a snap package"""
        if not self.available:
            return None
        
        try:
            cmd = ['snap', 'list', package_name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            
            if result.returncode != 0:
                return None
            
            # Parse output (skipping header line)
            lines = result.stdout.strip().splitlines()
            if len(lines) < 2:
                return None
            
            parts = lines[1].split()
            if len(parts) >= 2:
                return parts[1]
            
            return None
            
        except subprocess.SubprocessError:
            return None
    
    def get_latest_version(self, package_name: str) -> Optional[str]:
        """Get the latest available version of a snap package"""
        if not self.available:
            return None
        
        try:
            cmd = ['snap', 'info', package_name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            
            # Look for the latest/stable or latest/current line
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith('latest/stable:') or line.startswith('latest/current:'):
                    version = line.split(':', 1)[1].strip()
                    # Some versions include additional info in parentheses
                    if ' (' in version:
                        version = version.split(' (', 1)[0].strip()
                    return version
            
            return None
            
        except subprocess.SubprocessError:
            return None
    
    def is_version_available(self, package_name: str, version: str) -> bool:
        """Check if a specific version of a snap package is available
        
        For snaps, we check if the revision or channel is available
        """
        if not self.available:
            return False
        
        try:
            cmd = ['snap', 'info', package_name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            
            # Snap doesn't directly expose available versions in the same way as apt
            # We'll check if this looks like a revision number or a channel name
            if version.isdigit():
                # This looks like a revision number, check for it
                revision_pattern = f"rev {version}"
                return revision_pattern in result.stdout
            else:
                # Treat as a channel name
                channel_pattern = f"{version}:"
                for line in result.stdout.splitlines():
                    if line.strip().startswith(channel_pattern):
                        return True
            
            return False
            
        except subprocess.SubprocessError:
            return False
    
    def install_package(self, package_name: str, version: Optional[str] = None) -> bool:
        """Install a snap package
        
        Args:
            package_name: The name of the package to install
            version: The version to install, which can be:
                     - A channel name (e.g., "stable", "edge")
                     - A revision number (e.g., "12345")
                     
        Note: For snaps, we always use the latest version in a given channel
        unless a specific revision is requested.
        """
        if not self.available:
            logger.error("Snap package manager not available")
            return False
        
        try:
            cmd = ['snap', 'install', package_name]
            
            if version:
                # Check if this looks like a revision number
                if version.isdigit():
                    cmd.extend(['--revision', version])
                else:
                    # Treat as a channel name
                    cmd.extend(['--channel', version])
            
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return result.returncode == 0
            
        except subprocess.SubprocessError as e:
            logger.error(f"Error installing snap package {package_name}: {e}")
            return False
    
    def is_user_installed(self, package_name: str) -> bool:
        """Check if a snap package was explicitly installed by the user"""
        # All snap packages are considered user-installed
        return self.get_installed_version(package_name) is not None 