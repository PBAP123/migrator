#!/usr/bin/env python3
"""
Fstab entry analysis and management for Migrator

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
import re
import logging
from typing import List, Dict, Any, Tuple, Optional, Set

logger = logging.getLogger(__name__)

class FstabEntry:
    """Represents a single fstab entry"""
    
    def __init__(self, line: str):
        """Initialize from a line in fstab"""
        self.raw_line = line.strip()
        self.is_comment = line.strip().startswith('#')
        self.is_empty = len(line.strip()) == 0
        self.is_valid = not (self.is_comment or self.is_empty)
        
        # Default values
        self.fs_spec = ""
        self.mount_point = ""
        self.fs_type = ""
        self.options = ""
        self.dump = "0"
        self.fsck = "0"
        self.is_portable = False
        
        # Parse if it's a valid entry
        if self.is_valid:
            self._parse_entry()
            self._determine_portability()
    
    def _parse_entry(self) -> None:
        """Parse the entry components"""
        # Split fields and handle tabs/spaces
        fields = re.split(r'\s+', self.raw_line.strip())
        
        # Must have at least fs_spec, mount_point, and fs_type
        if len(fields) >= 3:
            self.fs_spec = fields[0]
            self.mount_point = fields[1]
            self.fs_type = fields[2]
            
            # Optional fields
            if len(fields) >= 4:
                self.options = fields[3]
            if len(fields) >= 5:
                self.dump = fields[4]
            if len(fields) >= 6:
                self.fsck = fields[5]
    
    def _determine_portability(self) -> None:
        """Determine if this entry is portable across systems"""
        # Consider the entry portable if it meets any of these criteria:
        
        # 1. Network filesystems (NFS, CIFS/SMB, etc.)
        if any(fs in self.fs_type.lower() for fs in ['nfs', 'cifs', 'smb', 'sshfs']):
            self.is_portable = True
            logger.debug(f"Entry marked portable (network filesystem): {self.fs_spec} -> {self.mount_point}")
            return
            
        # 2. Remote/network paths in fs_spec
        if self.fs_spec.startswith('//') or ':' in self.fs_spec:
            self.is_portable = True
            logger.debug(f"Entry marked portable (network path): {self.fs_spec} -> {self.mount_point}")
            return
            
        # 3. Special filesystem types that are not hardware-dependent
        portable_fs_types = [
            'proc', 'sysfs', 'tmpfs', 'devpts', 'debugfs', 'securityfs',
            'cgroup', 'pstore', 'efivarfs', 'configfs', 'fuse'
        ]
        if self.fs_type.lower() in portable_fs_types:
            self.is_portable = True
            logger.debug(f"Entry marked portable (special filesystem): {self.fs_spec} -> {self.mount_point}")
            return
            
        # 4. Bind mounts (these might be portable depending on the source)
        if 'bind' in self.options:
            # Consider bind mounts portable if the source is in a standard path
            portable_sources = ['/var', '/home', '/opt', '/usr', '/etc']
            if any(self.fs_spec.startswith(src) for src in portable_sources):
                self.is_portable = True
                logger.debug(f"Entry marked portable (bind mount): {self.fs_spec} -> {self.mount_point}")
                return
        
        # By default, entries are considered non-portable (hardware-specific)
        self.is_portable = False
        logger.debug(f"Entry not portable: {self.fs_spec} -> {self.mount_point}")
    
    @property
    def device(self) -> str:
        """Alias for fs_spec for compatibility"""
        return self.fs_spec
    
    @property
    def fstype(self) -> str:
        """Alias for fs_type for compatibility"""
        return self.fs_type
    
    @property
    def mountpoint(self) -> str:
        """Alias for mount_point for compatibility"""
        return self.mount_point
    
    def to_line(self) -> str:
        """Convert back to a fstab line"""
        if self.is_comment or self.is_empty:
            return self.raw_line
        
        # Reconstruct the line with proper spacing
        return f"{self.fs_spec}\t{self.mount_point}\t{self.fs_type}\t{self.options}\t{self.dump}\t{self.fsck}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'raw_line': self.raw_line,
            'is_comment': self.is_comment,
            'is_empty': self.is_empty,
            'is_valid': self.is_valid,
            'fs_spec': self.fs_spec,
            'mount_point': self.mount_point,
            'fs_type': self.fs_type,
            'options': self.options,
            'dump': self.dump,
            'fsck': self.fsck,
            'is_portable': self.is_portable
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FstabEntry':
        """Create from a dictionary"""
        entry = cls(data.get('raw_line', ''))
        entry.is_comment = data.get('is_comment', False)
        entry.is_empty = data.get('is_empty', False)
        entry.is_valid = data.get('is_valid', False)
        entry.fs_spec = data.get('fs_spec', '')
        entry.mount_point = data.get('mount_point', '')
        entry.fs_type = data.get('fs_type', '')
        entry.options = data.get('options', '')
        entry.dump = data.get('dump', '0')
        entry.fsck = data.get('fsck', '0')
        entry.is_portable = data.get('is_portable', False)
        return entry
    
    def __str__(self) -> str:
        if self.is_comment or self.is_empty:
            return f"Comment/Empty: {self.raw_line}"
        return f"FstabEntry: {self.fs_spec} -> {self.mount_point} ({self.fs_type}) Portable: {self.is_portable}"


class FstabManager:
    """Manages fstab entries and portability"""
    
    def __init__(self, fstab_path: str = '/etc/fstab'):
        """Initialize with path to fstab"""
        self.fstab_path = fstab_path
        self.entries: List[FstabEntry] = []
        self.portable_entries: List[FstabEntry] = []
        
        # Try to load the file if it exists
        if os.path.exists(fstab_path) and os.access(fstab_path, os.R_OK):
            self.load_fstab()
    
    def load_fstab(self) -> bool:
        """Load entries from fstab file"""
        self.entries = []
        self.portable_entries = []
        
        try:
            with open(self.fstab_path, 'r') as f:
                for line in f:
                    entry = FstabEntry(line)
                    self.entries.append(entry)
                    
                    # Collect portable entries
                    if entry.is_valid and entry.is_portable:
                        self.portable_entries.append(entry)
            
            logger.info(f"Loaded {len(self.entries)} entries from {self.fstab_path}")
            logger.info(f"Found {len(self.portable_entries)} portable entries")
            return True
        except Exception as e:
            logger.error(f"Error loading fstab from {self.fstab_path}: {e}")
            return False
    
    def get_portable_entries(self) -> List[FstabEntry]:
        """Get only the portable entries"""
        return self.portable_entries
    
    def append_portable_entries(self, target_fstab_path: str) -> bool:
        """Append portable entries to target fstab file"""
        if not self.portable_entries:
            logger.info("No portable entries to append")
            return True
        
        # Check if the target file exists and is writable
        if not os.path.exists(target_fstab_path):
            logger.error(f"Target fstab file does not exist: {target_fstab_path}")
            return False
        
        if not os.access(target_fstab_path, os.W_OK):
            logger.error(f"Target fstab file is not writable: {target_fstab_path}")
            return False
        
        try:
            # Create a backup of the target file
            backup_path = f"{target_fstab_path}.migrator.bak"
            with open(target_fstab_path, 'r') as src, open(backup_path, 'w') as backup:
                backup.write(src.read())
            
            logger.info(f"Created backup of target fstab: {backup_path}")
            
            # Open the target file for appending
            with open(target_fstab_path, 'a') as f:
                # Add a comment header
                f.write("\n# Portable fstab entries added by Migrator\n")
                
                # Add each portable entry
                for entry in self.portable_entries:
                    f.write(f"{entry.to_line()}\n")
            
            logger.info(f"Appended {len(self.portable_entries)} portable entries to {target_fstab_path}")
            return True
        except Exception as e:
            logger.error(f"Error appending portable entries to {target_fstab_path}: {e}")
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'fstab_path': self.fstab_path,
            'portable_entries': [entry.to_dict() for entry in self.portable_entries]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FstabManager':
        """Create from a dictionary"""
        manager = cls('/etc/fstab')  # Default path
        
        # Set the path
        if 'fstab_path' in data:
            manager.fstab_path = data['fstab_path']
        
        # Load the portable entries
        manager.portable_entries = []
        for entry_data in data.get('portable_entries', []):
            entry = FstabEntry.from_dict(entry_data)
            manager.portable_entries.append(entry)
        
        logger.info(f"Loaded {len(manager.portable_entries)} portable entries from backup")
        return manager 