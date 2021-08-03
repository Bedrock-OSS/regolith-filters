import glob, os, json

def list_textures():
    textures = []
    for texture in glob.glob("./RP/textures/**/*.png")+glob.glob("./RP/textures/**/*.tga"):
        bn = os.path.splitext(os.path.basename(texture))[1]
        texture = texture.replace(bn,"").replace("./","").replace("\\","/").replace("RP/", "", 1)
        textures.append(texture)
    return textures

if not os.path.exists("./RP/textures/texture_list.json"):
    with open("./RP/textures/texture_list.json", "w") as f:
        json.dump(list_textures(), f, indent=2)

list_textures()