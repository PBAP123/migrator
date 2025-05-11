#!/usr/bin/env python3
"""
Configuration module for Migrator

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
import json
import logging
from typing import Dict, Any, Optional

# Configure logging
logger = logging.getLogger(__name__)

# Default configuration values
DEFAULT_BACKUP_DIR = os.path.expanduser("~/migrator_backups")

# Configuration file location
CONFIG_DIR = os.path.expanduser("~/.config/migrator")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

class Config:
    """Configuration manager for Migrator"""
    
    def __init__(self):
        """Initialize the configuration manager"""
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default"""
        # Ensure config directory exists
        os.makedirs(CONFIG_DIR, exist_ok=True)
        
        # Check if config file exists
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                logger.info(f"Loaded configuration from {CONFIG_FILE}")
                return config
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading configuration: {e}")
                # Fall back to default config
        
        # Create default configuration
        default_config = {
            "backup_dir": DEFAULT_BACKUP_DIR
        }
        
        # Save default config
        self._save_config(default_config)
        return default_config
    
    def _save_config(self, config: Dict[str, Any]) -> bool:
        """Save configuration to file"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"Saved configuration to {CONFIG_FILE}")
            return True
        except IOError as e:
            logger.error(f"Error saving configuration: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value"""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> bool:
        """Set a configuration value"""
        self.config[key] = value
        return self._save_config(self.config)
    
    def get_backup_dir(self) -> str:
        """Get the configured backup directory"""
        return self.config.get("backup_dir", DEFAULT_BACKUP_DIR)
    
    def set_backup_dir(self, backup_dir: str) -> bool:
        """Set the backup directory
        
        Args:
            backup_dir: Path to the backup directory
            
        Returns:
            Whether the operation was successful
        """
        # Validate the path
        backup_dir = os.path.expanduser(backup_dir)
        
        # Check if directory exists or can be created
        try:
            os.makedirs(backup_dir, exist_ok=True)
        except (IOError, PermissionError) as e:
            logger.error(f"Cannot use backup directory {backup_dir}: {e}")
            return False
            
        self.config["backup_dir"] = backup_dir
        return self._save_config(self.config)

# Create singleton instance
config = Config() 