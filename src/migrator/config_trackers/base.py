#!/usr/bin/env python3
"""
Base configuration tracker abstract class and interfaces
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Set
import os
import logging
import hashlib
from datetime import datetime

logger = logging.getLogger(__name__)

class ConfigFile:
    """Represents a single configuration file"""
    
    def __init__(self, path: str, description: str = "", category: str = "",
                 is_system_config: bool = False, checksum: Optional[str] = None,
                 last_modified: Optional[datetime] = None):
        self.path = os.path.abspath(os.path.expanduser(path))
        self.description = description
        self.category = category  # e.g., "shell", "desktop", "application"
        self.is_system_config = is_system_config  # True if in /etc, False if user-specific
        self.checksum = checksum or self._calculate_checksum()
        self.last_modified = last_modified or self._get_last_modified()
        self.exists = os.path.exists(self.path)
    
    def _calculate_checksum(self) -> Optional[str]:
        """Calculate a checksum for the file"""
        if not os.path.exists(self.path):
            return None
            
        try:
            hash_md5 = hashlib.md5()
            with open(self.path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except (IOError, OSError) as e:
            logger.warning(f"Could not calculate checksum for {self.path}: {e}")
            return None
    
    def _calculate_checksum_from_data(self, data: bytes) -> Optional[str]:
        """Calculate a checksum from provided data instead of reading the file
        
        This is useful for virtual files or specially processed content.
        
        Args:
            data: The binary data to calculate checksum from
        
        Returns:
            MD5 checksum of the data
        """
        try:
            hash_md5 = hashlib.md5()
            hash_md5.update(data)
            self.checksum = hash_md5.hexdigest()
            return self.checksum
        except Exception as e:
            logger.warning(f"Could not calculate checksum from data for {self.path}: {e}")
            return None
    
    def _get_last_modified(self) -> Optional[datetime]:
        """Get the last modified time of the file"""
        if not os.path.exists(self.path):
            return None
            
        try:
            mtime = os.path.getmtime(self.path)
            return datetime.fromtimestamp(mtime)
        except (IOError, OSError) as e:
            logger.warning(f"Could not get modification time for {self.path}: {e}")
            return None
    
    def has_changed(self) -> bool:
        """Check if the file has changed since it was last tracked"""
        if not os.path.exists(self.path):
            return self.exists  # True if it existed before but doesn't now
            
        current_checksum = self._calculate_checksum()
        return current_checksum != self.checksum
    
    def update(self) -> None:
        """Update checksum and last modified time"""
        self.checksum = self._calculate_checksum()
        self.last_modified = self._get_last_modified()
        self.exists = os.path.exists(self.path)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'path': self.path,
            'description': self.description,
            'category': self.category,
            'is_system_config': self.is_system_config,
            'checksum': self.checksum,
            'last_modified': self.last_modified.isoformat() if self.last_modified else None,
            'exists': self.exists
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConfigFile':
        """Create a ConfigFile object from a dictionary"""
        last_modified = None
        if data.get('last_modified'):
            try:
                last_modified = datetime.fromisoformat(data['last_modified'])
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid last_modified date format: {data['last_modified']} - {str(e)}")
        
        # Get path with safeguards
        path = data.get('path', '')
        if not path:
            logger.warning("ConfigFile dictionary missing required 'path' field")
            path = '/dev/null'  # Use a default path that's unlikely to be useful but won't crash
            
        return cls(
            path=path,
            description=data.get('description', ''),
            category=data.get('category', ''),
            is_system_config=data.get('is_system_config', False),
            checksum=data.get('checksum'),
            last_modified=last_modified
        )
    
    def __str__(self) -> str:
        return f"{self.path} [{self.category}]"
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ConfigFile):
            return False
        return self.path == other.path
    
    def __hash__(self) -> int:
        return hash(self.path)


class ConfigTracker(ABC):
    """Base class for configuration file trackers"""
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    def find_config_files(self) -> List[ConfigFile]:
        """Find configuration files managed by this tracker"""
        pass
    
    @abstractmethod
    def get_config_file(self, path: str) -> Optional[ConfigFile]:
        """Get a specific configuration file by path"""
        pass
    
    @abstractmethod
    def track_config_file(self, path: str, description: str = "", category: str = "") -> Optional[ConfigFile]:
        """Add a configuration file to be tracked"""
        pass
    
    @abstractmethod
    def stop_tracking_config_file(self, path: str) -> bool:
        """Stop tracking a configuration file"""
        pass
    
    @abstractmethod
    def get_changed_files(self) -> List[ConfigFile]:
        """Get list of tracked files that have changed since last check"""
        pass
    
    @abstractmethod
    def update_all(self) -> None:
        """Update checksums for all tracked files"""
        pass 