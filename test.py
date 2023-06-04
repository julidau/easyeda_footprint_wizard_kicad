import easyeda2kicad



from easyeda2kicad import __version__
from easyeda2kicad.easyeda.easyeda_api import EasyedaApi
from easyeda2kicad.easyeda.easyeda_importer import (
    Easyeda3dModelImporter,
    EasyedaFootprintImporter,
    EasyedaSymbolImporter,
)

from easyeda2kicad.kicad.export_kicad_footprint import ExporterFootprintKicad

# fetch cad data
lcsc_id = "C194380"
api = EasyedaApi()
cad_data = api.get_cad_data_of_component(lcsc_id=lcsc_id)

print(cad_data)

def export():
    importer = EasyedaFootprintImporter(easyeda_cp_cad_data=cad_data)
    easyeda_footprint = importer.get_footprint()

    # is_id_already_in_footprint_lib = fp_already_in_footprint_lib(
    #     lib_path=f"{arguments['output']}.pretty",
    #     package_name=easyeda_footprint.info.name,
    # )
    
    # if not arguments["overwrite"] and is_id_already_in_footprint_lib:
    #     logging.error("Use --overwrite to replace the older footprint lib")
    #     return 1

    ki_footprint = ExporterFootprintKicad(footprint=easyeda_footprint)
    footprint_filename = f"{easyeda_footprint.info.name}.kicad_mod"
    footprint_path = f"{arguments['output']}.pretty"
    model_3d_path = f"{arguments['output']}.3dshapes".replace("\\", "/").replace(
        "./", "/"
    )

    if arguments.get("use_default_folder"):
        model_3d_path = "${EASYEDA2KICAD}/easyeda2kicad.3dshapes"
    if arguments["project_relative"]:
        model_3d_path = "${KIPRJMOD}" + model_3d_path

    ki_footprint.export(
        footprint_full_path=f"{footprint_path}/{footprint_filename}",
        model_3d_path=model_3d_path,
    )