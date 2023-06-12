import pcbnew
import os
from expandvars import expandvars,UnboundVariable


kicad_version = pcbnew.Version()
kicad_major = int(kicad_version.split(".")[0]) 
is_kicad_6 = kicad_major == 6
is_kicad_7 = kicad_major == 7

if not is_kicad_6 and not is_kicad_6:
    raise ImportError(f"unsupported kicad version {kicad_version}")

from FootprintWizardBase_v6 import FootprintWizard as FootprintWizardV6
from FootprintWizardBase_v7 import FootprintWizard as FootprintWizardV7

# why am i doing this junk you ask ? Well, stickytape requires all imports to be present, 
# and i'm pretty sure conditional imports are not supported. So lets use this workaround :)
base = FootprintWizardV6 if is_kicad_6 else FootprintWizardV7 if is_kicad_7 else None

from easyeda2kicad.easyeda.easyeda_api import EasyedaApi
from easyeda2kicad.easyeda.easyeda_importer import EasyedaFootprintImporter, Easyeda3dModelImporter
from easyeda2kicad.kicad.export_kicad_footprint import *
from easyeda2kicad.kicad.export_kicad_3d_model import Exporter3dModelKicad

class SimpleBB:
    def __init__(self):
        self.upperleft = None
    
    def addXY(self, x, y):
        if not self.upperleft:
            self.upperleft = pcbnew.VECTOR2I(x,y)
            return

        self.upperleft.x = min(self.upperleft.x, x)
        self.upperleft.y = min(self.upperleft.y, y)

    def addPt(self, pt):
        self.addXY(pt.x, pt.y)

