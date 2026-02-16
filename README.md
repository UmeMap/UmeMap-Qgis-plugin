# UmeMap-Qgis-plugin

UmeMap layer management is a plugin which helps with styles for vector layers that come from a UmeMap server and form management.

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
4. Click **Browse** and locate the ZIP file (e.g., `deploy/UmeMap-0.6+20251020.zip`)
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