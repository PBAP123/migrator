#!/usr/bin/env python3
"""
Snap package manager implementation
"""

import subprocess
import json
import os
import logging
import shutil
from typing import List, Optional, Dict, Any
from datetime import datetime

from .base import PackageManager, Package

logger = logging.getLogger(__name__)

class SnapPackageManager(PackageManager):
    """Package manager for Snap packages"""
    
    def __init__(self):
        super().__init__('snap')
        # Log whether snap is available
        logger.info(f"Snap package manager available: {self.available}")
    
    def _check_available(self) -> bool:
        """Override the base method to check if snap is available"""
        if not shutil.which('snap'):
            logger.warning("Snap command not found in PATH")
            return False
        
        try:
            # Use a specific snap command instead of --version which isn't supported
            cmd = ['snap', 'version']
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            available = result.returncode == 0
            logger.info(f"Snap availability check: {available}, returncode={result.returncode}")
            if not available:
                logger.warning(f"Snap version check failed: {result.stderr.strip()}")
            return available
        except Exception as e:
            logger.error(f"Error checking snap availability: {e}")
            return False
    
    def list_installed_packages(self, test_mode=False) -> List[Package]:
        """List all installed snap packages
        
        Args:
            test_mode: If True, only process a small number of packages for testing
        """
        if not shutil.which('snap'):
            logger.warning("Snap command not found in PATH")
            print("Snap command not found - skipping snap package scan")
            return []
        
        packages = []
        
        try:
            # First check if snap is working properly
            print("Checking for installed Snap packages...")
            check_cmd = ['snap', 'list']
            check_result = subprocess.run(check_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            
            if check_result.returncode != 0:
                logger.warning(f"Error checking snap: {check_result.stderr.strip()}")
                print(f"Error accessing snap: {check_result.stderr.strip()}")
                return []
                
            # If the output has less than 2 lines (just header or empty), no snaps are installed
            snap_lines = check_result.stdout.strip().splitlines()
            if len(snap_lines) < 2:
                logger.info("No Snap packages installed (beyond core system snaps)")
                print("No user-installed Snap packages found")
                return []
                
            # Get regular list output first (more reliable than JSON)
            snaps = []
            for line in snap_lines[1:]:  # Skip header
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[0]
                    version = parts[1]
                    # Skip core system snaps
                    if name not in ['core', 'core18', 'core20', 'core22', 'snapd']:
                        snaps.append({
                            'name': name,
                            'version': version
                        })
            
            # Limit in test mode
            if test_mode and snaps:
                snaps = snaps[:5]  # Only process 5 snaps in test mode
                logger.info("Running in TEST MODE - only processing 5 Snap packages")
                
            total_pkgs = len(snaps)
            logger.info(f"Found {total_pkgs} Snap packages to process")
            print(f"Processing {total_pkgs} Snap packages...")
            
            # Process each snap
            for i, snap in enumerate(snaps):
                name = snap.get('name', '')
                version = snap.get('version', '')
                
                progress_pct = ((i + 1) / total_pkgs) * 100
                print(f"\rProcessing Snap packages: {i+1}/{total_pkgs} ({progress_pct:.1f}%)      ", end="", flush=True)
                
                # Basic info only for faster processing
                packages.append(Package(
                    name=name,
                    version=version,
                    source='snap',
                    manually_installed=True  # All snaps are manually installed
                ))
            
            if total_pkgs > 0:
                print(f"\rCompleted processing {total_pkgs} Snap packages             ")
            
            return packages
            
        except subprocess.SubprocessError as e:
            logger.error(f"Error listing installed snap packages: {e}")
            print(f"Failed to list Snap packages: {str(e)}")
            return []
    
    def is_package_available(self, package_name: str) -> bool:
        """Check if a snap package is available in the snap store"""
        if not self.available:
            logger.warning(f"Snap package manager not available, cannot check if {package_name} is available")
            return False
        
        try:
            # First check if package is already installed - in that case it's obviously available
            installed_cmd = ['snap', 'list', package_name]
            installed_result = subprocess.run(
                installed_cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True, 
                check=False
            )
            
            if installed_result.returncode == 0:
                logger.info(f"Snap package {package_name} is already installed, considering available")
                return True
            
            # If not installed, check in the store
            cmd = ['snap', 'info', package_name]
            logger.debug(f"Checking snap package availability: {' '.join(cmd)}")
            result = subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True, 
                check=False,
                timeout=10  # Add timeout to prevent hanging
            )
            
            # Log full output for debugging
            if result.returncode != 0:
                logger.warning(f"Snap info failed for {package_name}: {result.stderr.strip()}")
                
            # Check if output contains expected store information
            has_publisher = 'publisher:' in result.stdout
            is_available = result.returncode == 0 and has_publisher
            
            if not is_available:
                # Detailed debug info
                if result.returncode == 0 and not has_publisher:
                    logger.warning(f"Snap package {package_name} found but missing publisher info. Output: {result.stdout[:200]}...")
                else:
                    logger.warning(f"Snap package {package_name} not available. Return code: {result.returncode}")
                    
            return is_available
            
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout checking snap package availability for {package_name}")
            return False
        except subprocess.SubprocessError as e:
            logger.error(f"Error checking snap package availability: {e}")
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
        
    def plan_installation(self, packages: List[Dict[str, Any]]) -> Dict[str, List]:
        """Plan snap package installation without executing it
        
        Args:
            packages: List of package dictionaries from backup
            
        Returns:
            Dict with available, unavailable, upgradable packages and installation commands
        """
        available_packages = []
        unavailable_packages = []
        upgradable_packages = []
        commands = []
        
        if not self.available:
            # If snap is not available, all packages are considered unavailable
            logger.warning(f"Snap package manager not available, marking all {len(packages)} packages as unavailable")
            for pkg in packages:
                pkg_copy = pkg.copy()
                pkg_copy['reason'] = 'Snap package manager not available on this system'
                unavailable_packages.append(pkg_copy)
            
            # Add a descriptive comment
            commands.append("# SNAP: Package manager not available on this system")
            
            return {
                "available": available_packages,
                "unavailable": unavailable_packages,
                "upgradable": upgradable_packages,
                "installation_commands": commands
            }
            
        # Add header for snap packages
        commands.append(f"# SNAP: Found {len(packages)} packages to install")
        
        # Check if snapd service is running
        try:
            status_cmd = ['systemctl', 'is-active', 'snapd.service']
            status_result = subprocess.run(status_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            if status_result.returncode != 0:
                commands.append("# SNAP: Warning - snapd service is not running, you may need to start it:")
                commands.append("# SNAP: sudo systemctl start snapd.service")
        except Exception:
            # If we can't check, just ignore
            pass
        
        # Get list of already installed packages to save time
        installed_packages = {}
        try:
            list_cmd = ['snap', 'list']
            list_result = subprocess.run(list_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            if list_result.returncode == 0:
                # Parse the output, skipping header
                for line in list_result.stdout.strip().splitlines()[1:]:
                    parts = line.split()
                    if len(parts) >= 2:
                        name = parts[0]
                        version = parts[1]
                        installed_packages[name] = version
                logger.info(f"Found {len(installed_packages)} already installed snap packages")
        except Exception as e:
            logger.warning(f"Failed to get installed snap packages: {e}")
        
        # Process each package
        total = len(packages)
        logger.info(f"Planning installation for {total} snap packages")
        
        for i, pkg in enumerate(packages):
            name = pkg.get('name', '')
            version = pkg.get('version', '')
            
            # Skip if name is missing
            if not name:
                continue
            
            # First check if already installed
            if name in installed_packages:
                installed_version = installed_packages[name]
                logger.info(f"Snap package {name} is already installed (version {installed_version})")
                
                if version and version != installed_version:
                    # Version mismatch between backup and installed
                    pkg_copy = pkg.copy()
                    pkg_copy['installed_version'] = installed_version
                    upgradable_packages.append(pkg_copy)
                    commands.append(f"# SNAP: Package '{name}' already installed but version differs: wanted {version}, have {installed_version}")
                else:
                    # Same version or no specific version requested
                    available_packages.append(pkg)
                    commands.append(f"# SNAP: Package '{name}' already installed with correct version")
                
                # Skip to next package
                continue
            
            # Check if package is available in the snap store
            if not self.is_package_available(name):
                pkg_copy = pkg.copy()
                pkg_copy['reason'] = 'Package not available in Snap store'
                unavailable_packages.append(pkg_copy)
                commands.append(f"# SNAP: Warning - Package '{name}' not found in Snap store")
                continue
                
            # For Snap, we have two version-like concepts:
            # 1. Channel (stable, edge, etc.)
            # 2. Revision number
            
            # Determine if the version looks like a channel or revision
            is_revision = version and version.isdigit()
            is_channel = version and not is_revision
            
            # Check if specific version/channel/revision is available
            if version and self.is_version_available(name, version):
                # Exact version/channel/revision is available
                available_packages.append(pkg)
                if is_revision:
                    commands.append(f"snap install {name} --revision {version}  # SNAP: Exact revision requested")
                elif is_channel:
                    commands.append(f"snap install {name} --channel {version}  # SNAP: Specific channel requested")
                else:
                    commands.append(f"snap install {name}  # SNAP: Will install version {version}")
            else:
                # No specific version requested or requested version not available
                # For Snap, we typically just install the latest version from the stable channel
                latest = self.get_latest_version(name)
                
                if latest:
                    pkg_copy = pkg.copy()
                    pkg_copy['available_version'] = latest
                    if version:
                        # Requested specific version but using a different one
                        upgradable_packages.append(pkg_copy)
                        commands.append(f"snap install {name}  # SNAP: Requested: {version}, Available: latest ({latest})")
                    else:
                        # No specific version requested
                        available_packages.append(pkg_copy)
                        commands.append(f"snap install {name}  # SNAP: Will install version {latest}")
                else:
                    # Package exists but no version info available - rare for Snap
                    pkg_copy = pkg.copy()
                    pkg_copy['reason'] = 'Package exists but version information unavailable'
                    unavailable_packages.append(pkg_copy)
                    commands.append(f"# SNAP: Warning - Package '{name}' exists but version information is unavailable")
            
            # Report progress periodically
            if (i+1) % 5 == 0 or (i+1) == total:
                logger.info(f"Planning progress: {i+1}/{total} snap packages processed")
        
        # Add accurate summaries at the top of the commands
        avail_count = len(available_packages)
        unavail_count = len(unavailable_packages)
        upgrade_count = len(upgradable_packages)
        
        # Insert summaries at the beginning
        if avail_count > 0:
            commands.insert(1, f"# SNAP: {avail_count} packages available out of {total} requested")
        
        if unavail_count > 0:
            commands.insert(2 if avail_count > 0 else 1, f"# SNAP: Warning - {unavail_count} packages are unavailable")
            
        if upgrade_count > 0:
            commands.insert(3 if avail_count > 0 or unavail_count > 0 else 1, 
                          f"# SNAP: Note - {upgrade_count} packages have version differences")
        
        logger.info(f"Plan for snap: {avail_count} available, {unavail_count} unavailable, {upgrade_count} with version differences")
        
        return {
            "available": available_packages,
            "unavailable": unavailable_packages,
            "upgradable": upgradable_packages,
            "installation_commands": commands
        } 