class EasyedaWizard(base):
    def __init__(self):
        base.__init__(self)

        self.api = EasyedaApi()

    def GetName(self):
        return "EasyEDA"

    def GetDescription(self):
        return "EasyEDA import"
   
    def GenerateParameterList(self):
        # FIXME: remove default value 
        # custom pad test : C80192
        # usb c port (mixed pads): C2988369
        self.AddParam("Part", "LCSC Number", self.uString, "C80192")
        
        self.AddParam("Part", "3d Model Path", self.uString, "${KIPRJMOD}/3dshapes/")
        self.AddParam("Part", "Import 3d Model", self.uBool, False)

    @property
    def part(self):
        return self.parameters['Part']

    def checkPartNumber(self):
        number = self.GetParam("Part", "LCSC Number")

        if not number.value.startswith("C"):
            number.AddError("lcsc number should start with letter C")
            return
        
        # try to fetch cad data
        self.cad_data = self.api.get_cad_data_of_component(number.value)
        if not self.cad_data:
            number.AddError("part number not found (no cad data or invalid number)")
            return
        
        try:
            importer = EasyedaFootprintImporter(easyeda_cp_cad_data=self.cad_data)
            self.input = importer.get_footprint()
        except Exception as e:
            number.AddError("part has no footprint: {}".format(e))
    

    def CheckParameters(self):
        # check for valid part number
        self.checkPartNumber()

        if self.GetParam("Part", "Import 3d Model").value:
            try:
                self.model3d_outpath = self.GetParam("Part", "3d Model Path").value
                self.model3d_outpath_expanded = expandvars(self.model3d_outpath, nounset=True)

            except UnboundVariable as e:
                errstr = f"could not expand some environment variables in path: {e}"
                if  "KIPRJMOD" in str(e):
                    errstr = "KIPRJMOD not set. Pcbnew must be started once, otherwise path is not set."

                self.GetParam("Part", "3d Model Path").AddError(errstr)

                self.GetParam("Part", "Import 3d Model").AddError(f"Cannot download 3d model, model download path not found.")
        
            if not self.input.model_3d:
                # this model has no 3d shape
                self.GetParam("Part", "Import 3d Model").AddError(f"footprint has no 3d model associated")
                return

    def GetValue(self):
        return "EasyEDA-{num}-{type}-{name}".format(
            num=self.part["LCSC Number"],
            type=self.input.info.fp_type,
            name=self.input.info.name
        )
    
    def SetModule3DModel(self):
        self.model_3d = None

        if not self.GetParam("Part", "Import 3d Model").value:
            # user did not want 3d model import, so dont
            return
    
        self.input.model_3d.convert_to_mm()

        #print("downloading 3d model...")

        exporter = Exporter3dModelKicad(
            model_3d=Easyeda3dModelImporter(
                easyeda_cp_cad_data=self.cad_data, download_raw_3d_model=True
            ).output
        )

        #exporter.export(lib_path=arguments["output"])
        if exporter.output:
            self.model3d_filepath = os.path.join(self.model3d_outpath, exporter.output.name + ".wrl")
            self.model3d_filepath_expanded = expandvars(self.model3d_filepath, nounset=True)

            # create target dir if not exists
            os.makedirs(self.model3d_outpath_expanded, exist_ok=True)

            # create and write output 3d file
            with open(
                file=self.model3d_filepath_expanded,
                mode="w",
                encoding="utf-8",
            ) as my_lib:
                my_lib.write(exporter.output.raw_wrl)

            #print(f"downloaded and exported model to {outpath}")

            # setup 3d model for footprint
            self.model_3d = pcbnew.FP_3DMODEL()
            self.model_3d.m_Filename = self.model3d_filepath
            self.model_3d.m_Show = True

    def UpdateAndAdd3dModule(self):
        # Add 3d model to footprint after footprint generation to make sure bb is converted and valid
        if not self.model_3d:
            return
        
        footprintmodel = self.input.model_3d

        # make sure roation angles are clamped to 0-360
        self.model_3d.m_Rotation = pcbnew.VECTOR3D(*map(lambda x: (360 - x) % 360, [
            footprintmodel.rotation.x, 
            footprintmodel.rotation.y, 
            footprintmodel.rotation.z
        ])) 

        self.model_3d.m_Offset = pcbnew.VECTOR3D(
            round(footprintmodel.translation.x - self.input.bbox.x, 2),
            round(-footprintmodel.translation.y + self.input.bbox.y, 2),
            0
            # NOTE: z translation seems to be incorrect from my testing, so hardcode to zero for now
            #footprintmodel.translation.z
        )

        self.module.Add3DModel(self.model_3d)

    def BuildThisFootprint(self):
        # Convert dimension from easyeda to kicad
        self.input.bbox.convert_to_mm()

        for fields in (
            self.input.pads,
            self.input.tracks,
            self.input.holes,
            self.input.circles,
            self.input.rectangles,
            self.input.texts,
        ):
            for field in fields:
                field.convert_to_mm()


        # For pads
        pad_shapes = {
            "ELLIPSE":  pcbnew.PAD_SHAPE_CIRCLE,
            "RECT": pcbnew.PAD_SHAPE_RECT,
            "OVAL": pcbnew.PAD_SHAPE_OVAL,
            "POLYGON": pcbnew.PAD_SHAPE_CUSTOM,
        }

        # layer set for vias on back copper
        backvia_layer_set = pcbnew.LSET()
        backvia_layer_set.AddLayer(pcbnew.B_Cu)
        backvia_layer_set.AddLayer(pcbnew.B_Mask)
        backvia_layer_set.AddLayer(pcbnew.B_Paste)

        # copied from easyeda2kicad layer set
        pad_layers = {
            # smd vias
            1: pcbnew.PAD.SMDMask(), # smdmask is smd pad for front copper
            2: backvia_layer_set,
            # drawings
            3: pcbnew.F_SilkS,
            13: pcbnew.F_Fab,
            15: pcbnew.Dwgs_User,
        }

        layers = {
            1: pcbnew.F_Cu, 
            2: pcbnew.B_Cu,
            3: pcbnew.F_SilkS,
            4: pcbnew.B_SilkS,
            5: pcbnew.F_Paste,
            6: pcbnew.B_Paste,
            7: pcbnew.F_Mask,
            8: pcbnew.B_Mask,
            10: pcbnew.Edge_Cuts,
            11: pcbnew.Edge_Cuts,
            12: pcbnew.Cmts_User,
            13: pcbnew.F_Fab,
            14: pcbnew.B_Fab,
            15: pcbnew.Dwgs_User,
            101: pcbnew.F_Fab,
        }

        # small helper functions
        get_or = lambda d,k: d[k] if k in d else None
        mmi = lambda x: pcbnew.FromMM(x)
        
        # use different size types depending on kicad version
        if is_kicad_6:
            sizexy = lambda x,y: pcbnew.wxSize(mmi(x), mmi(y))

            relposxy = lambda x,y: pcbnew.wxPoint(mmi(x), mmi(y))
            posxy = lambda x,y: relposxy(x-self.input.bbox.x, y-self.input.bbox.y)
        elif is_kicad_7:
            sizexy = lambda x,y: pcbnew.VECTOR2I(mmi(x), mmi(y))
            
            relposxy = sizexy
            posxy = lambda x,y: sizexy(x-self.input.bbox.x, y - self.input.bbox.y)
        else: 
            raise RuntimeError("unsupported Kicad Version (5 or lower)")

        for ee_pad in self.input.pads:
            shape = get_or(pad_shapes, ee_pad.shape) or pcbnew.PAD_SHAPE_CUSTOM

            if ee_pad.hole_radius > 0:
                # PAD with hole, figure out drill size
                pad = pcbnew.PAD(self.module)
                pad.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
                pad.SetLayerSet(pad.PTHMask())
            
                hole_w = 2* ee_pad.hole_radius
                hole_h = hole_w

                # find out if drill is oval 
                # and find drill pos and dimensions
                if ee_pad.hole_length and float(ee_pad.hole_length) != 0:
                    hole_h = ee_pad.hole_radius*2 
                    hole_w = ee_pad.hole_length

                    max_distance_hole = max(hole_w, hole_h)
                    pos_0 = ee_pad.height - max_distance_hole
                    pos_90 = ee_pad.width - max_distance_hole

                    max_distance = max(pos_0, pos_90)

                    if max_distance == pos_0:
                        hole_w, hole_h = hole_h, hole_w

                # add pad to module
                pad.SetDrillSize(sizexy(hole_w, hole_h))
            else:
                # SMD pad
                pad = pcbnew.PAD(self.module)
                pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
                pad.SetLayerSet(get_or(pad_layers, ee_pad.layer_id) or pad.SMDMask())

            point_list = [fp_to_ki(point) for point in ee_pad.points.split(" ")]

            if shape == pcbnew.PAD_SHAPE_CUSTOM:
                if len(point_list) <= 0:
                    print("PAD: custom shape has no points: ", ee_pad.number)
                    continue
                
                if is_kicad_7:
                    polygon = pcbnew.VECTOR_VECTOR2I()
                else:
                    polygon = pcbnew.wxPoint_Vector()

                for i in range(0, len(point_list), 2):
                    polygon.append(relposxy(point_list[i]-ee_pad.center_x,point_list[i+1]-ee_pad.center_y))


                # add polygon as custom shape
                pad.AddPrimitivePoly(polygon,0,True)

                # set base shape size to 0,0
                pad.SetSize(sizexy(0,0))
            else:
                pad.SetSize(sizexy(max(ee_pad.width, 0.01), max(ee_pad.height, 0.01)))

                # easyeda footprints with custom shapes seem to contain the  
                # pretransformed points.
                # rotation should therefore only be set for non-custom pad shapes
                pad.SetOrientationDegrees(angle_to_ki(ee_pad.rotation))

            pad.SetShape(shape)
            
            # normalize pad name
            pinname = ee_pad.number
            if "(" in pinname and ")" in pinname:
                pinname = pinname.split("(")[1].split(")")[0]

            pad.SetName(pinname)
            # Pos0 ?? must be set otherwise all pads will have 0,0 positions AFTER import to footprint editor 
            pad.SetPos0(posxy(ee_pad.center_x, ee_pad.center_y))
            pad.SetPosition(posxy(ee_pad.center_x, ee_pad.center_y))
            
            self.module.Add(pad)
