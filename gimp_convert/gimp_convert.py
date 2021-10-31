from gimpformats.gimpXcfDocument import GimpDocument
import os

for root, d_names,f_names in os.walk("."):
    for f in f_names:
        if f.endswith(".xcf"):
            gpath = os.path.join(root, f)
            gfile = GimpDocument()
            gfile.load(gpath)
            gfile.image.save(gpath[:-4]+".png", "png")
            os.remove(gpath)