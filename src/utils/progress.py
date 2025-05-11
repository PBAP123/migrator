#!/usr/bin/env python3
"""
Progress tracking utilities for Migrator

This handles terminal progress bars and status updates for
long-running operations like backup and restore.
"""

import sys
import time
import threading
import logging
from typing import List, Dict, Any, Optional, Callable, Union
from enum import Enum

# Import tqdm for progress bars - we'll handle the import error if not installed
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    
logger = logging.getLogger(__name__)

class OperationType(Enum):
    """Types of operations that can be tracked"""
    BACKUP = "backup"
    RESTORE = "restore"
    PACKAGE_SCAN = "package_scan"
    CONFIG_SCAN = "config_scan"
    PACKAGE_INSTALL = "package_install"
    CONFIG_RESTORE = "config_restore"
    FSTAB_PROCESSING = "fstab_processing"
    GENERAL = "general"

class ProgressTracker:
    """Class to track and display progress of long-running operations"""
    
    def __init__(self, 
                operation_type: Union[str, OperationType], 
                total: int = 0, 
                desc: str = "",
                unit: str = "items",
                show_eta: bool = True,
                autostart: bool = True):
        """Initialize a progress tracker
        
        Args:
            operation_type: Type of operation being tracked (backup, restore, etc.)
            total: Total number of items to process (0 for indeterminate)
            desc: Description of the operation
            unit: Unit of items being processed (files, packages, etc.)
            show_eta: Whether to show estimated time remaining
            autostart: Whether to start the progress bar immediately
        """
        self.operation_type = operation_type.value if isinstance(operation_type, OperationType) else operation_type
        self.total = total
        self.desc = desc or f"Processing {self.operation_type}"
        self.unit = unit
        self.show_eta = show_eta
        self.current = 0
        self.status_text = ""
        self.active = False
        self.indeterminate = (total == 0)
        
        # For storing sub-operations
        self.sub_operations = []
        self.current_sub_operation = None
        
        # Progress bar object
        self.pbar = None
        
        # For indeterminate progress
        self.spinner_thread = None
        self.spinner_active = False
        self.spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self.spinner_idx = 0
        
        # Start if requested
        if autostart:
            self.start()
    
    def start(self) -> 'ProgressTracker':
        """Start the progress tracker"""
        self.active = True
        
        if TQDM_AVAILABLE and not self.indeterminate:
            # Create a tqdm progress bar
            self.pbar = tqdm(
                total=self.total,
                desc=self.desc,
                unit=self.unit,
                bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]'
            )
        elif self.indeterminate:
            # Start a spinner for indeterminate progress
            self._start_spinner()
        else:
            # Fallback when tqdm is not available
            print(f"{self.desc} (0/{self.total} {self.unit})")
        
        return self
    
    def _start_spinner(self) -> None:
        """Start a spinner for indeterminate progress"""
        self.spinner_active = True
        self.spinner_thread = threading.Thread(target=self._spinner_worker)
        self.spinner_thread.daemon = True
        self.spinner_thread.start()
    
    def _spinner_worker(self) -> None:
        """Worker function for the spinner thread"""
        while self.spinner_active:
            char = self.spinner_chars[self.spinner_idx % len(self.spinner_chars)]
            status = self.status_text or "Processing..."
            sys.stdout.write(f"\r{char} {self.desc}: {status}")
            sys.stdout.flush()
            self.spinner_idx += 1
            time.sleep(0.1)
            
    def stop_spinner(self) -> None:
        """Stop the spinner thread"""
        if self.spinner_active:
            self.spinner_active = False
            if self.spinner_thread:
                self.spinner_thread.join(timeout=0.5)
            # Clear the line
            sys.stdout.write("\r" + " " * 100 + "\r")
            sys.stdout.flush()
    
    def update(self, n: int = 1, status: str = "") -> None:
        """Update the progress tracker
        
        Args:
            n: Number of items to increment by
            status: Status text to display
        """
        if not self.active:
            return
            
        self.current += n
        
        if status:
            self.status_text = status
            
        if TQDM_AVAILABLE and self.pbar:
            self.pbar.update(n)
            if status:
                self.pbar.set_description(f"{self.desc} - {status}")
        elif self.indeterminate:
            # Status is shown by the spinner thread
            pass
        else:
            # Fallback when tqdm is not available
            percent = int(100 * self.current / self.total) if self.total > 0 else 0
            status_str = f" - {status}" if status else ""
            print(f"\r{self.desc}{status_str} ({self.current}/{self.total} {self.unit}, {percent}%)", end="")
    
    def set_description(self, desc: str) -> None:
        """Set the description text"""
        self.desc = desc
        if TQDM_AVAILABLE and self.pbar:
            self.pbar.set_description(desc)
    
    def set_postfix(self, **kwargs) -> None:
        """Set postfix text (key=value pairs after the bar)"""
        if TQDM_AVAILABLE and self.pbar:
            self.pbar.set_postfix(**kwargs)
    
    def start_sub_operation(self, desc: str, total: int = 0, unit: str = "items") -> 'ProgressTracker':
        """Start a sub-operation with its own progress tracking
        
        Args:
            desc: Description of the sub-operation
            total: Total number of items in the sub-operation
            unit: Unit of items being processed
            
        Returns:
            The sub-operation progress tracker
        """
        sub_tracker = ProgressTracker(
            operation_type=OperationType.GENERAL, 
            total=total,
            desc=desc,
            unit=unit,
            autostart=True
        )
        
        self.sub_operations.append(sub_tracker)
        self.current_sub_operation = sub_tracker
        return sub_tracker
    
    def close(self, status: str = "Complete") -> None:
        """Close the progress tracker
        
        Args:
            status: Final status text to display
        """
        # Close any active sub-operations
        if self.current_sub_operation and self.current_sub_operation.active:
            self.current_sub_operation.close()
            
        if not self.active:
            return
            
        self.active = False
        
        if TQDM_AVAILABLE and self.pbar:
            # Set final status
            if status:
                self.pbar.set_description(f"{self.desc} - {status}")
            # Close the progress bar
            self.pbar.close()
        elif self.indeterminate:
            # Stop the spinner
            self.stop_spinner()
            # Print final status
            print(f"{self.desc} - {status}")
        else:
            # Fallback when tqdm is not available
            percent = int(100 * self.current / self.total) if self.total > 0 else 0
            print(f"\r{self.desc} - {status} ({self.current}/{self.total} {self.unit}, {percent}%)")
    
    def __enter__(self) -> 'ProgressTracker':
        """Context manager enter method"""
        if not self.active:
            self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit method"""
        status = "Error" if exc_type else "Complete"
        self.close(status=status)


class MultiProgressTracker:
    """Manages multiple progress trackers for complex operations"""
    
    def __init__(self, overall_desc: str = "Operation progress", overall_total: int = 100):
        """Initialize multi-progress tracker
        
        Args:
            overall_desc: Description for the overall progress
            overall_total: Total steps for the overall progress (default: 100 for percentage)
        """
        self.trackers = {}
        self.active_tracker = None
        self.overall_tracker = ProgressTracker(
            operation_type=OperationType.GENERAL,
            total=overall_total,
            desc=overall_desc,
            autostart=False
        )
    
    def start_overall(self) -> None:
        """Start the overall progress tracker"""
        self.overall_tracker.start()
    
    def add_tracker(self, name: str, tracker: ProgressTracker) -> None:
        """Add a named tracker
        
        Args:
            name: Name to identify this tracker
            tracker: ProgressTracker instance
        """
        self.trackers[name] = tracker
    
    def create_tracker(self, name: str, operation_type: Union[str, OperationType], 
                      total: int = 0, desc: str = "", unit: str = "items", 
                      autostart: bool = False) -> ProgressTracker:
        """Create and add a new tracker
        
        Args:
            name: Name to identify this tracker
            operation_type: Type of operation
            total: Total number of items
            desc: Description text
            unit: Unit of items
            autostart: Whether to start immediately
            
        Returns:
            The created tracker
        """
        tracker = ProgressTracker(
            operation_type=operation_type,
            total=total,
            desc=desc,
            unit=unit,
            autostart=autostart
        )
        self.trackers[name] = tracker
        return tracker
    
    def get_tracker(self, name: str) -> Optional[ProgressTracker]:
        """Get a tracker by name
        
        Args:
            name: Name of the tracker
            
        Returns:
            The tracker or None if not found
        """
        return self.trackers.get(name)
    
    def activate_tracker(self, name: str) -> Optional[ProgressTracker]:
        """Activate a specific tracker and start it if not already started
        
        Args:
            name: Name of the tracker to activate
            
        Returns:
            The activated tracker or None if not found
        """
        tracker = self.trackers.get(name)
        if tracker:
            self.active_tracker = tracker
            if not tracker.active:
                tracker.start()
        return tracker
    
    def update_overall(self, n: int = 1, status: str = "") -> None:
        """Update the overall progress
        
        Args:
            n: Number of steps to increment
            status: Status text
        """
        if self.overall_tracker:
            self.overall_tracker.update(n, status)
    
    def update_active(self, n: int = 1, status: str = "") -> None:
        """Update the active tracker
        
        Args:
            n: Number of items to increment
            status: Status text
        """
        if self.active_tracker:
            self.active_tracker.update(n, status)
    
    def update_tracker(self, name: str, n: int = 1, status: str = "") -> None:
        """Update a specific tracker
        
        Args:
            name: Name of the tracker
            n: Number of items to increment
            status: Status text
        """
        tracker = self.trackers.get(name)
        if tracker:
            tracker.update(n, status)
    
    def close_tracker(self, name: str, status: str = "Complete") -> None:
        """Close a specific tracker
        
        Args:
            name: Name of the tracker
            status: Final status text
        """
        tracker = self.trackers.get(name)
        if tracker:
            tracker.close(status)
            # If this was the active tracker, set active to None
            if self.active_tracker == tracker:
                self.active_tracker = None
    
    def close_all(self, overall_status: str = "Operation complete") -> None:
        """Close all trackers including the overall tracker
        
        Args:
            overall_status: Final status for the overall tracker
        """
        # Close all individual trackers
        for name, tracker in self.trackers.items():
            if tracker.active:
                tracker.close()
        
        # Close the overall tracker
        if self.overall_tracker and self.overall_tracker.active:
            self.overall_tracker.close(status=overall_status)
        
        self.active_tracker = None 