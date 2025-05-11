#!/usr/bin/env python3
"""
Direct runner for Migrator - helpful for development and troubleshooting.
This script allows you to run Migrator without going through the package installation.
"""

import os
import sys

# Add the src directory to the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(script_dir, 'src')
sys.path.insert(0, src_dir)

# Import and run the main function
from __main__ import main

if __name__ == "__main__":
    main() 