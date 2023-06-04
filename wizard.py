

from __future__ import division
import pcbnew

import pcbnew
import footprint_wizards.FootprintWizardBase as Base
import footprint_wizards.PadArray as PA

class EasyedaWizard(Base.FootprintWizard):
    def GetName(self):
        return "EasyEDA"

    def GetDescription(self):
        return "EasyEDA import"

    def GenerateParameterList(self):
        #TODO - Allow different number of pads in x and y directions
        self.AddParam("Part", "LCSC Number", self.uString, "")
        self.AddParam("Part", "Import 3d Model", self.uBool, True)

    @property
    def part(self):
        return self.parameters['Part']

    def CheckParameters(self):
        pass

    def GetValue(self):
        return "LCSC-{}".format(self.part["LCSC Number"])

    def BuildThisFootprint(self):
        # TODO: implement
        return
    
        pad_pitch = self.pads["pitch"]
        pad_length = self.pads["length"]
        # Fillet allows to define how much of the pad is outside of the package
        pad_fillet = self.pads["fillet"]
        pad_width = self.pads["width"]

        v_pitch = self.package["height"]
        h_pitch = self.package["width"]

        pads_per_row = int(self.pads["n"] // 4)

        row_len = (pads_per_row - 1) * pad_pitch

        pad_shape = pcbnew.PAD_SHAPE_OVAL if self.pads["oval"] else pcbnew.PAD_SHAPE_RECT

        h_pad = PA.PadMaker(self.module).SMDPad( pad_length + pad_fillet, pad_width,
                                                 shape=pad_shape, rot_degree=90.0)
        v_pad = PA.PadMaker(self.module).SMDPad( pad_length + pad_fillet, pad_width, shape=pad_shape)

        h_pitch = h_pitch / 2 - pad_length + (pad_length+pad_fillet)/2
        v_pitch = v_pitch / 2 - pad_length + (pad_length+pad_fillet)/2

        #left row
        pin1Pos = pcbnew.wxPoint(-h_pitch, 0)
        array = PA.PadLineArray(h_pad, pads_per_row, pad_pitch, True, pin1Pos)
        array.SetFirstPadInArray(1)
        array.AddPadsToModule(self.draw)

        #bottom row
        pin1Pos = pcbnew.wxPoint(0, v_pitch)
        array = PA.PadLineArray(v_pad, pads_per_row, pad_pitch, False, pin1Pos)
        array.SetFirstPadInArray(pads_per_row + 1)
        array.AddPadsToModule(self.draw)

        #right row
        pin1Pos = pcbnew.wxPoint(h_pitch, 0)
        array = PA.PadLineArray(h_pad, pads_per_row, -pad_pitch, True,
                                pin1Pos)
        array.SetFirstPadInArray(2*pads_per_row + 1)
        array.AddPadsToModule(self.draw)

        #top row
        pin1Pos = pcbnew.wxPoint(0, -v_pitch)
        array = PA.PadLineArray(v_pad, pads_per_row, -pad_pitch, False,
                                pin1Pos)
        array.SetFirstPadInArray(3*pads_per_row + 1)
        array.AddPadsToModule(self.draw)

        lim_x = self.package["width"] / 2
        lim_y = self.package["height"] / 2
        inner = (row_len / 2) + pad_pitch

        # epad
        epad_width   = self.epad["width"]
        epad_length  = self.epad["length"]

        epad_ny = self.epad["x divisions"]
        epad_nx = self.epad["y divisions"]

        epad_via_drill = self.epad["thermal vias drill"]

        # Create a central exposed pad?
        if self.epad['epad'] == True:

            epad_num = self.pads['n'] + 1

            epad_w = epad_length / epad_nx
            epad_l = epad_width / epad_ny

            # Create the epad
            epad = PA.PadMaker(self.module).SMDPad( epad_w, epad_l, shape=pcbnew.PAD_SHAPE_RECT )
            epad.SetLocalSolderPasteMargin( -1 * self.epad['paste margin'] )
            # set pad layers
            layers = pcbnew.LSET(pcbnew.F_Mask)
            layers.AddLayer(pcbnew.F_Cu)
            layers.AddLayer(pcbnew.F_Paste)
            epad.SetName(epad_num)

            array = PA.EPADGridArray( epad, epad_ny, epad_nx, epad_l, epad_w, pcbnew.wxPoint(0,0) )
            array.SetFirstPadInArray(epad_num)
            array.AddPadsToModule(self.draw)

            if self.epad['thermal vias']:

                # create the thermal via
                via_diam = min(epad_w, epad_l) / 2
                via_drill = min(via_diam / 2, epad_via_drill)
                via = PA.PadMaker(self.module).THRoundPad(via_diam, via_drill)
                layers = pcbnew.LSET.AllCuMask()
                layers.AddLayer(pcbnew.B_Mask)
                layers.AddLayer(pcbnew.F_Mask)
                via.SetLayerSet(layers)

                via_array = PA.EPADGridArray(via, epad_ny, epad_nx, epad_l, epad_w, pcbnew.wxPoint(0,0) )
                via_array.SetFirstPadInArray(epad_num)
                via_array.AddPadsToModule(self.draw)

        # Draw the package outline on the F.Fab layer
        bevel = min( pcbnew.FromMM(1.0), self.package['width']/2, self.package['height']/2 )

        self.draw.SetLayer(pcbnew.F_Fab)

        w = self.package['width']
        h = self.package['height']

        self.draw.BoxWithDiagonalAtCorner(0, 0, w, h, bevel)

        # Silkscreen
        self.draw.SetLayer(pcbnew.F_SilkS)

        offset = self.draw.GetLineThickness()
        clip = row_len / 2 + self.pads['pitch']

        self.draw.Polyline( [ [ clip, -h/2-offset], [ w/2+offset,-h/2-offset], [ w/2+offset, -clip] ] ) # top right
        self.draw.Polyline( [ [ clip,  h/2+offset], [ w/2+offset, h/2+offset], [ w/2+offset,  clip] ] ) # bottom right
        self.draw.Polyline( [ [-clip,  h/2+offset], [-w/2-offset, h/2+offset], [-w/2-offset,  clip] ] ) # bottom left

        # Add pin-1 indication as per IPC-7351C
        self.draw.Line(-clip, -h/2-offset, -w/2-pad_length/2, -h/2-offset)

        # Courtyard
        cmargin = self.package["margin"]
        self.draw.SetLayer(pcbnew.F_CrtYd)

        sizex = (lim_x + cmargin) * 2 + pad_length
        sizey = (lim_y + cmargin) * 2 + pad_length

        # round size to nearest 0.1mm, rectangle will thus land on a 0.05mm grid
        sizex = pcbnew.PutOnGridMM(sizex, 0.1)
        sizey = pcbnew.PutOnGridMM(sizey, 0.1)
        # set courtyard line thickness to the one defined in KLC
        thick = self.draw.GetLineThickness()
        self.draw.SetLineThickness(pcbnew.FromMM(0.05))
        self.draw.Box(0, 0, sizex, sizey)
        # restore line thickness to previous value
        self.draw.SetLineThickness(pcbnew.FromMM(thick))

        #reference and value
        text_size = self.GetTextSize()  # IPC nominal
        text_offset = v_pitch / 2 + text_size + pad_length / 2

        self.draw.Value(0, text_offset, text_size)
        self.draw.Reference(0, -text_offset, text_size)

        # set SMD attribute
        self.module.SetAttributes(pcbnew.MOD_CMS)

EasyedaWizard().register()

