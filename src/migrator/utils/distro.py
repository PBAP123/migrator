#!/usr/bin/env python3
"""
Distribution detection utilities for LinuxPackages
"""

import os
import subprocess
import platform
import json
import logging
import re
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

class DistroInfo:
    """Information about the current Linux distribution"""
    
    def __init__(self):
        self.name = ""
        self.version = ""
        self.id = ""
        self.id_like = []
        self.package_managers = []
        self.default_package_format = ""
    
    def detect(self) -> 'DistroInfo':
        """Detect the current Linux distribution and its properties"""
        # Try os-release first (most distributions)
        if os.path.exists('/etc/os-release'):
            try:
                with open('/etc/os-release', 'r') as f:
                    os_release = {}
                    for line in f:
                        if '=' in line:
                            key, value = line.rstrip().split('=', 1)
                            os_release[key] = value.strip('"')
                    
                    self.name = os_release.get('NAME', '')
                    self.version = os_release.get('VERSION_ID', '')
                    self.id = os_release.get('ID', '')
                    self.id_like = os_release.get('ID_LIKE', '').split()
                    
                logger.info(f"Detected distribution from os-release: {self.name} {self.version} ({self.id})")
            except Exception as e:
                logger.error(f"Error reading os-release: {e}")
        
        # Fallback to other methods if os-release doesn't provide enough info
        if not self.name or not self.id:
            self._fallback_detection()
        
        # Determine package managers based on distribution
        self._detect_package_managers()
        
        return self
    
    def _fallback_detection(self):
        """Use alternative methods to detect the distribution"""
        # Try lsb_release command
        try:
            result = subprocess.run(['lsb_release', '-a'], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE, 
                                   text=True,
                                   check=False)
            if result.returncode == 0:
                # Parse lsb_release output
                distro_name = ""
                distro_id = ""
                distro_version = ""
                
                for line in result.stdout.splitlines():
                    if "Distributor ID:" in line:
                        distro_id = line.split(":", 1)[1].strip()
                    elif "Description:" in line:
                        distro_name = line.split(":", 1)[1].strip()
                    elif "Release:" in line:
                        distro_version = line.split(":", 1)[1].strip()
                
                if distro_name:
                    self.name = distro_name
                if distro_id:
                    self.id = distro_id.lower()
                if distro_version:
                    self.version = distro_version
                    
                logger.info(f"Detected distribution from lsb_release: {self.name} {self.version} ({self.id})")
                return
        except Exception as e:
            logger.debug(f"lsb_release detection failed: {e}")
        
        # Check common distribution-specific files
        distro_files = {
            '/etc/fedora-release': ('fedora', 'Fedora'),
            '/etc/redhat-release': ('rhel', 'Red Hat Enterprise Linux'),
            '/etc/centos-release': ('centos', 'CentOS'),
            '/etc/debian_version': ('debian', 'Debian'),
            '/etc/arch-release': ('arch', 'Arch Linux'),
            '/etc/gentoo-release': ('gentoo', 'Gentoo'),
            '/etc/SuSE-release': ('opensuse', 'openSUSE'),
            '/etc/slackware-version': ('slackware', 'Slackware'),
        }
        
        for file_path, (dist_id, dist_name) in distro_files.items():
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        content = f.read().strip()
                    
                    # Try to extract version from the content
                    version_match = re.search(r'[0-9]+(\.[0-9]+)*', content)
                    version = version_match.group(0) if version_match else "unknown"
                    
                    self.id = dist_id
                    self.name = dist_name
                    self.version = version
                    
                    logger.info(f"Detected distribution from {file_path}: {self.name} {self.version} ({self.id})")
                    return
                except Exception as e:
                    logger.debug(f"Error reading {file_path}: {e}")
        
        # Check for common package managers and infer distribution
        self._infer_from_package_managers()
        
        # Last resort: try platform module (though it's deprecated in recent Python versions)
        if (not self.name or not self.id) and hasattr(platform, 'linux_distribution'):
            try:
                dist = platform.linux_distribution()
                if dist[0]:
                    self.name = dist[0]
                    self.version = dist[1]
                    self.id = self.name.lower().split()[0]
                    logger.info(f"Detected distribution from platform module: {self.name} {self.version} ({self.id})")
            except:
                pass
                
        # Ensure we don't return empty values
        if not self.name:
            uname = platform.uname()
            self.name = f"Unknown Linux ({uname.system})"
            logger.warning(f"Could not determine distribution name, using fallback: {self.name}")
            
        if not self.id:
            self.id = "linux"
            logger.warning(f"Could not determine distribution ID, using fallback: {self.id}")
            
        if not self.version:
            self.version = "unknown"
            logger.warning(f"Could not determine distribution version, using fallback: {self.version}")
    
    def _infer_from_package_managers(self):
        """Infer distribution based on available package managers"""
        # Check for common package managers
        pm_commands = {
            'apt': '/usr/bin/apt',
            'dnf': '/usr/bin/dnf',
            'pacman': '/usr/bin/pacman',
            'zypper': '/usr/bin/zypper',
            'emerge': '/usr/bin/emerge',
            'xbps': '/usr/bin/xbps-install',
        }
        
        found_pms = []
        for pm, path in pm_commands.items():
            if os.path.exists(path):
                found_pms.append(pm)
        
        # Infer distribution from package managers
        if 'apt' in found_pms:
            # Could be Debian or Ubuntu, try to differentiate
            if os.path.exists('/etc/debian_version'):
                if os.path.exists('/etc/lsb-release'):
                    # Likely Ubuntu
                    self.name = 'Ubuntu'
                    self.id = 'ubuntu'
                    
                    # Try to get version from lsb-release
                    try:
                        with open('/etc/lsb-release', 'r') as f:
                            for line in f:
                                if line.startswith('DISTRIB_RELEASE='):
                                    self.version = line.split('=', 1)[1].strip()
                                    break
                    except:
                        pass
                else:
                    # Likely Debian
                    self.name = 'Debian'
                    self.id = 'debian'
                    
                    # Try to get version from debian_version
                    try:
                        with open('/etc/debian_version', 'r') as f:
                            self.version = f.read().strip()
                    except:
                        pass
        elif 'dnf' in found_pms:
            # Likely Fedora or RHEL-based
            if os.path.exists('/etc/fedora-release'):
                self.name = 'Fedora'
                self.id = 'fedora'
            else:
                self.name = 'RPM-based Linux'
                self.id = 'rhel'
        elif 'pacman' in found_pms:
            # Arch-based
            self.name = 'Arch-based Linux'
            self.id = 'arch'
            self.version = 'rolling'
        elif 'zypper' in found_pms:
            # openSUSE
            self.name = 'openSUSE'
            self.id = 'opensuse'
        elif 'emerge' in found_pms:
            # Gentoo
            self.name = 'Gentoo'
            self.id = 'gentoo'
        elif 'xbps' in found_pms:
            # Void Linux
            self.name = 'Void Linux'
            self.id = 'void'
            
        if self.name:
            logger.info(f"Inferred distribution from package managers: {self.name} ({self.id})")
    
    def _detect_package_managers(self):
        """Detect available package managers"""
        package_managers = []
        
        # Check for common package managers
        pm_commands = {
            'apt': '/usr/bin/apt',
            'apt-get': '/usr/bin/apt-get',
            'dpkg': '/usr/bin/dpkg',
            'yum': '/usr/bin/yum',
            'dnf': '/usr/bin/dnf',
            'rpm': '/usr/bin/rpm',
            'pacman': '/usr/bin/pacman',
            'zypper': '/usr/bin/zypper',
            'emerge': '/usr/bin/emerge',
            'xbps': '/usr/bin/xbps-install',
            'snap': '/usr/bin/snap',
            'flatpak': '/usr/bin/flatpak',
        }
        
        for pm, path in pm_commands.items():
            if os.path.exists(path):
                package_managers.append(pm)
        
        # Determine primary package manager based on distro
        if self.id in ['ubuntu', 'debian', 'linuxmint', 'pop', 'elementary'] or 'debian' in self.id_like:
            self.default_package_format = 'deb'
        elif self.id in ['fedora', 'rhel', 'centos', 'rocky', 'alma'] or 'fedora' in self.id_like:
            self.default_package_format = 'rpm'
        elif self.id in ['arch', 'manjaro', 'endeavour'] or 'arch' in self.id_like:
            self.default_package_format = 'pacman'
        elif self.id in ['opensuse', 'suse']:
            self.default_package_format = 'rpm'
        elif self.id == 'gentoo':
            self.default_package_format = 'portage'
        elif self.id == 'void':
            self.default_package_format = 'xbps'
        else:
            # Try to guess based on available package managers
            if 'apt' in package_managers or 'dpkg' in package_managers:
                self.default_package_format = 'deb'
            elif 'dnf' in package_managers or 'yum' in package_managers or 'rpm' in package_managers:
                self.default_package_format = 'rpm'
            elif 'pacman' in package_managers:
                self.default_package_format = 'pacman'
            elif 'zypper' in package_managers:
                self.default_package_format = 'rpm'
            else:
                self.default_package_format = 'unknown'
                logger.warning(f"Could not determine default package format for {self.id}")
        
        self.package_managers = package_managers
        logger.info(f"Detected package managers: {', '.join(package_managers)}")
        logger.info(f"Default package format: {self.default_package_format}")
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            'name': self.name,
            'version': self.version,
            'id': self.id,
            'id_like': self.id_like,
            'package_managers': self.package_managers,
            'default_package_format': self.default_package_format
        }
    
    def __str__(self) -> str:
        return (f"Distribution: {self.name} {self.version}\n"
                f"ID: {self.id}\n"
                f"ID_LIKE: {', '.join(self.id_like)}\n"
                f"Package Managers: {', '.join(self.package_managers)}\n"
                f"Default Package Format: {self.default_package_format}")


def get_distro_info() -> DistroInfo:
    """Get information about the current distribution"""
    return DistroInfo().detect()


if __name__ == "__main__":
    # When run directly, print distribution info
    # Setup logging for standalone execution
    logging.basicConfig(level=logging.INFO,
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    distro_info = get_distro_info()
    print(distro_info)
    print(json.dumps(distro_info.to_dict(), indent=2)) 