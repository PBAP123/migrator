#!/usr/bin/env python3
"""
Base package manager abstract class and interfaces
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Set
import subprocess
import json
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class Package:
    """Represents a single software package"""
    
    def __init__(self, name: str, version: str = "", description: str = "", 
                 source: str = "", install_date: Optional[datetime] = None,
                 manually_installed: bool = False):
        self.name = name
        self.version = version
        self.description = description
        self.source = source  # apt, snap, flatpak, appimage, etc.
        self.install_date = install_date
        self.manually_installed = manually_installed  # True if explicitly installed by user
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'source': self.source,
            'install_date': self.install_date.isoformat() if self.install_date else None,
            'manually_installed': self.manually_installed
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Package':
        """Create a Package object from a dictionary"""
        install_date = None
        if data.get('install_date'):
            try:
                install_date = datetime.fromisoformat(data['install_date'])
            except ValueError:
                logger.warning(f"Invalid install date format: {data['install_date']}")
        
        return cls(
            name=data.get('name', ''),
            version=data.get('version', ''),
            description=data.get('description', ''),
            source=data.get('source', ''),
            install_date=install_date,
            manually_installed=data.get('manually_installed', False)
        )
    
    def __str__(self) -> str:
        return f"{self.name} {self.version} [{self.source}]"
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Package):
            return False
        return self.name == other.name and self.source == other.source
    
    def __hash__(self) -> int:
        return hash((self.name, self.source))


class PackageManager(ABC):
    """Base class for all package managers"""
    
    def __init__(self, name: str):
        self.name = name
        self.available = self._check_available()
    
    def _check_available(self) -> bool:
        """Check if this package manager is available on the system"""
        try:
            result = self._run_command(['--version'], check=False)
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def _run_command(self, args: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run a command using this package manager"""
        cmd = [self.name] + args
        try:
            result = subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                check=check
            )
            return result
        except subprocess.CalledProcessError as e:
            logger.error(f"Error running {' '.join(cmd)}: {e}")
            raise
    
    @abstractmethod
    def list_installed_packages(self) -> List[Package]:
        """List all installed packages"""
        pass
    
    @abstractmethod
    def is_package_available(self, package_name: str) -> bool:
        """Check if a package is available in the repository"""
        pass
    
    @abstractmethod
    def get_package_info(self, package_name: str) -> Optional[Package]:
        """Get detailed information about a package"""
        pass
    
    @abstractmethod
    def get_installed_version(self, package_name: str) -> Optional[str]:
        """Get the installed version of a package"""
        pass
    
    @abstractmethod
    def get_latest_version(self, package_name: str) -> Optional[str]:
        """Get the latest available version of a package"""
        pass
    
    @abstractmethod
    def install_package(self, package_name: str, version: Optional[str] = None) -> bool:
        """Install a package"""
        pass

    @abstractmethod
    def is_user_installed(self, package_name: str) -> bool:
        """Check if a package was explicitly installed by the user (not as a dependency)"""
        pass


class PackageManagerFactory:
    """Factory for creating appropriate package managers"""
    
    @staticmethod
    def create_for_system() -> List[PackageManager]:
        """Create all available package managers for the current system"""
        # This will be implemented by importing all package managers
        # and returning instances of those that are available
        return [] 