#!/usr/bin/env python3
"""
Test script for package mapper to verify mapping between apt and dnf
"""

import sys
import os
import logging
import json
from pathlib import Path

# Add migrator package to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'migrator')))

try:
    from src.migrator.package_managers.package_mapper import PackageMapper
except ImportError:
    print("Couldn't import PackageMapper, trying alternative import path...")
    try:
        # Adjust the path to where migrator is installed
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))
        from src.migrator.package_managers.package_mapper import PackageMapper
    except ImportError:
        print("Failed to import PackageMapper. Make sure the migrator package is in your Python path.")
        sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """Test the package mapper with common Debian packages"""
    print("Testing Package Mapper - apt to dnf conversion")
    print("-" * 60)
    
    # Create the mapper
    mapper = PackageMapper()
    
    # Define test packages - common Debian/Ubuntu packages
    test_packages = [
        "apt",
        "apt-utils",
        "build-essential",
        "git",
        "firefox",
        "chromium-browser",
        "libssl-dev",
        "python3-pip",
        "software-properties-common",
        "gnome-terminal",
        "vim",
        "nano",
        "curl",
        "wget",
        "htop",
        "ubuntu-restricted-extras",
        "synaptic",
        "gparted",
        "gcc"
    ]
    
    # Test mapping each package
    print("Package mapping results (apt -> dnf):")
    print(f"{'Package Name':<25} | {'Equivalent':<25} | {'Mapping Reason'}")
    print("-" * 75)
    
    for pkg in test_packages:
        equivalent, reason = mapper._get_equivalent_package_with_reason(pkg, 'apt', 'dnf')
        print(f"{pkg:<25} | {equivalent or 'None':<25} | {reason}")
    
    print("\nAdding a custom mapping for testing...")
    
    # Add a custom mapping
    mapper.create_custom_mapping("test-package", "apt", "test-package-fedora", "dnf")
    
    # Test the custom mapping
    equivalent, reason = mapper._get_equivalent_package_with_reason("test-package", 'apt', 'dnf')
    print(f"Custom mapping: test-package -> {equivalent} ({reason})")
    
    print("\nTest complete!")

if __name__ == "__main__":
    main() 