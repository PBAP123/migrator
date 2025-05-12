#!/usr/bin/env python3
from migrator.config_trackers.system_config import SystemConfigTracker
from migrator.utils.fstab import FstabManager

# Create the trackers
sys_tracker = SystemConfigTracker()

# Check if portable entries exist
print(f"Has portable fstab entries: {sys_tracker.has_portable_fstab_entries()}")

# Get the fstab manager and examine it
fm = sys_tracker.get_fstab_manager()
if fm:
    print("\nFound FstabManager:")
    print(f"  - Total entries: {len(fm.entries)}")
    print(f"  - Portable entries: {len(fm.get_portable_entries())}")
    
    # Print detailed info about portable entries
    portable = fm.get_portable_entries()
    if portable:
        print("\nPortable entries:")
        for entry in portable:
            print(f"  - {entry.device} -> {entry.mountpoint}")
    else:
        print("\nNo portable entries found!")
    
    # Check CIFS entries specifically
    cifs_entries = [e for e in fm.entries if e.fstype == 'cifs']
    print(f"\nCIFS entries detected: {len(cifs_entries)}")
    if cifs_entries:
        for entry in cifs_entries:
            print(f"  - {entry.device} -> {entry.mountpoint}")
            print(f"    Marked portable: {'Yes' if entry in portable else 'No'}")
else:
    print("No fstab manager created - critical error!")
