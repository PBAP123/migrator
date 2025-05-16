# Context Primers for Migrator

This directory contains context primer documents for the Migrator project. These documents are designed to help developers and AI assistants understand the purpose, structure, and relationships between different parts of the codebase.

## Purpose

These context primers serve as internal documentation for developers and LLMs to:
1. Quickly understand the purpose of each directory/component
2. Identify key files and their responsibilities
3. Understand architectural patterns used
4. See how different parts of the codebase relate to each other

## Available Primers

- [Root Directory](root.md) - Overview of the main project files
- [Source Directory](src.md) - The source code package structure
- [Migrator Package](src_migrator.md) - The core implementation package
- [Utils Directory](src_migrator_utils.md) - Utility functions and helpers
- [Config Trackers](src_migrator_config_trackers.md) - Configuration tracking modules
- [Package Managers](src_migrator_package_managers.md) - Package management modules
- [Virtual Environment](venv.md) - Python virtual environment

## How to Use

When making changes to the codebase, refer to these primers to understand:
- Where new functionality should be added
- Which existing components might be affected by your changes
- The design patterns and architectural approaches to follow
- How to maintain consistency with the existing codebase

## Maintenance

These primers should be updated when significant changes are made to the structure or functionality of the codebase. Keep them concise and focused on the high-level organization rather than implementation details that might change frequently. 