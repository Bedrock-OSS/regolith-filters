from pathlib import Path
import layeredimage.io
import zipfile
from PIL import Image, ImageSequence

def convert_kra(imgpath: Path):
    '''
    Converts a Krita file to a PNG.
    '''
    # Krita files are actually zip files
    with zipfile.ZipFile(imgpath) as z:
        with imgpath.with_suffix(".png").open("wb") as f2:
            f2.write(z.read("preview.png"))

def convert_layered(imgpath: Path):
    '''
    Converts a layered image format (like .pdn, .xcf or .psd) to a flattened
    PNG.
    '''
    img = layeredimage.io.openLayerImage(imgpath)
    img.getFlattenLayers().save(imgpath.with_suffix(".png"))

def convert_gif(imgpath: Path):
    '''
    Converts a GIF file to a PNG sprite sheet.
    '''
    with Image.open(imgpath) as img:
        frames = ImageSequence.all_frames(img)

    frame_width = frames[0].width
    frame_height = frames[0].height
    atlas_height = frame_height * len(frames)

    # Create canvas for atlas
    atlas = Image.new("RGBA", (frame_width, atlas_height))

    for index, frame in enumerate(frames):
        atlas.paste(frame, (0, index * frame_height))
    atlas.save(imgpath.with_suffix(".png"))


# EXECUTE SCRIPT
if __name__ == "__main__":
    for imgpath in Path(".").rglob("*"):
        if not imgpath.is_file():
            continue
        if imgpath.suffix in [".pdn", ".xcf", ".psd"]:
            convert_layered(imgpath)
            imgpath.unlink()
        elif imgpath.suffix == ".kra":
            convert_kra(imgpath)
            imgpath.unlink()
        elif imgpath.suffix == ".gif":
            convert_gif(imgpath)
            imgpath.unlink()