#! python2
# Builds the Leaf Venation tutorial example files, one .gh per tutorial step.
#
# How to run (Rhino 8, with LeafVenation.gha installed):
#   1. Type ScriptEditor in Rhino, open this file, press Run (F5).
#      Or type -RunPythonScript and pick this file.
#   2. The .gh files are written to a "Leaf Venation Examples" folder on your Desktop.
#
# The script places components through the Grasshopper SDK, so the files open in any Rhino 8.

import os
import System
import Rhino
import Grasshopper
from System.Drawing import PointF, RectangleF
from Rhino.Geometry import Point3d, Vector3d
from Grasshopper.Kernel import GH_Document, GH_DocumentIO, IGH_Component
from Grasshopper.Kernel.Special import GH_NumberSlider, GH_BooleanToggle, GH_Panel, GH_SliderAccuracy
from Grasshopper.Kernel.Types import GH_Point, GH_Number, GH_Vector, GH_Integer

OUT = os.path.join(os.path.expanduser("~"), "Desktop", "Leaf Venation Examples")

LEAF_OUTLINE = System.Guid("b0d6c1a4-7e2f-4b8e-a0b1-3c5d9e2f4a11")
LEAF_VENATION = System.Guid("3a9e7c21-5d4b-4f6a-8c2e-0b1f7d6a9e22")
VEIN_MESH = System.Guid("c4e2a9b7-1f3d-4e6c-b8a0-5d7e9f1b2c33")
LEAF_TEXTURE = System.Guid("d8f1b3c5-2a4e-4d7f-9c1b-6e8a0f2d4b44")

server = None


def load_grasshopper():
    global server
    gh = Rhino.RhinoApp.GetPlugInObject("Grasshopper")
    if gh is not None:
        gh.LoadEditor()
    server = Grasshopper.Instances.ComponentServer
    if server.FindObjectByName("Leaf Venation", True, True) is None and server.EmitObject(LEAF_VENATION) is None:
        raise Exception("LeafVenation.gha is not loaded. Install it (tutorial step 1), restart Rhino and run this again.")


class Doc(object):
    """A small helper around GH_Document for placing and wiring objects."""

    def __init__(self, title, note):
        self.doc = GH_Document()
        self.title = title
        self.panel(note, 20, 20, 360, 150)

    def add(self, obj, x, y):
        obj.CreateAttributes()
        obj.Attributes.Pivot = PointF(x, y)
        self.doc.AddObject(obj, False)
        return obj

    def plugin(self, guid, x, y):
        obj = server.EmitObject(guid)
        if obj is None:
            raise Exception("Could not create a Leaf Venation component (%s)." % guid)
        return self.add(obj, x, y)

    def native(self, name, n_inputs, x, y):
        """A built-in component by name, preferring the version with the expected input count."""
        fallback = None
        for proxy in server.ObjectProxies:
            if proxy.Obsolete or proxy.Desc.Name != name:
                continue
            obj = proxy.CreateInstance()
            if not isinstance(obj, IGH_Component):
                continue
            if obj.Params.Input.Count == n_inputs:
                return self.add(obj, x, y)
            if fallback is None and obj.Params.Input.Count > n_inputs:
                fallback = obj
        if fallback is not None:
            return self.add(fallback, x, y)
        raise Exception("Could not find the Grasshopper component '%s'." % name)

    def param(self, name, x, y):
        """A floating parameter: Line, Mesh or MD Slider."""
        P = Grasshopper.Kernel.Parameters
        if name == "Line":
            obj = P.Param_Line()
        elif name == "Mesh":
            obj = P.Param_Mesh()
        else:
            obj = None
            for proxy in server.ObjectProxies:
                if not proxy.Obsolete and proxy.Desc.Name == name:
                    obj = proxy.CreateInstance()
                    break
            if obj is None:
                raise Exception("Could not find the Grasshopper object '%s'." % name)
        return self.add(obj, x, y)

    def slider(self, name, value, lo, hi, x, y, decimals=2, integer=False):
        s = GH_NumberSlider()
        s.NickName = name
        s.Slider.Minimum = System.Decimal(lo)
        s.Slider.Maximum = System.Decimal(hi)
        if integer:
            s.Slider.Type = GH_SliderAccuracy.Integer
            s.Slider.DecimalPlaces = 0
        else:
            s.Slider.DecimalPlaces = decimals
        s.SetSliderValue(System.Decimal(value))
        return self.add(s, x, y)

    def toggle(self, name, value, x, y):
        t = GH_BooleanToggle()
        t.NickName = name
        t.Value = value
        return self.add(t, x, y)

    def panel(self, text, x, y, w=220, h=100):
        p = GH_Panel()
        p.UserText = text
        self.add(p, x, y)
        p.Attributes.Bounds = RectangleF(x, y, w, h)
        return p

    # wiring -------------------------------------------------------------

    @staticmethod
    def _out(obj, name):
        if isinstance(obj, IGH_Component):
            if isinstance(name, int):
                return obj.Params.Output[name]
            for p in obj.Params.Output:
                if p.Name == name or p.NickName == name:
                    return p
            raise Exception("No output '%s' on %s" % (name, obj.Name))
        return obj

    @staticmethod
    def _in(obj, name):
        if isinstance(obj, IGH_Component):
            if isinstance(name, int):
                return obj.Params.Input[name]
            for p in obj.Params.Input:
                if p.Name == name or p.NickName == name:
                    return p
            raise Exception("No input '%s' on %s" % (name, obj.Name))
        return obj

    def wire(self, src, src_out, dst, dst_in):
        self._in(dst, dst_in).AddSource(self._out(src, src_out))

    def set(self, comp, inp, *values):
        p = self._in(comp, inp)
        p.PersistentData.Clear()
        for v in values:
            p.PersistentData.Append(v)

    def save(self):
        path = os.path.join(OUT, self.title + ".gh")
        if not GH_DocumentIO(self.doc).SaveQuiet(path):
            raise Exception("Could not save " + path)
        return path


