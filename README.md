# easyeda_footprint_wizard_kicad

A footprint wizard implementation of the easyeda2kicad-project. Aims to suport 3d model import and footprint generation from a LCSC part number without the "hassle" of calling a CLI tool.

# Installation

for now this wizard needs easyeda2kicad installed as a system lib. It can be installed using pip as described below.

After installation, download this folder from here and paste it inside one of the /plugins paths kicad searches. The paths can be found by looking inside the footprint editor -> New Footprint From Wizard -> Messages dialog. 

On windows, one such path would be `%APPDATA%\kicad\[version]\plugins`. Make sure the __init__.py and the easyEdaWizard.py have been pasted inside a new folder in this directory. 

# Usage

After installation, a new "EasyEDA" wizard should be in the list of footprint wizards. Give it an LCSC number and watch it go :)

# Install easyeda2kicad

For now, install easyeda2kicad using pip

```
pip install easyeda2kicad
```

## Windows 

The Kicad python installation actually ships with pip, so to install easyeda2kicad on windows, use the pip module inside the python scripting ui. Type

```
import pip
pip.main(["install", "easyeda2kicad"])
```

This should take care of installing easyeda2kicad in the right path. 


