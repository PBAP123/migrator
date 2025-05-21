# Package Managers

This directory contains implementations for various Linux package managers and cross-distribution package mapping functionality.

## Package Manager Support

Migrator supports multiple package managers:

- `apt` - For Debian/Ubuntu-based distributions
- `dnf` - For Fedora/RHEL-based distributions
- `pacman` - For Arch Linux-based distributions
- `snap` - For Canonical's Snap packages (cross-distribution)
- `flatpak` - For Flatpak packages (cross-distribution)
- `appimage` - For AppImage applications (cross-distribution)

## Cross-Distribution Package Equivalence Detection

A key feature of Migrator is its ability to detect equivalent packages across different package managers. For example, if you backup a system with `apt` packages (Ubuntu) and restore on a system with `dnf` packages (Fedora), Migrator can find the equivalent packages.

### How it Works

The package mapping system uses several strategies to find equivalent packages:

1. **Built-in mappings**: Common packages are mapped directly (e.g., `libreoffice` in apt → `libreoffice` in dnf)
2. **Pattern matching**: Common package naming patterns are recognized (e.g., `python3-dev` in apt → `python3-devel` in dnf)
3. **Name normalization**: Package names are normalized to account for different naming conventions
4. **Similar package search**: When direct mappings fail, Migrator searches for similar package names

### Customizing Package Mappings

You can customize the package equivalence mappings by editing the JSON file at:

```
~/.config/migrator/package_mappings.json
```

The file structure is:

```json
{
  "_comment": "Add your custom package mappings here",
  "package_name": {
    "apt": "apt_package_name",
    "dnf": "dnf_package_name",
    "pacman": "pacman_package_name"
  },
  "another_package": {
    "apt": "apt_name",
    "dnf": "dnf_name",
    "pacman": "pacman_name"
  }
}
```

You can edit this file directly, or use the command:

```
migrator edit-mappings
```

### Adding Custom Mappings

To add a new mapping:

1. Find the package name in your source distribution
2. Find the equivalent package name in your target distribution
3. Add an entry to the `package_mappings.json` file

For example, if you know that `network-manager-gnome` in Debian/Ubuntu is equivalent to `network-manager-applet` in Fedora, you can add:

```json
"network-manager-gnome": {
  "apt": "network-manager-gnome",
  "dnf": "network-manager-applet"
}
```

This ensures the correct package will be found when migrating between distributions. 