def venation(d, x, y, preset=None, hide=True):
    v = d.plugin(LEAF_VENATION, x, y)
    if hide:
        v.Hidden = True
    if preset is not None:
        d.wire(d.slider("Preset", preset, 1, 6, x - 250, y - 60, integer=True), None, v, "Preset")
    return v


def show_veins(d, v, x, y):
    d.wire(v, "Segments", d.param("Line", x, y), None)
    d.wire(v, "Info", d.panel("", x, y + 40, 260, 160), None)


def outline(d, x, y, **values):
    o = d.plugin(LEAF_OUTLINE, x, y)
    sy = y - 120
    order = ["Length", "Width", "Shape", "Tip", "Teeth", "ToothAmp", "ToothAngle", "ToothSkew"]
    for name in sorted(values, key=order.index):
        val, lo, hi, integer = values[name]
        d.wire(d.slider(name, val, lo, hi, x - 260, sy, integer=integer), None, o, name)
        sy += 26
    return o


# --------------------------------------------------------------------- examples

def step2():
    d = Doc("Step 2 - Presets",
            "STEP 2: FIRST LEAF FROM A PRESET\n\n"
            "Drag the Preset slider from 1 to 6.\n"
            "The Line parameter shows the veins, the panel shows Info.\n"
            "Every unconnected input takes the preset's value.")
    v = venation(d, 700, 300, preset=1)
    show_veins(d, v, 950, 250)
    return d


def step3():
    d = Doc("Step 3 - Leaf Outline",
            "STEP 3: YOUR OWN LEAF SHAPE\n\n"
            "Leaf Outline draws the blade. Outline goes to Boundary, Base to Seeds.\n"
            "Try ToothAngle 0 vs 30 and ToothSkew 0.5 vs 0.75.\n"
            "Preset 3 gives looping (closed) veins.")
    o = outline(d, 500, 330,
                Length=(100, 20, 200, False), Width=(55, 10, 150, False),
                Shape=(0.4, 0.2, 0.8, False), Tip=(1.2, 0.5, 2.0, False),
                Teeth=(12, 0, 40, True), ToothAmp=(3.5, 0, 10, False),
                ToothAngle=(30, 0, 60, False), ToothSkew=(0.75, 0.5, 0.95, False))
    v = venation(d, 800, 330, preset=3)
    d.wire(o, "Outline", v, "Boundary")
    d.wire(o, "Base", v, "Seeds")
    show_veins(d, v, 1050, 280)
    return d