#            print("added pad: {} {} {} {}".format(ee_pad.number, ee_pad.center_x, ee_pad.center_y, ee_pad.shape))
#            print(f"pos: {ee_pad.center_x} {ee_pad.center_y}")
    
        for ee_hole in self.input.holes:
            # holes are NPT pads with size == drillsize and circular
            pad = pcbnew.PAD(self.module)
            pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)

            pad.SetPos0(posxy(ee_hole.center_x, ee_hole.center_y))
            pad.SetPosition(pad.GetPos0())

            pad.SetDrillShape(pcbnew.PAD_DRILL_SHAPE_CIRCLE)
            pad.SetDrillSize(sizexy(ee_hole.radius*2, ee_hole.radius*2))

            pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
            pad.SetSize(pad.GetDrillSize())
            pad.SetLayerSet(pad.UnplatedHoleMask())
            self.module.Add(pad)

        # shapes
        self.draw.TransformTranslate(mmi(-self.input.bbox.x), mmi(-self.input.bbox.y))
        
        bb = SimpleBB()

        # For rectangles
        for ee_rectangle in self.input.rectangles:
            self.draw.SetLayer(get_or(pad_layers, ee_rectangle.layer_id) or pcbnew.F_Fab)
            self.draw.SetLineThickness(mmi(max(ee_rectangle.stroke_width, 0.01)))

            self.draw.Box(ee_rectangle.x, ee_rectangle.y, ee_rectangle.width, ee_rectangle.height)
    
        # "Tracks" (probably lines ? )
        for ee_track in self.input.tracks:
            self.draw.SetLayer(get_or(pad_layers, ee_track.layer_id) or pcbnew.F_Fab)
            self.draw.SetLineThickness(mmi(max(ee_track.stroke_width, 0.01)))

            # Generate line
            point_list = [fp_to_ki(point) for point in ee_track.points.split(" ")]
            point_list = [sizexy(point_list[i], point_list[i+1]) for i in range(0, len(point_list), 2)]
            list(map(bb.addPt, point_list))

            self.draw.Polyline(point_list)

        # For circles
        for ee_circle in self.input.circles:
            self.draw.SetLayer(get_or(pad_layers, ee_circle.layer_id) or pcbnew.F_Fab)
            
            # fill circles with line thickness ~= 0
            filled = ee_circle.stroke_width <= 0.01
            if not filled:
                self.draw.SetLineThickness(mmi(ee_circle.stroke_width))

            bb.addPt(sizexy(ee_circle.cx - ee_circle.radius, ee_circle.cy + ee_circle.radius))
            self.draw.Circle(mmi(ee_circle.cx), mmi(ee_circle.cy), mmi(ee_circle.radius), filled=filled)

        # For arcs
        for ee_arc in self.input.arcs:
            # FIXME: implement ARCs
            continue

            arc_path = (
                ee_arc.path.replace(",", " ").replace("M ", "M").replace("A ", "A")
            )


            start_x, start_y = arc_path.split("A")[0][1:].split(" ", 1)
            start_x = fp_to_ki(start_x) - self.input.bbox.x
            start_y = fp_to_ki(start_y) - self.input.bbox.y

            arc_parameters = arc_path.split("A")[1].replace("  ", " ")
            (
                svg_rx,
                svg_ry,
                x_axis_rotation,
                large_arc,
                sweep,
                end_x,
                end_y,
            ) = arc_parameters.split(" ", 6)
            rx, ry = rotate(fp_to_ki(svg_rx), fp_to_ki(svg_ry), 0)

            end_x = fp_to_ki(end_x) - self.input.bbox.x
            end_y = fp_to_ki(end_y) - self.input.bbox.y
            if ry != 0:
                cx, cy, extent = compute_arc(
                    start_x,
                    start_y,
                    rx,
                    ry,
                    float(x_axis_rotation),
                    large_arc == "1",
                    sweep == "1",
                    end_x,
                    end_y,
                )
            else:
                cx = 0.0
                cy = 0.0
                extent = 0.0

            ki_arc = KiFootprintArc(
                start_x=cx,
                start_y=cy,
                end_x=end_x,
                end_y=end_y,
                angle=extent,
                layers=KI_LAYERS[ee_arc.layer_id]
                if ee_arc.layer_id in KI_LAYERS
                else "F.Fab",
                stroke_width=max(fp_to_ki(ee_arc.stroke_width), 0.01),
            )
            self.output.arcs.append(ki_arc)

        # For texts
        for ee_text in self.input.texts:
            text = pcbnew.FP_TEXT(self.module)
            text.SetPos0(posxy(ee_text.center_x, ee_text.center_y))
            text.SetPosition(text.GetPos0())
            text.SetLayer(get_or(layers, ee_text.layer_id) or pcbnew.F_Fab)
            
            if ee_text.type == "N":
                # rebind slik to fab if type is "N" ? 
                text.SetLayer(get_or({pcbnew.F_SilkS: pcbnew.F_Fab, pcbnew.B_SilkS: pcbnew.B_Fab}, text.GetLayer()) or text.GetLayer())
            
            if pcbnew.IsBackLayer(ee_text.GetLayer()):
                # mirror text on bottom layers
                text.SetMirrored(True)

            text.SetTextSize(mmi(max(ee_text.font_size, 1)))
            text.SetTextThickness(mmi(max(ee_text.stroke_width, 0.01)))
            text.SetVisible(bool(ee_text.is_displayed))
            text.SetTextAngleDegrees(ee_text.rotation)

            text.SetText(ee_text.text)

            self.module.Add(text)    
        
        # hide the default value text 
        self.module.Value().SetVisible(False)
        
        # set reference text to be above footprint shapes
        if bb.upperleft:
            self.module.Reference().SetPos0(self.draw.TransformPoint(bb.upperleft.x, bb.upperleft.y))
            self.module.Reference().SetPosition(self.module.Reference().GetPos0())
            if is_kicad_7:
                self.module.Reference().SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_BOTTOM)
            elif is_kicad_6:
                self.module.Reference().SetVertJustify(pcbnew.GR_TEXT_VJUSTIFY_BOTTOM)

        # set LCSC number as description
        number = self.GetParam("Part", "LCSC Number").value
        self.module.SetDescription(number)

        # Add 3d model if defined and requested
        self.UpdateAndAdd3dModule()

# register singleton
EasyedaWizard().register()
