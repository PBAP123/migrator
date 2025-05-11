#!/usr/bin/env python3
"""
Distribution detection utilities for LinuxPackages
"""

import os
import subprocess
import platform
import json
from typing import Dict, List, Tuple, Optional

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
        
        # Fallback to platform module if os-release doesn't exist
        if not self.name:
            self.name = platform.linux_distribution()[0]
            self.version = platform.linux_distribution()[1]
            self.id = self.name.lower()
        
        # Determine package managers based on distribution
        self._detect_package_managers()
        
        return self
    
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
        if self.id in ['ubuntu', 'debian'] or 'debian' in self.id_like:
            self.default_package_format = 'deb'
        elif self.id in ['fedora', 'rhel', 'centos'] or 'fedora' in self.id_like:
            self.default_package_format = 'rpm'
        elif self.id in ['arch', 'manjaro'] or 'arch' in self.id_like:
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
            else:
                self.default_package_format = 'unknown'
        
        self.package_managers = package_managers
    
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
    distro_info = get_distro_info()
    print(distro_info)
    print(json.dumps(distro_info.to_dict(), indent=2)) 