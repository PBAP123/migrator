#!/usr/bin/env python3
"""
DNF package manager implementation for RHEL-based systems (Fedora, CentOS, etc.)
"""

import subprocess
import re
import os
import logging
import json
import time
import multiprocessing
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from pathlib import Path
from functools import partial

from .base import PackageManager, Package

logger = logging.getLogger(__name__)

# Number of packages to process in each batch
BATCH_SIZE = 50
# Number of parallel processes to use (default to CPU count or 4, whichever is lower)
NUM_PROCESSES = min(multiprocessing.cpu_count(), 4)

class DnfPackageManager(PackageManager):
    """Package manager for DNF (Fedora, RHEL, CentOS, etc.)"""
    
    def __init__(self):
        super().__init__('dnf')
        self.rpm_path = '/usr/bin/rpm'
        self.dnf_path = '/usr/bin/dnf'
        
        # Check if we have sudo privileges
        self.has_sudo = self._check_sudo()
        
        # Handle timestamp ranges - platform specific maximum
        self.max_timestamp = 2147483647  # Default max for 32-bit systems
        # Check if we're on a 64-bit system and adjust accordingly
        import sys
        if sys.maxsize > 2**32:
            self.max_timestamp = 2524608000  # Max for 64-bit (~2050)
            
        # Initialize package availability cache
        self.availability_cache = {}
        self.cache_timestamp = 0
        self.cache_path = Path(os.path.expanduser("~/.cache/migrator/dnf_packages.json"))
        self._load_availability_cache()
        
        # Version cache to avoid redundant queries
        self.version_cache = {}
    
    def _check_sudo(self) -> bool:
        """Check if we have sudo privileges"""
        try:
            # Use dnf instead of sudo to avoid asking for password
            result = subprocess.run(['dnf', '--version'], 
                       stdout=subprocess.PIPE, 
                       stderr=subprocess.PIPE, 
                       check=False)
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def _safe_run_rpm_command(self, cmd, check=True, timeout=None):
        """Run a command safely, handling timeouts and command failures"""
        try:
            result = subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                check=check,
                timeout=timeout
            )
            return result
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {' '.join(cmd)}")
            logger.error(f"Error output: {e.stderr}")
            if check:
                raise
            
            # Create a dummy result object for non-checked calls
            class DummyResult:
                def __init__(self):
                    self.returncode = 1
                    self.stdout = ""
                    self.stderr = str(e)
                    
            return DummyResult()
        except subprocess.TimeoutExpired as e:
            logger.error(f"Command timed out after {timeout}s: {' '.join(cmd)}")
            
            # Create a dummy result object for timeout
            class DummyResult:
                def __init__(self):
                    self.returncode = 1
                    self.stdout = ""
                    self.stderr = f"Command timed out after {timeout}s"
                    
            return DummyResult()
    
    def _load_availability_cache(self):
        """Load package availability cache from file"""
        try:
            if self.cache_path.exists():
                with open(self.cache_path, 'r') as f:
                    cache_data = json.load(f)
                    self.availability_cache = cache_data.get('packages', {})
                    self.cache_timestamp = cache_data.get('timestamp', 0)
                    
                    # Check if cache is fresh (less than 1 hour old)
                    if time.time() - self.cache_timestamp > 3600:
                        logger.info("Package availability cache is older than 1 hour, will validate freshness")
                        self._check_cache_freshness()
                    else:
                        logger.info(f"Loaded availability cache with {len(self.availability_cache)} packages")
        except Exception as e:
            logger.warning(f"Could not load package availability cache: {e}")
            # Initialize empty cache
            self.availability_cache = {}
            self.cache_timestamp = 0
    
    def _save_availability_cache(self):
        """Save package availability cache to file"""
        try:
            # Create cache directory if it doesn't exist
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            cache_data = {
                'timestamp': time.time(),
                'packages': self.availability_cache
            }
            
            with open(self.cache_path, 'w') as f:
                json.dump(cache_data, f)
                
            logger.info(f"Saved availability cache with {len(self.availability_cache)} packages")
        except Exception as e:
            logger.warning(f"Could not save package availability cache: {e}")
    
    def _check_cache_freshness(self):
        """Check if the cache is still valid by checking DNF repository timestamp"""
        try:
            # Get timestamp of the DNF repository metadata
            cmd = [self.dnf_path, 'repoquery', '--refresh', '--refresh-timeout=1', '--cacheonly']
            result = self._safe_run_rpm_command(cmd, check=False)
            
            # If repoquery is successful with cacheonly, the cache is fresh enough
            if result.returncode == 0:
                # Update our cache timestamp but keep the data
                self.cache_timestamp = time.time()
                logger.info("Repository metadata is fresh, keeping package cache")
                return True
            
            # If repoquery fails, we need to update the repo data and invalidate our cache
            logger.info("Repository metadata needs update, clearing package cache")
            self.availability_cache = {}
            self.cache_timestamp = 0
            return False
            
        except Exception as e:
            logger.warning(f"Error checking cache freshness: {e}, clearing cache to be safe")
            self.availability_cache = {}
            self.cache_timestamp = 0
            return False
    
    def list_installed_packages(self) -> List[Package]:
        """List all packages installed via DNF/RPM"""
        packages = []
        invalid_timestamp_count = 0
        
        try:
            # Get list of installed packages with their versions
            cmd = [self.rpm_path, '-qa', '--queryformat', '%{NAME} %{VERSION}-%{RELEASE} %{SUMMARY}\\n']
            result = self._safe_run_rpm_command(cmd)
            
            # Parse rpm output
            for line in result.stdout.splitlines():
                parts = line.split(maxsplit=2)
                if len(parts) >= 2:
                    name = parts[0]
                    version = parts[1]
                    description = parts[2] if len(parts) > 2 else ""
                    
                    try:
                        # Check if it was manually installed
                        manually_installed = self.is_user_installed(name)
                        
                        # Get install date
                        install_date = self._get_install_date(name)
                        if install_date is None and name.startswith('kernel'):
                            # Only increment for kernel packages to avoid too much noise
                            invalid_timestamp_count += 1
                        
                        packages.append(Package(
                            name=name,
                            version=version,
                            description=description,
                            source='dnf',
                            install_date=install_date,
                            manually_installed=manually_installed
                        ))
                    except Exception as pkg_error:
                        # Log the error but continue processing other packages
                        logger.warning(f"Error processing package {name}: {pkg_error}")
                        # Still add the package with limited information
                        packages.append(Package(
                            name=name,
                            version=version,
                            description=description,
                            source='dnf',
                            install_date=None,
                            manually_installed=False
                        ))
            
            # Log summary of timestamp issues
            if invalid_timestamp_count > 0:
                logger.info(f"Found {invalid_timestamp_count} packages with invalid installation timestamps (mostly kernel packages)")
                print(f"Note: {invalid_timestamp_count} packages had invalid timestamps - using fallback data")
            
            return packages
        
        except subprocess.SubprocessError as e:
            logger.error(f"Error listing installed packages: {e}")
            return []
    
    def _get_install_date(self, package_name: str) -> Optional[datetime]:
        """Get the installation date of a package"""
        try:
            # Try to get install date using buildtime as fallback if installtime is invalid
            # (buildtime is typically more reliable)
            cmd = [self.rpm_path, '-q', '--queryformat', '%{INSTALLTIME}|%{BUILDTIME}', package_name]
            result = self._safe_run_rpm_command(cmd)
            
            # Parse timestamp - now potentially has both install and build time
            data = result.stdout.strip()
            
            if not data:
                return None
                
            # Try install time first, then build time as fallback
            timestamps = data.split('|')
            timestamp = timestamps[0]
            
            # If install time looks invalid but we have build time, use that instead
            if (not timestamp or not timestamp.isdigit() or len(timestamp) > 12) and len(timestamps) > 1 and timestamps[1].isdigit():
                timestamp = timestamps[1]
                logger.debug(f"Using build time instead of install time for package {package_name}")
            
            if timestamp and timestamp.isdigit():
                try:
                    # Handle timestamp out of range errors
                    timestamp_int = int(timestamp)
                    
                    # More thorough validation of timestamp
                    # Normal Unix timestamps are ~10 digits for recent dates
                    # Anything over 12 digits is definitely invalid
                    # Max realistic value: Jan 1, 2100 = 4102444800
                    if timestamp_int < 0 or timestamp_int > 4102444800 or len(timestamp) > 12:
                        logger.debug(f"Invalid timestamp for package {package_name}: {timestamp} (outside reasonable date range)")
                        return None
                    
                    return datetime.fromtimestamp(timestamp_int)
                except (ValueError, OverflowError, OSError) as e:
                    # This handles the "timestamp out of range for platform time_t" error
                    logger.debug(f"Error parsing timestamp for package {package_name}: {e}")
                    return None
            
            return None
        except subprocess.SubprocessError:
            return None
    
    def is_user_installed(self, package_name: str) -> bool:
        """Check if a package was explicitly installed by the user"""
        try:
            # In DNF, packages explicitly installed usually appear in the "install" transaction
            cmd = ['dnf', 'history', 'userinstalled']
            result = self._safe_run_rpm_command(cmd, check=False)
            
            if result.returncode != 0:
                return False
                
            return package_name in result.stdout
        except subprocess.SubprocessError:
            return False
    
    def is_package_available(self, package_name: str) -> bool:
        """Check if a package is available in the DNF repositories"""
        # Check cache first
        if package_name in self.availability_cache:
            return self.availability_cache[package_name]
            
        try:
            # Try common variations first
            variations = [package_name]
            
            # Special case for 7zip -> p7zip
            if package_name == '7zip':
                variations.append('p7zip')
                
            # Handle lib packages - check for -devel suffix variations
            if package_name.startswith('lib') and not package_name.endswith('-devel'):
                variations.append(f"{package_name}-devel")
                
            # Try python3- prefix
            if not package_name.startswith('python'):
                variations.append(f"python3-{package_name}")
                
            # First try using dnf list available which is more reliable
            cmd = [self.dnf_path, 'list', 'available', package_name]
            result = self._safe_run_rpm_command(cmd, check=False)
            
            if result.returncode == 0:
                # Parse the output to find matching packages
                for line in result.stdout.splitlines():
                    line = line.strip()
                    
                    # Skip metadata and header lines
                    if not line or line.startswith('Last metadata') or line.startswith('Available Packages'):
                        continue
                        
                    # Parse package line (format: name.arch  version  repo)
                    parts = line.split()
                    if len(parts) >= 2:
                        pkg_name_with_arch = parts[0]
                        # Split off architecture (e.g., firefox.x86_64 -> firefox)
                        pkg_name = pkg_name_with_arch.split('.')[0]
                        
                        if pkg_name.lower() == package_name.lower():
                            # Direct match
                            self.availability_cache[package_name] = True
                            logger.debug(f"Package {package_name} found available in repositories")
                            return True
            
            # If not found by direct check, try variations
            for variation in variations:
                if variation == package_name:
                    continue  # Skip the original name which we already checked
                    
                cmd = [self.dnf_path, 'list', 'available', variation]
                result = self._safe_run_rpm_command(cmd, check=False)
                
                if result.returncode == 0:
                    # Parse the output
                    for line in result.stdout.splitlines():
                        line = line.strip()
                        if not line or line.startswith('Last metadata') or line.startswith('Available Packages'):
                            continue
                            
                        parts = line.split()
                        if len(parts) >= 2:
                            pkg_name_with_arch = parts[0]
                            pkg_name = pkg_name_with_arch.split('.')[0]
                            
                            if pkg_name.lower() == variation.lower():
                                # Found a variation match
                                self.availability_cache[package_name] = True
                                self.availability_cache[variation] = True
                                logger.debug(f"Package {package_name} available as {variation}")
                                
                                # Periodically save the cache (every 50 new entries)
                                if len(self.availability_cache) % 50 == 0:
                                    self._save_availability_cache()
                                    
                                return True
            
            # Fall back to dnf info if list failed (some versions of DNF handle different commands better)
            for variation in variations:
                cmd = [self.dnf_path, 'info', variation]
                result = self._safe_run_rpm_command(cmd, check=False)
                
                if result.returncode == 0 and "Available Packages" in result.stdout:
                    # Cache both the original name and the variation as available
                    self.availability_cache[package_name] = True
                    self.availability_cache[variation] = True
                    logger.debug(f"Package {package_name} available via info command")
                    
                    # Periodically save the cache (every 50 new entries)
                    if len(self.availability_cache) % 50 == 0:
                        self._save_availability_cache()
                        
                    return True
            
            # If we get here, none of the variations were available
            self.availability_cache[package_name] = False
            logger.debug(f"Package {package_name} not available (checked all variations)")
            
            # Periodically save the cache (every 50 new entries)
            if len(self.availability_cache) % 50 == 0:
                self._save_availability_cache()
                
            return False
        except subprocess.SubprocessError as e:
            # On error, cache as not available
            logger.warning(f"Error checking availability for {package_name}: {e}")
            self.availability_cache[package_name] = False
            return False
    
    def get_package_info(self, package_name: str) -> Optional[Package]:
        """Get detailed information about a package"""
        try:
            # Check if installed first
            installed_version = self.get_installed_version(package_name)
            if not installed_version:
                return None
            
            # Get package details
            cmd = [self.rpm_path, '-qi', package_name]
            result = self._safe_run_rpm_command(cmd)
            
            # Parse rpm -qi output
            package_info = {}
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue
                    
                if ': ' in line:
                    key, value = line.split(': ', 1)
                    package_info[key.strip()] = value.strip()
            
            # Get install date
            install_date = self._get_install_date(package_name)
            
            # Get manual installation status
            manually_installed = self.is_user_installed(package_name)
            
            return Package(
                name=package_name,
                version=package_info.get('Version', ''),
                description=package_info.get('Summary', ''),
                source='dnf',
                install_date=install_date,
                manually_installed=manually_installed
            )
            
        except subprocess.SubprocessError as e:
            logger.error(f"Error getting package info for {package_name}: {e}")
            return None
    
    def get_installed_version(self, package_name: str) -> Optional[str]:
        """Get the installed version of a package"""
        try:
            cmd = [self.rpm_path, '-q', '--queryformat', '%{VERSION}-%{RELEASE}', package_name]
            result = self._safe_run_rpm_command(cmd)
            
            if result.returncode != 0 or not result.stdout.strip():
                return None
            
            return result.stdout.strip()
            
        except subprocess.SubprocessError:
            return None
    
    def get_latest_version(self, package_name: str) -> Optional[str]:
        """Get the latest available version of a package"""
        # Check cache first
        if package_name in self.version_cache:
            return self.version_cache[package_name]
            
        try:
            # Use DNF info to get the available version
            cmd = [self.dnf_path, 'info', package_name]
            result = self._safe_run_rpm_command(cmd, check=False)
            
            if result.returncode != 0:
                self.version_cache[package_name] = None
                return None
            
            # Parse the output for the available version
            available_section = False
            for line in result.stdout.splitlines():
                if "Available Packages" in line:
                    available_section = True
                elif available_section and line.startswith("Version"):
                    version = line.split(":", 1)[1].strip()
                    self.version_cache[package_name] = version
                    return version
            
            self.version_cache[package_name] = None
            return None
            
        except subprocess.SubprocessError:
            self.version_cache[package_name] = None
            return None
    
    def batch_get_latest_versions(self, package_names: List[str]) -> Dict[str, Optional[str]]:
        """Get the latest available versions for multiple packages in a single operation"""
        if not package_names:
            return {}
            
        # Remove packages already in cache
        packages_to_check = [pkg for pkg in package_names if pkg not in self.version_cache]
        if not packages_to_check:
            return {pkg: self.version_cache.get(pkg) for pkg in package_names}
            
        results = {}
        try:
            # Use DNF list to get available versions for multiple packages at once
            cmd = [self.dnf_path, 'list', 'available'] + packages_to_check
            result = self._safe_run_rpm_command(cmd, check=False)
            
            if result.returncode != 0:
                # Mark all as not found
                for pkg in packages_to_check:
                    self.version_cache[pkg] = None
                return {pkg: self.version_cache.get(pkg) for pkg in package_names}
            
            # Parse the output for available versions
            for line in result.stdout.splitlines():
                if not line.strip() or line.startswith('Last metadata') or line.startswith('Available Packages'):
                    continue
                    
                parts = line.split()
                if len(parts) >= 2:
                    # The first part should be package name, second part is version
                    pkg_name_arch = parts[0]
                    pkg_name = pkg_name_arch.split('.')[0]  # Remove architecture suffix
                    version = parts[1]
                    
                    if pkg_name in packages_to_check:
                        self.version_cache[pkg_name] = version
                        results[pkg_name] = version
            
            # Mark all packages that weren't found in the output as None
            for pkg in packages_to_check:
                if pkg not in results:
                    self.version_cache[pkg] = None
                    
            # Combine with existing cache data
            return {pkg: self.version_cache.get(pkg) for pkg in package_names}
            
        except Exception as e:
            logger.error(f"Error in batch version check: {e}")
            # Mark all as not found on error
            for pkg in packages_to_check:
                self.version_cache[pkg] = None
            return {pkg: self.version_cache.get(pkg) for pkg in package_names}
    
    def batch_check_versions_available(self, packages: List[Tuple[str, str]]) -> Dict[str, bool]:
        """Check if specific versions are available for multiple packages at once
        
        Args:
            packages: List of (package_name, version) tuples
            
        Returns:
            Dict mapping package names to boolean indicating if the version is available
        """
        if not packages:
            return {}
            
        results = {}
        try:
            # Get all package names
            package_names = [pkg[0] for pkg in packages]
            
            # Use DNF list with --showduplicates to get all available versions
            cmd = [self.dnf_path, 'list', '--showduplicates'] + package_names
            result = self._safe_run_rpm_command(cmd, check=False)
            
            if result.returncode != 0:
                # Mark all as not available
                return {pkg[0]: False for pkg in packages}
            
            # Parse output to map each package to its available versions
            package_versions = {}
            current_pkg = None
            available_section = False
            
            for line in result.stdout.splitlines():
                if "Available Packages" in line:
                    available_section = True
                    continue
                    
                if not available_section or not line.strip():
                    continue
                    
                parts = line.split()
                if len(parts) >= 2:
                    pkg_name_arch = parts[0]
                    pkg_name = pkg_name_arch.split('.')[0]  # Remove architecture suffix
                    ver = parts[1].strip()
                    
                    if pkg_name in package_names:
                        if pkg_name not in package_versions:
                            package_versions[pkg_name] = []
                        package_versions[pkg_name].append(ver)
            
            # Check each requested package/version against available versions
            for pkg_name, version in packages:
                if pkg_name not in package_versions:
                    results[pkg_name] = False
                    continue
                    
                # Check if the version is in the list
                available_versions = package_versions[pkg_name]
                version_available = False
                
                for available in available_versions:
                    if available.startswith(version) or version.startswith(available):
                        version_available = True
                        break
                        
                results[pkg_name] = version_available
                
            return results
            
        except Exception as e:
            logger.error(f"Error in batch version availability check: {e}")
            # Mark all as not available on error
            return {pkg[0]: False for pkg in packages}
    
    def is_version_available(self, package_name: str, version: str) -> bool:
        """Check if a specific version of a package is available"""
        # Use batch check for a single package
        result = self.batch_check_versions_available([(package_name, version)])
        return result.get(package_name, False)
    
    def install_package(self, package_name: str, version: Optional[str] = None) -> bool:
        """Install a package using DNF"""
        if not self.has_sudo:
            logger.error("Sudo privileges required to install packages")
            return False
        
        try:
            cmd = [self.dnf_path, 'install', '-y']
            
            if version:
                # For DNF, we use package-version format
                cmd.append(f"{package_name}-{version}")
            else:
                cmd.append(package_name)
            
            result = self._safe_run_rpm_command(cmd, check=True)
            return result.returncode == 0
            
        except subprocess.SubprocessError as e:
            logger.error(f"Error installing package {package_name}: {e}")
            return False
    
    def populate_bulk_availability_cache(self, package_names: List[str]):
        """Efficiently populate the availability cache for multiple packages at once
        
        This is much faster than calling is_package_available individually for each package
        """
        if not package_names:
            return
            
        logger.info(f"Bulk checking availability for {len(package_names)} packages...")
        
        # Deduplicate the package list and only check packages not already in cache
        packages_to_check = list(set([pkg for pkg in package_names if pkg not in self.availability_cache]))
        if not packages_to_check:
            logger.info(f"All {len(package_names)} packages already in cache")
            return
            
        logger.info(f"Need to check {len(packages_to_check)} unique packages")
        
        # Use a smaller batch size to avoid command line length issues
        batch_size = 25
        total_batches = (len(packages_to_check) + batch_size - 1) // batch_size
        total_available = 0
        
        # First try 'dnf list available' with wildcards to get all available packages
        try:
            # Get a full list of available packages in one command
            cmd = [self.dnf_path, 'list', 'available', '--quiet']
            logger.info(f"Running: {' '.join(cmd)}")
            print(f"Loading available package list from repositories...")
            result = self._safe_run_rpm_command(cmd, check=False, timeout=60)
            
            if result.returncode == 0:
                # Process all available packages
                available_packages = set()
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if not line or line.startswith('Last metadata') or line.startswith('Available Packages'):
                        continue
                    
                    # Parse line (format: name.arch  version  repo)
                    parts = line.split()
                    if len(parts) >= 2:
                        pkg_name_with_arch = parts[0]
                        # Extract package name without architecture
                        pkg_name = pkg_name_with_arch.split('.')[0]
                        available_packages.add(pkg_name.lower())
                
                # Update availability cache
                for pkg in packages_to_check:
                    is_available = pkg.lower() in available_packages
                    self.availability_cache[pkg] = is_available
                    
                    if is_available:
                        total_available += 1
                    
                logger.info(f"Found {len(available_packages)} available packages in repositories")
                logger.info(f"Matched {total_available} packages from our list of {len(packages_to_check)}")
                
                # Also check for common variations for packages not found
                for pkg in packages_to_check:
                    if not self.availability_cache.get(pkg, False):
                        # Try common variations
                        if pkg == '7zip' and 'p7zip'.lower() in available_packages:
                            self.availability_cache[pkg] = True
                            total_available += 1
                            logger.debug(f"Package {pkg} available as p7zip")
                            
                        elif pkg.startswith('lib') and not pkg.endswith('-devel'):
                            devel_pkg = f"{pkg}-devel"
                            if devel_pkg.lower() in available_packages:
                                self.availability_cache[pkg] = True
                                total_available += 1
                                logger.debug(f"Package {pkg} available as {devel_pkg}")
                                
                        elif not pkg.startswith('python'):
                            python_pkg = f"python3-{pkg}"
                            if python_pkg.lower() in available_packages:
                                self.availability_cache[pkg] = True
                                total_available += 1
                                logger.debug(f"Package {pkg} available as {python_pkg}")
                
                # Save the cache
                self._save_availability_cache()
                logger.info(f"Updated availability cache with {total_available} available packages")
                return
        except Exception as e:
            logger.warning(f"Error getting full list of available packages: {e}")
            # Fall back to batch processing
        
        # Fall back to batch processing if the full list approach failed
        logger.info(f"Falling back to batch processing ({total_batches} batches of up to {batch_size} packages)")
        total_available = 0
        
        for i in range(0, len(packages_to_check), batch_size):
            batch = packages_to_check[i:i+batch_size]
            logger.info(f"Checking batch {i//batch_size + 1}/{total_batches} ({len(batch)} packages)")
            
            try:
                # Run dnf list for the batch
                cmd = [self.dnf_path, 'list', 'available'] + batch
                result = self._safe_run_rpm_command(cmd, check=False, timeout=30)
                
                # Process the output to determine which packages are available
                available_in_batch = set()
                
                if result.returncode == 0:
                    # Parse the output for available packages
                    in_available_section = False
                    
                    for line in result.stdout.splitlines():
                        line = line.strip()
                        
                        if "Available Packages" in line:
                            in_available_section = True
                            continue
                            
                        if not in_available_section or not line:
                            continue
                            
                        # Available package lines are in format: name.arch  version  repo
                        parts = line.split()
                        if len(parts) >= 2:
                            # Extract the package name without architecture
                            pkg_name_with_arch = parts[0]
                            # Split off the architecture (e.g., firefox.x86_64 -> firefox)
                            pkg_name = pkg_name_with_arch.split('.')[0]
                            available_in_batch.add(pkg_name.lower())
                            logger.debug(f"Found available package: {pkg_name}")
                
                # Update cache with results (case-insensitive matching)
                for pkg in batch:
                    is_available = pkg.lower() in available_in_batch
                    self.availability_cache[pkg] = is_available
                    
                    if is_available:
                        total_available += 1
                        logger.debug(f"Package {pkg} is available")
                    else:
                        logger.debug(f"Package {pkg} is not available")
                        
                    # Also check common variations
                    if not is_available:
                        # Special case for 7zip -> p7zip
                        if pkg.lower() == '7zip' and 'p7zip'.lower() in available_in_batch:
                            self.availability_cache[pkg] = True
                            total_available += 1
                            logger.debug(f"Package {pkg} is available as p7zip")
                            
                        # Try lib packages with -devel suffix
                        elif pkg.lower().startswith('lib') and not pkg.lower().endswith('-devel'):
                            lib_devel = f"{pkg}-devel"
                            if lib_devel.lower() in available_in_batch:
                                self.availability_cache[pkg] = True
                                total_available += 1
                                logger.debug(f"Package {pkg} is available as {lib_devel}")
                        
                        # Try python variations
                        elif not pkg.lower().startswith('python'):
                            python3_pkg = f"python3-{pkg}"
                            if python3_pkg.lower() in available_in_batch:
                                self.availability_cache[pkg] = True
                                total_available += 1
                                logger.debug(f"Package {pkg} is available as {python3_pkg}")
                
                # Save the cache periodically
                if (i // batch_size) % 5 == 0:
                    self._save_availability_cache()
                    
            except Exception as e:
                logger.warning(f"Error checking batch {i//batch_size + 1}: {e}")
                # Mark all packages in this batch as unavailable on error
                for pkg in batch:
                    self.availability_cache[pkg] = False
        
        # Final cache save
        logger.info(f"Updated availability cache with {total_available} available packages")
        self.cache_timestamp = time.time()
        self._save_availability_cache()
    
    def batch_search_packages(self, package_names: List[str], batch_size: int = 50) -> Dict[str, bool]:
        """Search for multiple packages in batches and update availability cache
        
        Args:
            package_names: List of package names to search for
            batch_size: Number of packages to search for in each batch
            
        Returns:
            Dictionary mapping package names to availability status
        """
        results = {}
        
        # Process in batches to avoid command line length limits
        for i in range(0, len(package_names), batch_size):
            batch = package_names[i:i + batch_size]
            
            try:
                # Use dnf search for this batch
                search_cmd = [self.dnf_path, 'search'] + batch
                result = self._safe_run_rpm_command(search_cmd, check=False, timeout=30)
                
                if result.returncode == 0:
                    # Parse search results to identify available packages
                    found_packages = set()
                    
                    for line in result.stdout.splitlines():
                        line = line.strip()
                        if not line or line.startswith('Last metadata') or line.startswith('='):
                            continue
                            
                        if ':' in line:
                            parts = line.split(':')
                            key = parts[0].strip()
                            
                            if key == 'Name' and len(parts) > 1:
                                pkg_name = parts[1].strip()
                                found_packages.add(pkg_name)
                    
                    # Update results for this batch
                    for pkg_name in batch:
                        is_available = pkg_name in found_packages
                        results[pkg_name] = is_available
                        self.availability_cache[pkg_name] = is_available
                        
                        # Check common variants if not found directly
                        if not is_available:
                            # p7zip for 7zip
                            if pkg_name == '7zip' and 'p7zip' in found_packages:
                                results[pkg_name] = True
                                self.availability_cache[pkg_name] = True
                            
                            # Check for -devel variants for lib packages
                            if pkg_name.startswith('lib') and not pkg_name.endswith('-devel'):
                                devel_pkg = f"{pkg_name}-devel"
                                if devel_pkg in found_packages:
                                    results[pkg_name] = True
                                    self.availability_cache[pkg_name] = True
                                    
                            # Check for python3- prefix
                            if not pkg_name.startswith('python'):
                                python_pkg = f"python3-{pkg_name}"
                                if python_pkg in found_packages:
                                    results[pkg_name] = True
                                    self.availability_cache[pkg_name] = True
                else:
                    # Search failed, mark all packages in this batch as unavailable
                    for pkg_name in batch:
                        results[pkg_name] = False
                        self.availability_cache[pkg_name] = False
                        
            except Exception as e:
                logger.error(f"Error during batch search: {e}")
                # Mark all packages in this batch as unavailable on error
                for pkg_name in batch:
                    results[pkg_name] = False
                    self.availability_cache[pkg_name] = False
        
        # Save the updated cache
        self._save_availability_cache()
        
        return results
    
    def plan_installation(self, packages: List[Dict[str, Any]]) -> tuple:
        """Plan package installation without executing it
        
        Args:
            packages: List of package dictionaries from backup
            
        Returns:
            Tuple of (available_packages, unavailable_packages, upgradable_packages, commands)
        """
        available_packages = []
        unavailable_packages = []
        upgradable_packages = []
        commands = []
        
        # Calculate total for progress reporting
        total = len(packages)
        logger.info(f"Planning installation for {total} DNF packages using parallel processing")
        
        # Extract all package names for bulk availability check
        package_names = [pkg.get('name', '') for pkg in packages if pkg.get('name', '')]
        
        # Perform bulk availability check to populate cache
        self.populate_bulk_availability_cache(package_names)
        
        # Check how many packages are already in cache
        cached_count = sum(1 for name in package_names if name in self.availability_cache)
        logger.info(f"{cached_count}/{len(package_names)} packages found in availability cache")
        
        # Split packages into batches for parallel processing
        batches = []
        for i in range(0, len(packages), BATCH_SIZE):
            batches.append(packages[i:i+BATCH_SIZE])
            
        logger.info(f"Split {len(packages)} packages into {len(batches)} batches for parallel processing")
        
        # Use multiple processes to handle batches in parallel
        try:
            # Create a process pool
            with multiprocessing.Pool(processes=NUM_PROCESSES) as pool:
                # Process batches in parallel
                results = []
                
                # Print info about parallel processing
                logger.info(f"Processing packages using {NUM_PROCESSES} parallel processes")
                print(f"Processing packages in parallel (using {NUM_PROCESSES} processes)...")
                
                # Submit all batches to the pool
                batch_results = pool.map(self._process_package_batch, batches)
                
                # Combine results from all batches
                for batch_avail, batch_unavail, batch_upgrade, batch_cmds in batch_results:
                    available_packages.extend(batch_avail)
                    unavailable_packages.extend(batch_unavail)
                    upgradable_packages.extend(batch_upgrade)
                    commands.extend(batch_cmds)
                    
                logger.info(f"Parallel processing complete. Results: {len(available_packages)} available, "
                          f"{len(unavailable_packages)} unavailable, {len(upgradable_packages)} upgradable")
                
        except Exception as e:
            logger.error(f"Error in parallel processing: {e}")
            logger.info("Falling back to sequential processing")
            
            # Fall back to sequential processing if parallel fails
            for i, pkg in enumerate(packages):
                name = pkg.get('name', '')
                version = pkg.get('version', '')
                
                # Skip if name is missing
                if not name:
                    continue
                    
                # Check if package is available in the repositories (using cache)
                if not self.is_package_available(name):
                    pkg['reason'] = 'Package not available in current repositories'
                    unavailable_packages.append(pkg)
                    continue
                    
                # Check if specific version is requested and available
                if version and self.is_version_available(name, version):
                    # Exact version is available
                    available_packages.append(pkg)
                    commands.append(f"dnf install -y {name}-{version}")
                elif version:
                    # Specific version requested but not available
                    latest = self.get_latest_version(name)
                    if latest:
                        # A different version is available
                        pkg_copy = pkg.copy()
                        pkg_copy['available_version'] = latest
                        upgradable_packages.append(pkg_copy)
                        commands.append(f"dnf install -y {name}  # Requested: {version}, Available: {latest}")
                    else:
                        # No version available
                        pkg['reason'] = f'Requested version {version} not available and no alternative found'
                        unavailable_packages.append(pkg)
                else:
                    # No specific version requested
                    latest = self.get_latest_version(name)
                    if latest:
                        # Latest version is available
                        pkg_copy = pkg.copy()
                        pkg_copy['available_version'] = latest
                        available_packages.append(pkg_copy)
                        commands.append(f"dnf install -y {name}  # Will install version {latest}")
                    else:
                        # Package exists in repo but no installable version found
                        pkg['reason'] = 'Package exists but no installable version found'
                        unavailable_packages.append(pkg)
                
                # Report progress periodically
                if (i+1) % 10 == 0 or (i+1) == total:
                    logger.info(f"Planning progress: {i+1}/{total} packages processed")
        
        # Save the cache when done
        self._save_availability_cache()
                
        return available_packages, unavailable_packages, upgradable_packages, commands 