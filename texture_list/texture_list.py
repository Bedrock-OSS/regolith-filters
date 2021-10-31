import json
from itertools import chain
from pathlib import Path


TEXTURES_PATH = Path("RP/textures")

def list_textures():
    textures = []
    for texture in chain(
            TEXTURES_PATH.glob("**/*.png"), TEXTURES_PATH.glob("**/*.tga")):
        textures.append(texture.relative_to("RP").with_suffix("").as_posix())
    return textures

def main():
    texture_list_path = TEXTURES_PATH / "texture_list.json"
    texture_list_path.parent.mkdir(parents=True, exist_ok=True)

    with texture_list_path.open("w") as f:
        json.dump(list_textures(), f, indent='\t')

if __name__ == "__main__":
    main()