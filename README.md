# UmeMap-Qgis-plugin
UmeMap layer managment is a plugin which helps with styles for vector layers that come from a UmeMap server and form management

# Build steps for the plugin

## Preparations
To be able to compile and run the plugin in QGIS you need to install pb_tool, PyQt5, setuptools:
```bash
pip install pb_tool pyqt5 setuptools
```

## Compiling

1. Open a terminal and go to the root folder of the plugin project (e.g.  [src\UmeMap](\src\UmeMap))
2. Run the following command to build and copy the plugin:
```powershell
.\build.ps1
```

## Install in your local QGIS installation
1. Open QGIS
2. Go to Plugins > Manage and Install Plugins > Install from ZIP
3. Locate the zip file called e.g. [/deploy/UmeMap-0.6+20251020.zip](/deploy/UmeMap-0.5+20251013.zip) and install it.