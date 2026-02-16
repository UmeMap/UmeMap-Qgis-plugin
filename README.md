# UmeMap-Qgis-plugin

UmeMap layer management is a QGIS plugin for managing styles and configurations for vector layers from UmeMap WFS servers, and for browsing and adding WFS layers via an integrated Layer Browser.

## Features

- **Layer Browser** - Dockable panel for browsing WFS layers organized by keyword hierarchy, with search, filtering and drag-and-drop support
- **Style Management** - Automatically load and save QML styles from/to UmeMap servers
- **Authentication** - Integrates with QGIS authentication manager for secure WFS connections

## Requirements

- **QGIS:** Version 3.0 or later
- **Python:** 3.x (included with QGIS)

---

# Build & Installation Guide

## Prerequisites

Install the required Python packages:

```bash
pip install pb_tool pyqt5 setuptools
```

> **Note:** If you're using QGIS's bundled Python, run pip from the OSGeo4W Shell (Windows) or use QGIS's Python environment.

---

## Building the Plugin

### Windows (PowerShell)

1. Open PowerShell and navigate to the plugin source folder:
   ```powershell
   cd src\UmeMap
   ```

2. Run the build script:
   ```powershell
   .\build.ps1
   ```

3. The ZIP file will be created in the `deploy` folder:
   ```
   deploy\UmeMap-{version}.zip
   ```

### Linux/macOS (Make)

1. Open a terminal and navigate to the plugin source folder:
   ```bash
   cd src/UmeMap
   ```

2. Compile resources and create the package:
   ```bash
   make compile
   make package
   ```

3. The ZIP file will be created in the current directory.

---

## Installing in QGIS

### Method 1: Install from ZIP (Recommended)

1. Open **QGIS**
2. Go to **Plugins** → **Manage and Install Plugins...**
3. Click the **Install from ZIP** tab
4. Click **Browse** and locate the ZIP file (e.g., `deploy/UmeMap-0.7+20260206.zip`)
5. Click **Install Plugin**
6. The plugin will appear under **Plugins** → **UmeMap layer management**

### Method 2: Manual Installation

1. Locate your QGIS plugins folder:
   - **Windows:** `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
   - **Linux:** `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
   - **macOS:** `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`

2. Extract the ZIP file contents to the plugins folder (the `UmeMap` folder should be directly inside `plugins`)

3. Restart QGIS

4. Go to **Plugins** → **Manage and Install Plugins...**

5. Find **UmeMap layer management** in the list and enable it

---

## Usage

### Layer Browser

1. Open via **Plugins** → **UmeMap layer management** → **Layer Browser** (or the toolbar icon)
2. Click the **+** button to add a WFS source (URL + optional authentication)
3. The panel displays layers organized in folders based on WFS keywords
4. Use the search bar to filter layers
5. Double-click or drag-and-drop a layer to add it to the map

### Style Management

- When a WFS layer from a UmeMap server is added, styles are automatically loaded
- Right-click any UmeMap WFS layer → **Save Style To UmeMap** to save the current style back to the server

---

## Project Structure

```
src/UmeMap/
├── plugin.py                           # Main plugin class
├── core/                               # Shared core logic (no UI)
│   ├── api_client.py                   # UmeMap server API
│   ├── auth_manager.py                 # QGIS auth integration
│   └── wfs_utils.py                    # WFS URI parsing
├── features/
│   ├── layer_browser/                  # WFS Layer Browser feature
│   │   ├── browser_dock.py             # Dockable browser panel
│   │   ├── wfs_parser.py               # WFS GetCapabilities parser
│   │   ├── wfs_source.py               # WFS source data class
│   │   ├── layer_tree_model.py         # Tree model with keyword hierarchy
│   │   ├── settings_manager.py         # Persistent settings
│   │   └── source_dialog.py            # Add/edit WFS source dialog
│   └── style_manager/                  # Style management feature
│       ├── style_service.py            # Save/load styles
│       └── style_actions.py            # Context menu integration
├── ui/                                 # UI components
│   ├── dialogs.py                      # Dialog classes
│   └── utils.py                        # UI helpers
└── icons/                              # SVG icons
```

---

## Development

### Quick Deploy

During development, you can quick-deploy the plugin directly to your QGIS plugins folder:

```powershell
cd src\UmeMap
.\build.ps1
# Select [1] Quick deploy to QGIS
```

### Plugin Reloader

Install **Plugin Reloader** in QGIS (Plugins > Manage and Install Plugins > All > search "Plugin Reloader") to reload UmeMap without restarting QGIS. After a quick deploy, just click the reload button in the toolbar.

> **Note:** Changes to `metadata.txt` and `__init__.py` require a full QGIS restart.

---

## Verifying Installation

After installation, you should see:
- A new menu item under **Plugins** → **UmeMap layer management**
- A toolbar icon for the **Layer Browser** panel
- Right-click on any WFS vector layer → **Save Style To UmeMap** option

---

## Troubleshooting

### Plugin not showing up
- Make sure the plugin is enabled in **Plugins** → **Manage and Install Plugins** → **Installed**
- Check that the folder structure is correct: `plugins/UmeMap/` (not `plugins/UmeMap/UmeMap/`)

### Build errors
- Ensure `pb_tool` is installed: `pip show pb_tool`
- On Windows, run PowerShell as Administrator if you get permission errors

### Missing dependencies
- Install requests if not present: `pip install requests`
