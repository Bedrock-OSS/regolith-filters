from pathlib import Path  # Import the Path class for cleaner path handling.
import layeredimage.io  # Import the layeredimage library for handling layered image formats like PSD, PDN, XCF.
import zipfile  # Import the zipfile module to handle zip files (used for .kra format images).

def convert_kra(imgpath: Path):
    with zipfile.ZipFile(imgpath) as z:  # Open the .kra file as a zip archive.
        with imgpath.with_suffix(".png").open(
            "wb"
        ) as f2:  # Create the output PNG file.
            f2.write(z.read("preview.png"))  # Write the preview image to the PNG file.


def convert_layered(imgpath: Path):
    img = layeredimage.io.openLayerImage(imgpath)  # Open the layered image.
    img.getFlattenLayers().save(imgpath.with_suffix(".png"))  # Flatten and save as PNG.


# EXECUTE SCRIPT
if __name__ == "__main__":

    # Use rglob to recursively search for files in all subdirectories.
    for imgpath in Path(".").rglob("*"):

        # Check if the current item is a file.
        if imgpath.is_file():

            # Handle Photoshop, paint.net and XCF file
            if imgpath.suffix in [".pdn", ".xcf", ".psd"]:
                convert_layered(imgpath)  # Convert layered formats to png
                imgpath.unlink()  # Delete the original file.

            # Handle Krita file
            if imgpath.suffix == ".kra":
                convert_kra(imgpath)  # Convert .kra to png
                imgpath.unlink()  # Delete the original file.