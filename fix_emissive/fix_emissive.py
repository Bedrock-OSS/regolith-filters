import glob

from PIL import Image


def fix(input_img, output_img):
    img = Image.open(input_img)
    pixels = img.load()

    for i in range(img.size[0]):
        for j in range(img.size[1]):
            if pixels[i, j][3] == 0:
                pixels[i, j] = (0, 0, 0, 0)

    img.save(output_img)


for texture in glob.glob("./RP/textures/**/*.png"):
    fix(texture, texture)
