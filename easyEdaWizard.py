#
# This program source code file is part of KiCad, a free EDA CAD application.
#
# Copyright (C) 2021 KiCad Developers, see AUTHORS.txt for contributors.
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#

from __future__ import division
import pcbnew
import math


class FootprintWizard(pcbnew.FootprintWizardPlugin):
    """!
    A class to simplify many aspects of footprint creation, leaving only
    the footprint specific routines to the wizards themselves.

    Inherit this class to make a new wizard.

    Provides simplified access to helpers like drawing functions, a transform
    matrix stack and simple parameter checking.

    Generally, you need to implement:
        GetValue()
        GenerateParameterList()
        CheckParameters()
        BuildThisFootprint()
        GetName()
        GetDescription()
    """

    # Copy units from pcbnew
    uMM = pcbnew.uMM
    uMils = pcbnew.uMils
    uFloat = pcbnew.uFloat
    uInteger = pcbnew.uInteger
    uBool = pcbnew.uBool
    uRadians = pcbnew.uRadians
    uDegrees = pcbnew.uDegrees
    uPercent = pcbnew.uPercent
    uString = pcbnew.uString

    def __init__(self):
        pcbnew.FootprintWizardPlugin.__init__(self)
        self.GenerateParameterList()

    def GetName(self):
        """!
        Return the name of the footprint wizard
        """
        raise NotImplementedError

    def GetDescription(self):
        """!
        Return the footprint wizard description
        """
        raise NotImplementedError

    def GetValue(self):
        """!
        Return the value (name) of the generated footprint
        """
        raise NotImplementedError

    def GenerateParameterList(self):
        """!
        Footprint parameter specification is done here
        """
        raise NotImplementedError

    def CheckParameters(self):
        """!
        Any custom parameter checking should be performed here
        """
        raise NotImplementedError

    def BuildThisFootprint(self):
        """!
        Draw the footprint.

        This is specific to each footprint class, you need to implement
        this to draw what you want
        """
        raise NotImplementedError

    # Do not override this method!
    def BuildFootprint(self):
        """!
        Actually make the footprint. We defer all but the set-up to
        the implementing class
        """

        self.buildmessages = ""
        self.module = pcbnew.FOOTPRINT(None)  # create a new module

        # Perform default checks on all parameters
        for p in self.params:
            p.ClearErrors()
            p.Check()  # use defaults

        self.CheckParameters()  # User error checks

        if self.AnyErrors():  # Errors were detected!

            self.buildmessages = ("Cannot build footprint: "
                                  "Parameters have errors:\n")

            for p in self.params:
                if len(p.error_list) > 0:
                    self.buildmessages += "['{page}']['{name}']:\n".format(
                        page=p.page, name=p.name)

                    for error in p.error_list:
                        self.buildmessages += "\t" + error + "\n"

            return

        self.buildmessages = (
            "Building new {name} footprint with the following parameters:\n"
            .format(name=self.name))

        self.buildmessages += self.Show()

        self.draw = FootprintWizardDrawingAids(
            self.module)

        self.module.SetValue(self.GetValue())
        self.module.SetReference("%s**" % self.GetReferencePrefix())

        fpid = pcbnew.LIB_ID("", self.module.GetValue())  # the lib name  (empty) and the name in library
        self.module.SetFPID(fpid)

        self.SetModule3DModel()  # add a 3D module if specified

        thick = self.GetTextThickness()

        self.module.Reference().SetTextThickness(thick)
        self.module.Value().SetTextThickness(thick)

        self.BuildThisFootprint()  # implementer's build function

        return

    def SetModule3DModel(self):
        """!
        If your plug-in sets a 3D model, override this function
        """
        pass

    def GetTextSize(self):
        """!
        Get the default text size for the footprint. Override to change it.

        Defaults to IPC nominal of 1.0mm
        """
        return pcbnew.FromMM(1.0)

    def GetTextThickness(self):
        """!
        Thicker than IPC guidelines (10% of text height = 0.12mm)
        as 5 wires/mm is a common silk screen limitation
        """
        return pcbnew.FromMM(0.15)