def step4():
    d = Doc("Step 4 - Move the seed",
            "STEP 4: WHERE THE VEINS START\n\n"
            "Drag the dot in the MD Slider: the seed moves over the leaf.\n"
            "(0.5, 0) is the base of the leaf. Near the corners the point can fall\n"
            "outside the leaf and then no veins grow.\n"
            "Evaluate Surface's S input is reparameterized (right-click S) so 0 to 1 covers the leaf.")
    o = outline(d, 400, 330, Length=(100, 20, 200, False), Width=(55, 10, 150, False))
    srf = d.native("Boundary Surfaces", 1, 620, 380)
    d.wire(o, "Outline", srf, 0)
    ev = d.native("Evaluate Surface", 2, 820, 400)
    d.wire(srf, 0, ev, 0)
    try:
        ev.Params.Input[0].Reparameterization = Grasshopper.Kernel.GH_Reparameterization.Unitize
    except Exception:
        pass
    md = d.param("MD Slider", 560, 470)
    try:
        md.Value = Point3d(0.5, 0.0, 0.0)
    except Exception:
        pass
    d.wire(md, None, ev, 1)
    v = venation(d, 1050, 330, preset=1)
    d.wire(o, "Outline", v, "Boundary")
    d.wire(ev, 0, v, "Seeds")
    show_veins(d, v, 1300, 280)
    return d


def step5():
    d = Doc("Step 5 - Holes",
            "STEP 5: HOLES AND RIM VEINS\n\n"
            "Two circles go into Holes. Veins route around them.\n"
            "RimHoles turns hole edges into veins, RimMargin the leaf edge.\n"
            "Move the circles with the X/Y sliders; keep them inside the leaf.")
    o = outline(d, 400, 300, Length=(100, 20, 200, False), Width=(70, 10, 150, False))
    v = venation(d, 900, 330, preset=1)
    d.wire(o, "Outline", v, "Boundary")
    d.wire(o, "Base", v, "Seeds")
    for i, (cx, cy, r) in enumerate([(-11, 42, 7), (10, 64, 5)]):
        y = 420 + i * 130
        pt = d.native("Construct Point", 3, 420, y)
        d.wire(d.slider("X%d" % (i + 1), cx, -30, 30, 170, y - 15), None, pt, 0)
        d.wire(d.slider("Y%d" % (i + 1), cy, 0, 100, 170, y + 10), None, pt, 1)
        c = d.native("Circle CNR", 3, 640, y)
        d.wire(pt, 0, c, 0)
        d.wire(d.slider("R%d" % (i + 1), r, 1, 15, 420, y + 50), None, c, 2)
        d.wire(c, 0, v, "Holes")
    d.wire(d.toggle("RimHoles", True, 700, 690), None, v, "RimHoles")
    d.wire(d.toggle("RimMargin", False, 700, 720), None, v, "RimMargin")
    show_veins(d, v, 1150, 280)
    return d


def step6():
    d = Doc("Step 6 - Curved surface",
            "STEP 6: GROW ON A CURVED SURFACE\n\n"
            "Two arcs are lofted into a curved sheet (Surface).\n"
            "The leaf outline is projected onto it and used as Boundary.\n"
            "Change Bend to curve the sheet more or less.")
    bend = d.slider("Bend", 25, 0, 60, 80, 330)
    arcs = []
    for i, y in enumerate((-20.0, 130.0)):
        arc = d.native("Arc 3Pt", 3, 560, 300 + i * 160)
        for j, x in enumerate((-60.0, 0.0, 60.0)):
            if j == 1:
                mid = d.native("Construct Point", 3, 330, 270 + i * 160)
                d.set(mid, 1, GH_Number(y))
                d.wire(bend, None, mid, 2)
                d.wire(mid, 0, arc, 1)
            else:
                d.set(arc, j, GH_Point(Point3d(x, y, 0)))
        arcs.append(arc)
    loft = d.native("Loft", 2, 760, 380)
    for a in arcs:
        d.wire(a, 0, loft, 0)
    o = outline(d, 560, 640, Length=(100, 20, 120, False), Width=(55, 10, 110, False))
    proj = d.native("Project", 3, 820, 600)
    d.wire(o, "Outline", proj, 0)
    d.wire(loft, 0, proj, 1)
    v = venation(d, 1100, 450, preset=1)
    d.wire(loft, 0, v, "Surface")
    d.wire(proj, 0, v, "Boundary")
    show_veins(d, v, 1350, 400)
    return d


