from FootprintWizardBase import FootprintWizard
import pcbnew

from easyeda2kicad.easyeda.easyeda_api import EasyedaApi
from easyeda2kicad.easyeda.easyeda_importer import EasyedaFootprintImporter
from easyeda2kicad.kicad.export_kicad_footprint import *

class EasyedaWizard(FootprintWizard):
    def __init__(self):
        FootprintWizard.__init__(self)

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
        
        self.AddParam("Part", "Import 3d Model", self.uBool, True)

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

    def GetValue(self):
        return "EasyEDA-{num}-{type}-{name}".format(
            num=self.part["LCSC Number"],
            type=self.input.info.fp_type,
            name=self.input.info.name
        )
    
    def SetModule3DModel(self):
        
        if not self.GetParam("Part", "Import 3d Model").value:
            # user did not want 3d model import, so dont
            return
        
        if not self.input.model_3d:
            # this model has no 3d shape
            return
    
        self.input.model_3d.convert_to_mm()

        # if self.input.model_3d.translation.z != 0:
        #     self.input.model_3d.translation.z -= 1
        # ki_3d_model_info = Ki3dModel(
        #     name=self.input.model_3d.name,
        #     translation=Ki3dModelBase(
        #         x=round((self.input.model_3d.translation.x - self.input.bbox.x), 2),
        #         y=-round(
        #             (self.input.model_3d.translation.y - self.input.bbox.y), 2
        #         ),
        #         z=-round(self.input.model_3d.translation.z, 2),
        #     ),
        #     rotation=Ki3dModelBase(
        #         x=(360 - self.input.model_3d.rotation.x) % 360,
        #         y=(360 - self.input.model_3d.rotation.y) % 360,
        #         z=(360 - self.input.model_3d.rotation.z) % 360,
        #     ),
        #     raw_wrl=None,
        # )
        # print(ki_3d_model_info)

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
        layers = {
            # smd vias
            1: pcbnew.PAD.SMDMask(), # smdmask is smd pad for front copper
            2: backvia_layer_set,
            # drawings
            3: pcbnew.F_SilkS,
            13: pcbnew.F_Fab,
            15: pcbnew.Dwgs_User,
        }

        # small helper functions
        get_or = lambda d,k: d[k] if k in d else None
        mmi = lambda x: pcbnew.FromMM(x)

        sizexy = lambda x,y: pcbnew.VECTOR2I(mmi(x), mmi(y))
        posxy = lambda x,y: sizexy(x-self.input.bbox.x, y - self.input.bbox.y)

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
                pad.SetLayerSet(get_or(layers, ee_pad.layer_id) or pad.SMDMask())

            point_list = [fp_to_ki(point) for point in ee_pad.points.split(" ")]

            if shape == pcbnew.PAD_SHAPE_CUSTOM:
                if len(point_list) <= 0:
                    print("PAD: custom shape has no points: ", ee_pad.number)
                    continue
                
                polygon = pcbnew.VECTOR_VECTOR2I()
                for i in range(0, len(point_list), 2):
                    polygon.append(sizexy(point_list[i]-ee_pad.center_x,point_list[i+1]-ee_pad.center_y))

                # add polygon as custom shape
                pad.AddPrimitivePoly(polygon,0,True)

                # set base shape size to 0,0
                pad.SetSize(pcbnew.VECTOR2I(0,0))
            else:
                pad.SetSize(sizexy(max(ee_pad.width, 0.01), max(ee_pad.height, 0.01)))

            pad.SetShape(shape)

            if not isnan(ee_pad.rotation):
                pad.SetOrientation(pcbnew.EDA_ANGLE(float(ee_pad.rotation), pcbnew.DEGREES_T))
            
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

        # shapes
        self.draw.TransformTranslate(-self.input.bbox.x, -self.input.bbox.y)

        # For rectangles
        for ee_rectangle in self.input.rectangles:
            self.draw.SetLayer(get_or(layers, ee_rectangle.layer_id) or pcbnew.F_Fab)
            self.draw.SetLineThickness(mmi(max(ee_rectangle.stroke_width, 0.01)))

            self.draw.Box(ee_rectangle.x, ee_rectangle.y, ee_rectangle.width, ee_rectangle.height)
            print("box ", ee_rectangle.layer_id, ee_rectangle.x, ee_rectangle.y)

    
        # For tracks
        for ee_track in self.input.tracks:
            ki_track = KiFootprintTrack(
                layers=KI_PAD_LAYER[ee_track.layer_id]
                if ee_track.layer_id in KI_PAD_LAYER
                else "F.Fab",
                stroke_width=max(ee_track.stroke_width, 0.01),
            )
            self.draw.SetLayer(get_or(layers, ee_track.layer_id) or pcbnew.F_Fab)
            self.draw.SetLineThickness(mmi(max(ee_track.stroke_width, 0.01)))

            # Generate line
            point_list = [fp_to_ki(point) for point in ee_track.points.split(" ")]
            print("track ", ee_track.layer_id, point_list)

            point_list = [sizexy(point_list[i], point_list[i+1]) for i in range(0, len(point_list), 2)]
            self.draw.Polyline(point_list)


        return 
    
        # For holes
        for ee_hole in self.input.holes:
            ki_hole = KiFootprintHole(
                pos_x=ee_hole.center_x - self.input.bbox.x,
                pos_y=ee_hole.center_y - self.input.bbox.y,
                size=ee_hole.radius * 2,
            )

            self.output.holes.append(ki_hole)

        # For circles
        for ee_circle in self.input.circles:
            ki_circle = KiFootprintCircle(
                cx=ee_circle.cx - self.input.bbox.x,
                cy=ee_circle.cy - self.input.bbox.y,
                end_x=0.0,
                end_y=0.0,
                layers=KI_LAYERS[ee_circle.layer_id]
                if ee_circle.layer_id in KI_LAYERS
                else "F.Fab",
                stroke_width=max(ee_circle.stroke_width, 0.01),
            )
            ki_circle.end_x = ki_circle.cx + ee_circle.radius
            ki_circle.end_y = ki_circle.cy
            self.output.circles.append(ki_circle)


        # For arcs
        for ee_arc in self.input.arcs:
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
            ki_text = KiFootprintText(
                pos_x=ee_text.center_x - self.input.bbox.x,
                pos_y=ee_text.center_y - self.input.bbox.y,
                orientation=angle_to_ki(ee_text.rotation),
                text=ee_text.text,
                layers=KI_LAYERS[ee_text.layer_id]
                if ee_text.layer_id in KI_LAYERS
                else "F.Fab",
                font_size=max(ee_text.font_size, 1),
                thickness=max(ee_text.stroke_width, 0.01),
                display=" hide" if ee_text.is_displayed is False else "",
                mirror="",
            )
            ki_text.layers = (
                ki_text.layers.replace(".SilkS", ".Fab")
                if ee_text.type == "N"
                else ki_text.layers
            )
            ki_text.mirror = " mirror" if ki_text.layers[0] == "B" else ""
            self.output.texts.append(ki_text)

        # TODO: implement
        #ki_footprint = ExporterFootprintKicad(footprint=self.cad_data)

        return
    
