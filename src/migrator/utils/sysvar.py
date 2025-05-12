#!/usr/bin/env python3
"""
System variable tracking and substitution module for Migrator

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
import socket
import logging
import getpass
import shutil
from typing import Dict, List, Optional, Tuple, Any, Set, Pattern

logger = logging.getLogger(__name__)

class SystemVariables:
    """Tracks and manages system-specific variables for portability"""
    
    def __init__(self):
        """Initialize system variables"""
        # Current system information
        self.username = getpass.getuser()
        self.hostname = socket.gethostname()
        self.home_dir = os.path.expanduser("~")
        
        # Variable placeholders - used when storing paths
        self.placeholders = {
            "USERNAME": self.username,
            "HOSTNAME": self.hostname,
            "HOME": self.home_dir,
            # Add more system variables as needed
        }
        
        # Create regex patterns for variable detection
        self._compile_patterns()
        
        logger.info(f"Initialized system variables: username={self.username}, hostname={self.hostname}")
    
    def _compile_patterns(self) -> None:
        """Compile regex patterns for variable detection"""
        # Create regex patterns for each variable
        self.patterns = {}
        for var_name, value in self.placeholders.items():
            if value:
                # Escape special regex characters in the value
                escaped_value = re.escape(value)
                # Create pattern that matches the value
                self.patterns[var_name] = re.compile(r'(?<!\w)' + escaped_value + r'(?!\w)')
    
    def detect_variables(self, path: str) -> str:
        """Detect and replace system variables in a path with placeholders
        
        Args:
            path: The path to process
            
        Returns:
            Path with system-specific variables replaced by placeholders
        """
        # Skip if path is empty
        if not path:
            return path
            
        # Start with the original path
        result = path
        
        # Replace system variables with placeholders
        for var_name, pattern in self.patterns.items():
            placeholder = f"${{{var_name}}}"
            result = pattern.sub(placeholder, result)
        
        # Log if substitutions were made
        if result != path:
            logger.debug(f"Path with variables: {path} -> {result}")
            
        return result
    
    def substitute_variables(self, path: str, target_vars: Optional[Dict[str, str]] = None) -> str:
        """Substitute variable placeholders in a path with actual values
        
        Args:
            path: The path with placeholders to process
            target_vars: Optional dictionary of target system variables.
                         If None, uses current system variables.
        
        Returns:
            Path with placeholders replaced by actual system values
        """
        # Skip if path is empty
        if not path:
            return path
            
        # Use current system variables if target_vars not provided
        vars_to_use = target_vars or self.placeholders
        
        # Start with the original path
        result = path
        
        # Replace placeholders with system variables
        for var_name, value in vars_to_use.items():
            placeholder = f"${{{var_name}}}"
            result = result.replace(placeholder, value)
        
        # Log if substitutions were made
        if result != path:
            logger.debug(f"Substituted variables: {path} -> {result}")
            
        return result
    
    def process_config_file(self, file_path: str, target_vars: Optional[Dict[str, str]] = None) -> bool:
        """Process a configuration file, replacing system variables
        
        Args:
            file_path: Path to the configuration file
            target_vars: Optional dictionary of target system variables.
                         If None, uses current system variables.
        
        Returns:
            Whether the operation was successful
        """
        if not os.path.exists(file_path) or not os.access(file_path, os.R_OK):
            logger.error(f"Cannot access config file {file_path}")
            return False
        
        try:
            # Read the file content
            with open(file_path, 'r', errors='replace') as f:
                content = f.read()
            
            # Apply variable substitution
            modified_content = content
            
            # Use current system variables if target_vars not provided
            vars_to_use = target_vars or self.placeholders
            
            # Substitute each variable
            for var_name, value in vars_to_use.items():
                if value:
                    # Skip empty values
                    placeholder = f"${{{var_name}}}"
                    modified_content = modified_content.replace(placeholder, value)
            
            # Write back only if changes were made
            if modified_content != content:
                # Create a backup of the original file
                backup_path = f"{file_path}.migrator.bak"
                shutil.copy2(file_path, backup_path)
                
                # Write the modified content
                with open(file_path, 'w') as f:
                    f.write(modified_content)
                
                logger.info(f"Updated system variables in {file_path}")
                return True
            
            return True  # File processed, no changes needed
            
        except Exception as e:
            logger.error(f"Error processing config file {file_path}: {e}")
            return False
    
    def to_dict(self) -> Dict[str, str]:
        """Convert system variables to dictionary for serialization"""
        return {
            "username": self.username,
            "hostname": self.hostname,
            "home_dir": self.home_dir
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'SystemVariables':
        """Create SystemVariables object from a dictionary
        
        This is used when restoring from a backup to compare
        the source system variables to the current system.
        """
        sysvar = cls()
        
        # Save original system values
        orig_username = sysvar.username
        orig_hostname = sysvar.hostname
        orig_home_dir = sysvar.home_dir
        
        # Set the source system values from the backup data
        if "username" in data:
            sysvar.placeholders["USERNAME"] = data["username"]
        
        if "hostname" in data:
            sysvar.placeholders["HOSTNAME"] = data["hostname"]
            
        if "home_dir" in data:
            sysvar.placeholders["HOME"] = data["home_dir"]
        
        # Create a dictionary mapping source system variables to target system variables
        sysvar.source_to_target = {
            data.get("username", ""): orig_username,
            data.get("hostname", ""): orig_hostname,
            data.get("home_dir", ""): orig_home_dir
        }
        
        # Recompile patterns with the source system values
        sysvar._compile_patterns()
        
        return sysvar
    
    def get_path_transformation_map(self) -> Dict[str, str]:
        """Get a mapping of source system paths to target system paths
        
        This is useful for bulk string replacement operations in config files.
        
        Returns:
            Dictionary mapping source paths to target paths
        """
        # Start with an empty map
        path_map = {}
        
        # Add home directory mapping if source and target differ
        source_home = self.placeholders.get("HOME", "")
        target_home = self.home_dir
        
        if source_home and source_home != target_home:
            path_map[source_home] = target_home
        
        # Add username mapping (for paths containing username)
        source_username = self.placeholders.get("USERNAME", "")
        target_username = self.username
        
        if source_username and source_username != target_username:
            # Add mapping for username appearing in paths
            path_map[f"/home/{source_username}"] = f"/home/{target_username}"
        
        return path_map

def count_replacements(sysvar: SystemVariables, content: str) -> int:
    """Count the number of path replacements that would be made
    
    Args:
        sysvar: SystemVariables object with source system variables
        content: Content to check for replacements
        
    Returns:
        Number of replacements that would be made
    """
    count = 0
    
    # Check for source system variables in content
    for src, tgt in sysvar.source_to_target.items():
        if src and tgt and src in content:
            count += content.count(src)
            
    # Check for other placeholder patterns
    for pattern in sysvar.patterns:
        count += len(pattern.findall(content))
            
    return count

def transform_content(sysvar: SystemVariables, content: str) -> Tuple[str, int]:
    """Transform content by replacing source system paths
    
    Args:
        sysvar: SystemVariables object with source system variables
        content: Content to transform
        
    Returns:
        Tuple of (transformed content, number of replacements made)
    """
    new_content = content
    count = 0
    
    # Replace source system variables with target system variables
    for src, tgt in sysvar.source_to_target.items():
        if src and tgt and src in new_content:
            replacements = new_content.count(src)
            new_content = new_content.replace(src, tgt)
            count += replacements
    
    # Replace patterns
    for pattern in sysvar.patterns:
        for match in pattern.finditer(content):
            placeholder = match.group(1)
            if placeholder in sysvar.placeholders:
                replacement = sysvar.placeholders[placeholder]
                # Replace this specific match
                start, end = match.span(0)
                before = new_content[:start]
                after = new_content[end:]
                matched_text = new_content[start:end]
                new_text = matched_text.replace(match.group(0), replacement)
                new_content = before + new_text + after
                count += 1
    
    return new_content, count

# Create singleton instance
system_variables = SystemVariables() 