def step7():
    d = Doc("Step 7 - Key settings",
            "STEP 7: THE SETTINGS WORTH CHANGING FIRST\n\n"
            "Each slider overrides one preset value. Values are used as given,\n"
            "so they are set here for a 100-unit leaf.\n"
            "Lower KillDist = denser veins. Closed = loops. Growth: 0 static,\n"
            "1 from the edge, 2 even, 3 length only. Seed = another variation.")
    o = outline(d, 450, 260, Length=(100, 20, 200, False), Width=(55, 10, 150, False))
    v = venation(d, 900, 360, preset=1)
    d.wire(o, "Outline", v, "Boundary")
    d.wire(o, "Base", v, "Seeds")
    y = 380
    for name, val, lo, hi, integer in [("Iterations", 220, 20, 600, True), ("D", 1.0, 0.3, 3.0, False),
                                       ("KillDist", 4.0, 1.0, 10.0, False), ("Darts", 60, 5, 500, True),
                                       ("Growth", 1, 0, 3, True), ("Seed", 1, 1, 100, True)]:
        d.wire(d.slider(name, val, lo, hi, 450, y, integer=integer), None, v, name)
        y += 26
    d.wire(d.toggle("Closed", False, 450, y + 10), None, v, "Closed")
    show_veins(d, v, 1150, 300)
    return d


def step8():
    d = Doc("Step 8 - Vein Mesh",
            "STEP 8: TURN THE VEINS INTO A MESH\n\n"
            "Vein Mesh builds one joined skin that thins toward the tips.\n"
            "The blade is the outline, filled and extruded downward.\n"
            "Half = True keeps only raised veins on top of the blade.\n"
            "CellSize 0 = automatic. Set a size to control detail: smaller is finer and slower.")
    o = outline(d, 400, 300, Length=(100, 20, 200, False), Width=(55, 10, 150, False))
    v = venation(d, 750, 330, preset=3)
    d.wire(o, "Outline", v, "Boundary")
    d.wire(o, "Base", v, "Seeds")
    m = d.plugin(VEIN_MESH, 1100, 380)
    d.wire(v, "Venation", m, "Venation")
    d.wire(d.toggle("Joined", True, 850, 450), None, m, "Joined")
    d.wire(d.toggle("Half", True, 850, 480), None, m, "Half")
    d.wire(d.slider("MaxRadius", 0.8, 0.1, 3.0, 800, 520), None, m, "MaxRadius")
    d.wire(d.slider("Taper", 1.5, 1.0, 4.0, 800, 546), None, m, "Taper")
    d.wire(d.slider("CellSize", 0.0, 0.0, 1.0, 800, 572), None, m, "CellSize")
    d.wire(m, "Info", d.panel("", 1300, 420, 240, 80), None)
    srf = d.native("Boundary Surfaces", 1, 750, 650)
    d.wire(o, "Outline", srf, 0)
    ext = d.native("Extrude", 2, 950, 680)
    d.wire(srf, 0, ext, 0)
    d.set(ext, 1, GH_Vector(Vector3d(0, 0, -0.6)))
    return d


def step9():
    d = Doc("Step 9 - Leaf Texture",
            "STEP 9: TEXTURES FOR RENDERING\n\n"
            "Leaf Texture writes four PNGs into a 'leaf-textures' folder next to\n"
            "this file. Bake the Leaf mesh, make a Physically Based material and\n"
            "load the Color, Normal and Alpha images. Turn Write off while you edit.")
    o = outline(d, 400, 300, Length=(100, 20, 200, False), Width=(55, 10, 150, False),
                Teeth=(12, 0, 40, True), ToothAmp=(3.5, 0, 10, False))
    v = venation(d, 750, 330, preset=3)
    d.wire(o, "Outline", v, "Boundary")
    d.wire(o, "Base", v, "Seeds")
    t = d.plugin(LEAF_TEXTURE, 1100, 380)
    t.Hidden = False
    d.wire(v, "Venation", t, "Venation")
    d.wire(d.slider("Size", 1024, 256, 4096, 850, 470, integer=True), None, t, "Size")
    d.wire(d.toggle("Write", True, 850, 500), None, t, "Write")
    d.wire(t, "Leaf", d.param("Mesh", 1350, 330), None)
    for i, name in enumerate(["Color", "Height", "Normal", "Alpha"]):
        d.wire(t, name, d.panel("", 1350, 380 + i * 50, 320, 40), None)
    return d


def main():
    load_grasshopper()
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    done, failed = [], []
    for build in (step2, step3, step4, step5, step6, step7, step8, step9):
        try:
            done.append(build().save())
        except Exception as e:
            failed.append("%s: %s" % (build.__name__, e))
    print("Saved %d example files to %s" % (len(done), OUT))
    for f in failed:
        print("Not saved, " + f)


main()
