# easyeda_footprint_wizard_kicad

**This plugin is currently only tested to work with kicad v7.0.5 and python 3.11. Is is know to not work with kicad v6 due to an API incompatibility. See #2**

A footprint wizard implementation of the easyeda2kicad-project. Aims to suport 3d model import and footprint generation from a LCSC part number without the "hassle" of calling a CLI tool.

# Usage

After installation, a new "EasyEDA" wizard should be in the list of footprint wizards. Give it an LCSC number and watch it go :)

![demo](/doc/demo.mp4)

# Installation

This package can be installed using the Kicad Content Manager. To do this, download the `package.zip` from the releases tab. Then start the Kicad Plugin Manager, choose `Install from File` and select the downloaded zip file. If all goes well, then the wizard should show up in the Footprint editor now. 

# Manual Installation

This wizard needs easyeda2kicad installed as a system lib. It can be installed using pip as described below.

You can install easyeda2kicad using pip

```
pip install easyeda2kicad
```

After installation, download this source folder and paste it inside one of the /plugins paths kicad searches. The paths can be found by looking inside the `footprint editor -> New Footprint From Wizard -> Messages` dialog. 

On Windows, one such path would be `%APPDATA%\kicad\[version]\plugins`. Make sure the __init__.py and the easyEdaWizard.py have been pasted inside a new folder in this directory. 

## Windows 

The Kicad python installation actually ships with pip, so to install easyeda2kicad on windows, use the pip module inside the python scripting ui. Type

```
import pip
pip.main(["install", "easyeda2kicad"])
```

This should take care of installing easyeda2kicad in the right path. It can fail due to insufficient permissions, in this case installing the plugin using the Content Manager is preferred. 


