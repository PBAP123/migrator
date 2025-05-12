#!/usr/bin/env python3
"""
Diagnostic tool for fstab entry detection in Migrator
"""

import os
import sys
import logging

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("fstab_diagnostic")

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from migrator.utils.fstab import FstabManager, FstabEntry
    from migrator.config_trackers.system_config import SystemConfigTracker
except ImportError as e:
    logger.error(f"Failed to import Migrator modules: {e}")
    logger.error("Make sure you're running this script from the Migrator project directory")
    sys.exit(1)

def analyze_fstab():
    """Analyze the fstab entries"""
    logger.info("=== Migrator Fstab Entry Diagnostic Tool ===")
    
    # Create a FstabManager directly
    fstab_path = "/etc/fstab"
    if os.path.exists(fstab_path):
        logger.info(f"Analyzing fstab file: {fstab_path}")
        
        # Read the raw file
        with open(fstab_path, 'r') as f:
            contents = f.readlines()
        
        logger.info(f"Raw fstab file has {len(contents)} lines")
        
        # Process directly with FstabEntry
        for i, line in enumerate(contents):
            if line.strip() and not line.strip().startswith('#'):
                logger.info(f"Line {i+1}: {line.strip()}")
                
                entry = FstabEntry(line)
                logger.info(f"  Processed as: {entry.fs_spec} -> {entry.mount_point} ({entry.fs_type})")
                logger.info(f"  Portable: {entry.is_portable}")
                logger.info(f"  Valid: {entry.is_valid}")
                
                # Check why a CIFS entry might not be portable
                if 'cifs' in entry.fs_type.lower() and not entry.is_portable:
                    logger.warning(f"CIFS entry not marked as portable!")
                    
                    # Apply the portable check manually
                    if any(fs in entry.fs_type.lower() for fs in ['nfs', 'cifs', 'smb', 'sshfs']):
                        logger.info("  Should be portable based on filesystem type")
                    
                    if entry.fs_spec.startswith('//') or ':' in entry.fs_spec:
                        logger.info("  Should be portable based on network path")
        
        # Now use the FstabManager
        logger.info("\nTesting with FstabManager...")
        manager = FstabManager(fstab_path)
        
        logger.info(f"FstabManager loaded {len(manager.entries)} entries")
        logger.info(f"FstabManager found {len(manager.portable_entries)} portable entries")
        
        # Check portable entries
        for i, entry in enumerate(manager.portable_entries):
            logger.info(f"Portable entry {i+1}: {entry.fs_spec} -> {entry.mount_point} ({entry.fs_type})")
        
        # Check specifically for CIFS entries
        cifs_entries = [e for e in manager.entries if 'cifs' in e.fs_type.lower()]
        logger.info(f"\nFound {len(cifs_entries)} CIFS entries in total")
        
        for i, entry in enumerate(cifs_entries):
            logger.info(f"CIFS entry {i+1}: {entry.fs_spec} -> {entry.mount_point}")
            logger.info(f"  Portable: {entry.is_portable}")
            
            if not entry.is_portable:
                logger.warning(f"  This CIFS entry was NOT marked as portable!")
    
    # Now test with the SystemConfigTracker
    logger.info("\nTesting with SystemConfigTracker...")
    tracker = SystemConfigTracker()
    
    # Force fstab processing
    tracker._process_fstab_entries()
    
    logger.info(f"SystemConfigTracker found {len(tracker.portable_fstab_entries)} portable entries")
    
    if tracker.has_portable_fstab_entries():
        for i, entry in enumerate(tracker.portable_fstab_entries):
            logger.info(f"Portable entry {i+1}: {entry.fs_spec} -> {entry.mount_point} ({entry.fs_type})")
    else:
        logger.warning("SystemConfigTracker did not find any portable fstab entries")

if __name__ == "__main__":
    analyze_fstab() 