class FootprintWizardDrawingAids:
    """!
    Collection of handy functions to simplify drawing shapes from within
    footprint wizards

    A "drawing context" is provided which can be used to set and retain
    settings such as line thickness and layer. The DC also contains a
    "transform stack", which allows easy positioning and transforming of
    drawn elements without lots of geometric book-keeping.
    """

    # directions (in degrees, compass-like)
    dirN = 0
    dirNE = 45
    dirE = 90
    dirSE = 135
    dirS = 180
    dirSW = 225
    dirW = 270
    dirNW = 315

    # Flip constants
    flipNone = 0  # no flip transform
    flipX = 1  # flip X values, i.e. about the Y-axis
    flipY = 2  # flip Y values, i.e. about the X-axis
    flipBoth = 3  # flip X and Y values, equivalent to a 180-degree rotation

    xfrmIDENTITY = [1, 0, 0, 0, 1, 0]  # no transform

    # these values come from our KiCad Library Convention 0.11
    defaultLineThickness = pcbnew.FromMM(0.15)

    def DefaultGraphicLayer(self):
        return pcbnew.F_SilkS

    def DefaultTextValueLayer(self):
        return pcbnew.F_Fab

    def __init__(self, module):
        self.module = module
        # drawing context defaults
        self.dc = {
            'layer': self.DefaultGraphicLayer(),
            'lineThickness': self.defaultLineThickness,
            'transforms': [],
            'transform': self.xfrmIDENTITY
        }

    def PushTransform(self, mat):
        """!
        Add a transform to the top of the stack and recompute the
        overall transform

        @param mat: the transform matrix to add to the stack
        """
        self.dc['transforms'].append(mat)
        self.RecomputeTransforms()

    def PopTransform(self, num=1):
        """!
        Remove a transform from the top of the stack and recompute the
        overall transform

        @param num: the number of transforms to pop from the stack.
        @return the last popped transform
        """

        for i in range(num):
            mat = self.dc['transforms'].pop()
        self.RecomputeTransforms()
        return mat

    def ResetTransform(self):
        """!
        Reset the transform stack to the identity matrix.
        """
        self.dc['transforms'] = []
        self.RecomputeTransforms()

    def _ComposeMatricesWithIdentity(self, mats):
        """!
        Compose a sequence of matrices together by sequential
        pre-multiplication with the identity matrix.

        @param mats: list of matrices to compose
        @return: the composed transform matrix
        """

        x = self.xfrmIDENTITY

        for mat in mats:
            # Pre-compose with each transform in turn
            x = [
                x[0] * mat[0] + x[1] * mat[3],
                x[0] * mat[1] + x[1] * mat[4],
                x[0] * mat[2] + x[1] * mat[5] + x[2],
                x[3] * mat[0] + x[4] * mat[3],
                x[3] * mat[1] + x[4] * mat[4],
                x[3] * mat[2] + x[4] * mat[5] + x[5]]

        return x

    def RecomputeTransforms(self):
        """!
        Re-compute the transform stack into a single transform and
        store in the DC
        """
        self.dc['transform'] = self._ComposeMatricesWithIdentity(
            self.dc['transforms'])

    def TransformTranslate(self, x, y, push=True):
        """!
        Set up and return a transform matrix representing a translation
        optionally pushing onto the stack

        (   1  0   x  )
        (   0  1   y  )

        @param x: translation in x-direction
        @param y: translation in y-direction
        @param push: add this transform to the current stack
        @return the generated transform matrix
        """
        mat = [1, 0, x, 0, 1, y]

        if push:
            self.PushTransform(mat)
        return mat

    def TransformFlipOrigin(self, flip, push=True):
        """!
        Set up and return a transform matrix representing a horizontal,
        vertical or both flip about the origin

        @param flip: one of flipNone, flipX, flipY, flipBoth
        @param push: add this transform to the current stack
        @return the generated transform matrix
        """
        mat = None
        if flip == self.flipX:
            mat = [-1, 0, 0, 0, 1, 0]
        elif flip == self.flipY:
            mat = [1, 0, 0, 0, -1, 0]
        elif flip == self.flipBoth:
            mat = [-1, 0, 0, 0, -1, 0]
        elif flip == self.flipNone:
            mat = self.xfrmIDENTITY
        else:
            raise ValueError

        if push:
            self.PushTransform(mat)
        return mat

    def TransformFlip(self, x, y, flip=flipNone, push=True):
        """!
        Set up and return a transform matrix representing a horizontal,
        vertical or both flip about a point (x,y)

        This is performed by a translate-to-origin, flip, translate-
        back sequence.

        @param x: the x coordinate of the flip point
        @param y: the y coordinate of the flip point
        @param flip: one of flipNone, flipX, flipY, flipBoth
        @param push: add this transform to the current stack
        @return the generated transform matrix
        """
        mats = [self.TransformTranslate(x, y, push=False),
                self.TransformFlipOrigin(flip, push=False),
                self.TransformTranslate(-x, -y, push=False)]

        # Distil into a single matrix
        mat = self._ComposeMatricesWithIdentity(mats)

        if push:
            self.PushTransform(mat)
        return mat

    def TransformRotationOrigin(self, rot, push=True):
        """!
        Set up and return a transform matrix representing a rotation
        about the origin, and optionally push onto the stack

        (   cos(t)  -sin(t)   0  )
        (   sin(t)   cos(t)   0  )

        @param rot: the rotation angle in degrees
        @param push: add this transform to the current stack
        @return the generated transform matrix
        """
        rads = rot * math.pi / 180
        mat = [math.cos(rads), -math.sin(rads), 0,
               math.sin(rads), math.cos(rads), 0]

        if push:
            self.PushTransform(mat)
        return mat

    def TransformRotation(self, x, y, rot, push=True):
        """!
        Set up and return a transform matrix representing a rotation
        about the point (x,y), and optionally push onto the stack

        This is performed by a translate-to-origin, rotate, translate-
        back sequence

        @param x: the x coordinate of the rotation centre
        @param y: the y coordinate of the rotation centre
        @param rot: the rotation angle in degrees
        @param push: add this transform to the current stack
        @return the generated transform matrix
        """

        mats = [self.TransformTranslate(x, y, push=False),
                self.TransformRotationOrigin(rot, push=False),
                self.TransformTranslate(-x, -y, push=False)]

        # Distil into a single matrix
        mat = self._ComposeMatricesWithIdentity(mats)

        if push:
            self.PushTransform(mat)
        return mat

    def TransformScaleOrigin(self, sx, sy=None, push=True):
        """!
        Set up and return a transform matrix representing a scale about
        the origin, and optionally push onto the stack

        (   sx   0   0  )
        (    0  sy   0  )

        @param sx: the scale factor in the x direction
        @param sy: the scale factor in the y direction
        @param push: add this transform to the current stack
        @return the generated transform matrix
        """

        if sy is None:
            sy = sx

        mat = [sx, 0, 0, 0, sy, 0]

        if push:
            self.PushTransform(mat)
        return mat

    def TransformPoint(self, x, y, mat=None):
        """!
        Return a point (x, y) transformed by the given matrix, or if
        that is not given, the drawing context transform

        @param x: the x coordinate of the point to transform
        @param y: the y coordinate of the point to transform
        @param mat: the transform matrix to use or None to use the current DC's
        @return: the transformed point as a VECTOR2I
        """

        if not mat:
            mat = self.dc['transform']

        return pcbnew.VECTOR2I( (int)(x * mat[0] + y * mat[1] + mat[2]),
                                (int)(x * mat[3] + y * mat[4] + mat[5]) )

    def SetLineThickness(self, lineThickness):
        """!
        Set the current pen lineThickness used for subsequent drawing
        operations

        @param lineThickness: the new line thickness to set
        """
        self.dc['lineThickness'] = lineThickness

    def SetLineTickness(self, lineThickness):
        """!
        Old version of SetLineThickness.
        Does the same thing, but is only here for compatibility with old
        scripts.
        Set the current pen lineThickness used for subsequent drawing
        operations

        @param lineThickness: the new line thickness to set
        """
        self.SetLineThickness(lineThickness)

    def GetLineThickness(self):
        """!
        Get the current drawing context line thickness
        """
        return self.dc['lineThickness']

    def SetLayer(self, layer):
        """!
        Set the current drawing layer, used for subsequent drawing
        operations
        """
        self.dc['layer'] = layer

    def GetLayer(self):
        """!
        Return the current drawing layer, used for drawing operations
        """
        return self.dc['layer']

    def Line(self, x1, y1, x2, y2):
        """!
        Draw a line from (x1, y1) to (x2, y2)
        """
        outline = pcbnew.PCB_SHAPE(self.module)
        outline.SetWidth(self.GetLineThickness())
        outline.SetLayer(self.GetLayer())
        outline.SetShape(pcbnew.S_SEGMENT)
        start = self.TransformPoint(x1, y1)
        end = self.TransformPoint(x2, y2)
        outline.SetStartEnd(start, end)
        self.module.Add(outline)

    def Circle(self, x, y, r, filled=False):
        """!
        Draw a circle at (x,y) of radius r
        If filled is true, the thickness and radius of the line will be set
        such that the circle appears filled

        @param x: the x coordinate of the arc centre
        @param y: the y coordinate of the arc centre
        @param r: the circle's radius
        @param filled: True to draw a filled circle, False to use the current
                       DC line thickness
        """

        circle = pcbnew.PCB_SHAPE(self.module)
        start = self.TransformPoint(x, y)

        if filled:
            circle.SetWidth(r)
            end = self.TransformPoint(x, y + r/2)
        else:
            circle.SetWidth(self.dc['lineThickness'])
            end = self.TransformPoint(x, y + r)

        circle.SetLayer(self.dc['layer'])
        circle.SetShape(pcbnew.S_CIRCLE)
        circle.SetStartEnd(start, end)
        self.module.Add(circle)

    def MyCmp(self, n1, n2):
        """
        replace the cmp() of python2
        """
        if n1 < n2:
            return -1
        if n1 > n2:
            return 1
        return 0

    def Arc(self, cx, cy, sx, sy, angle):
        """!
        Draw an arc based on centre, start and angle

        The transform matrix is applied

        Note that this won't work properly if the result is not a
        circular arc (e.g. a horizontal scale)

        @param cx: the x coordinate of the arc centre
        @param cy: the y coordinate of the arc centre
        @param sx: the x coordinate of the arc start point
        @param sy: the y coordinate of the arc start point
        @param angle: the arc's central angle (in deci-degrees)
        """
        arc = pcbnew.PCB_SHAPE(self.module)
        arc.SetShape(pcbnew.SHAPE_T_ARC)
        arc.SetWidth(self.dc['lineThickness'])

        center = self.TransformPoint(cx, cy)
        start = self.TransformPoint(sx, sy)

        arc.SetLayer(self.dc['layer'])

        # check if the angle needs to be reverse (a flip scaling)
        if self.MyCmp(self.dc['transform'][0], 0) != self.MyCmp(self.dc['transform'][4], 0):
            angle = -angle

        arc.SetCenter(center)
        arc.SetStart(start)
        arc.SetArcAngleAndEnd(angle, True)
        #arc.SetLocalCoord()
        self.module.Add(arc)

    def HLine(self, x, y, l):
        """!
        Draw a horizontal line from (x,y), rightwards

        @param x: line start x coordinate
        @param y: line start y coordinate
        @param l: line length
        """
        self.Line(x, y, x + l, y)

    def VLine(self, x, y, l):
        """!
        Draw a vertical line from (x1,y1), downwards

        @param x: line start x coordinate
        @param y: line start y coordinate
        @param l: line length
        """
        self.Line(x, y, x, y + l)

    def Polyline(self, pts, mirrorX=None, mirrorY=None):
        """!
        Draw a polyline, optionally mirroring around the given points

        @param pts: list of polyline vertices (list of (x, y))
        @param mirrorX: x coordinate of mirror point (None for no x-flip)
        @param mirrorY: y coordinate of mirror point (None for no y-flip)
        """

        def _PolyLineInternal(pts):
            if len(pts) < 2:
                return

            for i in range(0, len(pts) - 1):
                self.Line(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1])

        if mirrorX is None and mirrorY is None:
            _PolyLineInternal(pts)  # original

        elif mirrorX is not None and mirrorY is not None:
            self.TransformFlip(mirrorX, mirrorY, self.flipBoth)  # both
            _PolyLineInternal(pts)
            self.PopTransform()

        elif mirrorX is not None:
            self.TransformFlip(mirrorX, 0, self.flipX)
            _PolyLineInternal(pts)
            self.PopTransform()

        elif mirrorY is not None:
            self.TransformFlip(0, mirrorY, self.flipY)
            _PolyLineInternal(pts)
            self.PopTransform()

    def Reference(self, x, y, size, orientation_degree=0):
        """!
        Draw the module's reference as the given point.

        The actual setting of the reference is not done in this drawing
        aid - that is up to the wizard

        @param x: the x position of the reference
        @param y: the y position of the reference
        @param size: the text size (in both directions)
        @param orientation_degree: text orientation in degrees
        """

        text_size = pcbnew.VECTOR2I(size, size)

        self.module.Reference().SetPosition( self.TransformPoint(x, y) )
        self.module.Reference().SetTextSize(text_size)
        self.module.Reference().SetTextAngle( pcbnew.EDA_ANGLE( orientation_degree, pcbnew.DEGREES_T ) )

    def Value(self, x, y, size, orientation_degree=0):
        """!
        As for references, draw the module's value

        @param x: the x position of the value
        @param y: the y position of the value
        @param size: the text size (in both directions)
        @param orientation_degree: text orientation in degrees
        """
        text_size = pcbnew.VECTOR2I(size, size)

        self.module.Value().SetPosition(self.TransformPoint(x, y))
        self.module.Value().SetTextSize(text_size)
        self.module.Value().SetLayer(self.DefaultTextValueLayer())
        self.module.Value().SetTextAngle( pcbnew.EDA_ANGLE( orientation_degree, pcbnew.DEGREES_T ) )

    def Box(self, x, y, w, h):
        """!
        Draw a rectangular box, centred at (x,y), with given width and
        height

        @param x: the x coordinate of the box's centre
        @param y: the y coordinate of the box's centre
        @param w: the width of the box
        @param h: the height of the box
        """

        pts = [[x - w/2, y - h/2],  # left
               [x + w/2, y - h/2],  # right
               [x + w/2, y + h/2],  # bottom
               [x - w/2, y + h/2],  # top
               [x - w/2, y - h/2]]  # close

        self.Polyline(pts)

    def NotchedCircle(self, x, y, r, notch_w, notch_h, rotate=0):
        """!
        Circle radius r centred at (x, y) with a raised or depressed notch
        at the top
        Notch height is measured from the top of the circle radius

        @param x: the x coordinate of the circle's centre
        @param y: the y coordinate of the circle's centre
        @param r: the radius of the circle
        @param notch_w: the width of the notch
        @param notch_h: the height of the notch
        @param rotate: the rotation of the whole figure, in degrees
        """

        self.TransformRotation(x, y, rotate)

        # find the angle where the notch vertical meets the circle
        angle_intercept = math.asin(notch_w/(2 * r))

        # and find the co-ords of this point
        sx = math.sin(angle_intercept) * r
        sy = -math.cos(angle_intercept) * r

        # NOTE: this may be out by a factor of ten one day
        arc_angle = (math.pi * 2 - angle_intercept * 2) * (1800/math.pi)

        self.Arc(x, y, sx, sy, arc_angle)

        pts = [[sx,  sy],
               [sx,  -r - notch_h],
               [-sx, -r - notch_h],
               [-sx, sy]]

        self.Polyline(pts)
        self.PopTransform()

    def NotchedBox(self, x, y, w, h, notchW, notchH, rotate=0):
        """!
        Draw a box with a notch in the centre of the top edge

        @param x: the x coordinate of the circle's centre
        @param y: the y coordinate of the circle's centre
        @param w: the width of the box
        @param h: the height of the box
        @param notchW: the width of the notch
        @param notchH: the height of the notch
        @param rotate: the rotation of the whole figure, in degrees
        """

        self.TransformRotation(x, y, rotate)

        # limit to half the overall width
        notchW = min(x + w/2, notchW)

        # draw notch
        self.Polyline([  # three sides of box
            (x - w/2, y - h/2),
            (x - w/2, y + h/2),
            (x + w/2, y + h/2),
            (x + w/2, y - h/2),
            # the notch
            (notchW/2, y - h/2),
            (notchW/2, y - h/2 + notchH),
            (-notchW/2, y - h/2 + notchH),
            (-notchW/2, y - h/2),
            (x - w/2, y - h/2)
        ])

        self.PopTransform()

    def BoxWithDiagonalAtCorner(self, x, y, w, h,
                                setback=pcbnew.FromMM(1.27), flip=flipNone):
        """!
        Draw a box with a diagonal at the top left corner.

        @param x: the x coordinate of the circle's centre
        @param y: the y coordinate of the circle's centre
        @param w: the width of the box
        @param h: the height of the box
        @param setback: the set-back of the diagonal, in both x and y
        @param flip: one of flipNone, flipX, flipY or flipBoth to change the
         diagonal corner
        """

        self.TransformFlip(x, y, flip, push=True)

        pts = [[x - w/2 + setback, y - h/2],
               [x - w/2,           y - h/2 + setback],
               [x - w/2,           y + h/2],
               [x + w/2,           y + h/2],
               [x + w/2,           y - h/2],
               [x - w/2 + setback, y - h/2]]

        self.Polyline(pts)

        self.PopTransform()

    def BoxWithOpenCorner(self, x, y, w, h,
                          setback=pcbnew.FromMM(1.27), flip=flipNone):
        """!
        Draw a box with an opening at the top left corner

        @param x: the x coordinate of the circle's centre
        @param y: the y coordinate of the circle's centre
        @param w: the width of the box
        @param h: the height of the box
        @param setback: the set-back of the opening, in both x and y
        @param flip: one of flipNone, flipX, flipY or flipBoth to change the
         open corner position
        """

        self.TransformTranslate(x, y)
        self.TransformFlipOrigin(flip)

        pts = [[- w/2,           - h/2 + setback],
               [- w/2,           + h/2],
               [+ w/2,           + h/2],
               [+ w/2,           - h/2],
               [- w/2 + setback, - h/2]]

        self.Polyline(pts)

        self.PopTransform(num=2)

    def RoundedBox(self, x, y, w, h, rad):
        """!
        Draw a box with rounded corners (i.e. a 90-degree circular arc)

        :param x: the x coordinate of the box's centre
        :param y: the y coordinate of the box's centre
        :param w: the width of the box
        :param h: the height of the box
        :param rad: the radius of the corner rounds
        """

        x_inner = w - rad * 2
        y_inner = h - rad * 2

        x_left = x - w / 2
        y_top = y - h / 2

        # Draw straight sections
        self.HLine(x_left + rad, y_top, x_inner)
        self.HLine(x_left + rad, -y_top, x_inner)

        self.VLine(x_left, y_top + rad, y_inner)
        self.VLine(-x_left, y_top + rad, y_inner)

        # corner arcs
        ninety_deg = 90 * 10  # deci-degs
        cx = x - w / 2 + rad
        cy = y - h / 2 + rad

        # top left
        self.Arc(+cx, +cy, +x_left, +cy, +ninety_deg)
        self.Arc(-cx, +cy, -x_left, +cy, -ninety_deg)
        self.Arc(+cx, -cy, +x_left, -cy, -ninety_deg)
        self.Arc(-cx, -cy, -x_left, -cy, +ninety_deg)

    def ChamferedBox(self, x, y, w, h, chamfer_x, chamfer_y):
        """!
        Draw a box with chamfered corners.

        :param x: the x coordinate of the box's centre
        :param y: the y coordinate of the box's centre
        :param w: the width of the box
        :param h: the height of the box
        :param chamfer_x: the size of the chamfer set-back in the x direction
        :param chamfer_y: the size of the chamfer set-back in the y direction
        """
        # outermost dimensions
        x_left = x - w / 2
        y_top = y - h / 2

        # x and y coordinates of inner edges of chamfers
        x_inner = x_left + chamfer_x
        y_inner = y_top + chamfer_y

        pts = [
            [+x_inner, +y_top],
            [-x_inner, +y_top],
            [-x_left,  +y_inner],
            [-x_left,  -y_inner],
            [-x_inner, -y_top],
            [+x_inner, -y_top],
            [+x_left,  -y_inner],
            [+x_left,  +y_inner],
            [+x_inner, +y_top],
        ]

        self.draw.Polyline(pts)

    def MarkerArrow(self, x, y, direction=dirN, width=pcbnew.FromMM(1)):
        """!
        Draw a marker arrow facing in the given direction, with the
        point at (x,y)

        @param x: x position of the arrow tip
        @param y: y position of the arrow tip
        @param direction: arrow direction in degrees (0 is "north", can use
         dir* shorthands)
        @param width: arrow width
        """

        self.TransformTranslate(x, y)
        self.TransformRotationOrigin(direction)

        pts = [[0,          0],
               [width / 2,  width / 2],
               [-width / 2, width / 2],
               [0,          0]]

        self.Polyline(pts)
        self.PopTransform(2)

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


        #self.output = KiFootprint(info=ki_info, model_3d=ki_3d_model_info)

        # For pads
        pad_shapes = {
            "ELLIPSE":  pcbnew.PAD_SHAPE_CIRCLE,
            "RECT": pcbnew.PAD_SHAPE_RECT,
            "OVAL": pcbnew.PAD_SHAPE_OVAL,
            "POLYGON": pcbnew.PAD_SHAPE_CUSTOM,
        }

        layers = {
            1: "F.Cu F.Paste F.Mask",
            2: "B.Cu B.Paste B.Mask",
            3: "F.SilkS",
            11: "*.Cu *.Paste *.Mask",
            13: "F.Fab",
            15: "Dwgs.User",
        }

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
                pad.SetLayerSet(pad.SMDMask())

            point_list = [fp_to_ki(point) for point in ee_pad.points.split(" ")]

            if shape == pcbnew.PAD_SHAPE_CUSTOM:
                if len(point_list) <= 0:
                    print("PAD: custom shape has no points: ", ee_pad.number)
                    continue
                
                polygon = pcbnew.VECTOR_VECTOR2I()
                for i in range(0, len(point_list), 2):
                    polygon.append(sizexy(point_list[i]-ee_pad.center_x,point_list[i+1]-ee_pad.center_y))

                print(point_list)

                # add polygon as custom shape
                pad.AddPrimitivePoly(polygon,0,True)

                # set base shape size to 0,0
                pad.SetSize(pcbnew.VECTOR2I(0,0))
            else:
                pad.SetSize(sizexy(max(ee_pad.width, 0.01), max(ee_pad.height, 0.01)))

            pad.SetShape(shape)
            pad.SetOrientation(pcbnew.EDA_ANGLE(0, pcbnew.DEGREES_T))

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

        return 
    
        # For tracks
        for ee_track in self.input.tracks:
            ki_track = KiFootprintTrack(
                layers=KI_PAD_LAYER[ee_track.layer_id]
                if ee_track.layer_id in KI_PAD_LAYER
                else "F.Fab",
                stroke_width=max(ee_track.stroke_width, 0.01),
            )

            # Generate line
            point_list = [fp_to_ki(point) for point in ee_track.points.split(" ")]
            for i in range(0, len(point_list) - 2, 2):
                ki_track.points_start_x.append(
                    round(point_list[i] - self.input.bbox.x, 2)
                )
                ki_track.points_start_y.append(
                    round(point_list[i + 1] - self.input.bbox.y, 2)
                )
                ki_track.points_end_x.append(
                    round(point_list[i + 2] - self.input.bbox.x, 2)
                )
                ki_track.points_end_y.append(
                    round(point_list[i + 3] - self.input.bbox.y, 2)
                )

            self.output.tracks.append(ki_track)

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

        # For rectangles
        for ee_rectangle in self.input.rectangles:
            ki_rectangle = KiFootprintRectangle(
                layers=KI_PAD_LAYER[ee_rectangle.layer_id]
                if ee_rectangle.layer_id in KI_PAD_LAYER
                else "F.Fab",
                stroke_width=max(ee_rectangle.stroke_width, 0.01),
            )

            start_x = ee_rectangle.x - self.input.bbox.x
            start_y = ee_rectangle.y - self.input.bbox.y
            width = ee_rectangle.width
            height = ee_rectangle.height

            ki_rectangle.points_start_x = [
                start_x,
                start_x + width,
                start_x + width,
                start_x,
            ]
            ki_rectangle.points_start_y = [start_y, start_y, start_y + height, start_y]
            ki_rectangle.points_end_x = [
                start_x + width,
                start_x + width,
                start_x,
                start_x,
            ]
            ki_rectangle.points_end_y = [
                start_y,
                start_y + height,
                start_y + height,
                start_y,
            ]

            self.output.rectangles.append(ki_rectangle)

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
    
EasyedaWizard().register()

