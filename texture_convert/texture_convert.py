import layeredimage.io
import zipfile
import os

for root, d_names,f_names in os.walk("."):
    for f in f_names:
        imgpath = os.path.join(root, f)
        replaced = False
        ext = f.split(".")[1]
        if ext in ["pdn", "xcf", "psd"]:
            replaced = True
            img = layeredimage.io.openLayerImage(imgpath)
            img.getFlattenLayers().save(imgpath.replace('.' + ext, '.png'))
        if f.endswith(".kra"):
            replaced = True
            with zipfile.ZipFile(imgpath) as z:
                with open(imgpath.replace('.kra', '.png'), 'wb') as f2:
                    f2.write(z.read('preview.png'))
        if replaced:
            os.remove(imgpath)