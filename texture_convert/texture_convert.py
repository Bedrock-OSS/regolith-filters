from gimpformats.gimpXcfDocument import GimpDocument
import zipfile
import os
from psd_tools import PSDImage

for root, d_names,f_names in os.walk("."):
    for f in f_names:
        replaced = False
        imgpath = os.path.join(root, f)
        if f.endswith(".xcf"):
            replaced = True
            gfile = GimpDocument()
            gfile.load(imgpath)
            gfile.image.save(imgpath[:-4]+".png", "png")
        if f.endswith(".kra"):
            replaced = True
            with zipfile.ZipFile(imgpath) as z:
                with open(imgpath.replace('.kra', '.png'), 'wb') as f2:
                    f2.write(z.read('preview.png'))
        if f.endswith(".psd"):
            replaced = True
            psd = PSDImage.open(imgpath)
            psd.composite().save(imgpath[:-4]+".png")
        if replaced:
            os.remove(imgpath)