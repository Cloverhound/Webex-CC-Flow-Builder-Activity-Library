#!/usr/bin/env python3
"""Build sample_flow.drawio from the generated library, so the sample always matches it.

Usage: python3 build_sample_flow.py [library.xml] [output.drawio]
"""
import base64, json, sys, urllib.parse, zlib
import xml.etree.ElementTree as ET

LIB = sys.argv[1] if len(sys.argv) > 1 else "WxCC-FlowBuilder-Activities.xml"
OUT = sys.argv[2] if len(sys.argv) > 2 else "sample_flow.drawio"

NORMAL, ERROR, TIMEOUT = "#1170cf", "#ab0a15", "#7d4705"
HDR_CENTER = 28   # matches the library's input point (header row centre)

# key: (library title, x, y)
NODES = {
    "start":  ("Start Flow",         0,    60),
    "hours":  ("Business Hours",     330,  0),
    "menu":   ("Menu",               660,  0),
    "closed": ("Play Message",       660,  440),
    "queue":  ("Queue Contact",      990,  0),
    "xfer":   ("Blind Transfer",     990,  380),
    "dcA":    ("Disconnect Contact", 990,  640),
    "music":  ("Play Music",         1320, 0),
    "dcB":    ("Disconnect Contact", 1320, 260),
    "end":    ("End Flow",           1650, 0),
}
# (source key, exit label, target key, colour)
EDGES = [
    ("start",  "Out",              "hours",  NORMAL),
    ("hours",  "Working Hours",    "menu",   NORMAL),
    ("hours",  "Holidays",         "closed", NORMAL),
    ("closed", "Default",          "dcA",    NORMAL),
    ("menu",   "Option 0",         "queue",  NORMAL),
    ("menu",   "Option 1",         "xfer",   NORMAL),
    ("menu",   "No-Input Timeout", "dcB",    TIMEOUT),
    ("queue",  "Default",          "music",  NORMAL),
    ("queue",  "Failure",          "dcB",    ERROR),
    ("music",  "Default",          "end",    NORMAL),
]

text = open(LIB).read()
items = {i["title"]: i for i in json.loads(text[len("<mxlibrary>"):-len("</mxlibrary>")])}


def load(title):
    xml = urllib.parse.unquote(zlib.decompress(base64.b64decode(items[title]["xml"]), -15).decode())
    return ET.fromstring(xml)


out_cells, row_ids, root_ids = [], {}, {}
for key, (title, x, y) in NODES.items():
    model = load(title)
    for c in model.iter("mxCell"):
        cid = c.get("id")
        if cid in ("0", "1"):
            continue
        c.set("id", f"{key}_{cid}")
        parent = c.get("parent")
        c.set("parent", "1" if parent == "1" else f"{key}_{parent}")
        g = c.find("mxGeometry")
        if cid == "2":                       # card: drop it expanded
            alt = g.find("mxRectangle")
            c.attrib.pop("collapsed", None)
            g.set("width", alt.get("width")); g.set("height", alt.get("height"))
            g.set("x", str(x)); g.set("y", str(y)); g.remove(alt)
            root_ids[key] = c.get("id")
        if c.get("style", "").startswith("label"):
            row_ids[(key, c.get("value"))] = c.get("id")
        out_cells.append(c)

n = 100
for src, label, dst, color in EDGES:
    style = ("rounded=1;orthogonalLoop=1;jettySize=auto;edgeStyle=orthogonalEdgeStyle;"
             f"strokeColor={color};strokeWidth=2;fillColor=none;startArrow=oval;startFill=1;"
             "startSize=6;endArrow=block;endFill=1;"
             "exitX=1;exitY=0.5;exitDx=0;exitDy=0;exitPerimeter=0;"
             f"entryX=0;entryY=0;entryDx=0;entryDy={HDR_CENTER};entryPerimeter=0;")
    e = ET.Element("mxCell", id=f"e{n}", value="", style=style, edge="1", parent="1",
                   source=row_ids[(src, label)], target=root_ids[dst])
    g = ET.SubElement(e, "mxGeometry", relative="1"); g.set("as", "geometry")
    out_cells.append(e); n += 1

model = ET.Element("mxGraphModel", dx="1706", dy="934", grid="1", gridSize="10", guides="1",
                   tooltips="1", connect="1", arrows="1", fold="1", page="0", math="0", shadow="0")
root = ET.SubElement(model, "root")
ET.SubElement(root, "mxCell", id="0")
ET.SubElement(root, "mxCell", id="1", parent="0")
root.extend(out_cells)

diagram = ET.Element("mxfile", host="app.diagrams.net")
d = ET.SubElement(diagram, "diagram", name="WxCC Inbound Call Flow", id="0")
d.append(model)
ET.indent(diagram)
ET.ElementTree(diagram).write(OUT, encoding="utf-8", xml_declaration=False)
print(f"Wrote {OUT}: {len(NODES)} nodes, {len(EDGES)} connections")
