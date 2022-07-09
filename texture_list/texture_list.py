import json
from itertools import chain
from pathlib import Path

ROOT_PATH = Path("RP")
SUBPACK_PATH = ROOT_PATH / "subpacks"


def fetch_subpack_folders():
    """
    Fetches a list of all subpack folders in the resource-pack.
    """
    if SUBPACK_PATH.exists():
        for subpack_folder in SUBPACK_PATH.iterdir():
            if subpack_folder.is_dir() and (subpack_folder / "textures").exists():
                yield subpack_folder

def list_textures(root_folder: Path):
    """
    Lists all textures within the 'textures' folder within the path. For example
    pass in 'RP", and it will search 'RP/textures'.
    """
    textures = []
    textures_folder = root_folder / "textures"

    for texture in chain(textures_folder.glob("**/*.png"), textures_folder.glob("**/*.tga")):
        textures.append(texture.relative_to(root_folder).with_suffix("").as_posix())
    return textures

def generate_texture_list_file(root_folder: Path, textures):
    """
    Generates root_folder/textures/texture_list.json
    """
    if len(textures) > 0:
        with open(root_folder / "textures" / "texture_list.json", "w") as f:
            json.dump(textures, f, indent='\t')


def main():
    # Handle the root resource pack file
    pack_textures = list_textures(ROOT_PATH);
    generate_texture_list_file(ROOT_PATH, pack_textures)

    for subpack_folder in fetch_subpack_folders():
        # list+set is a way of crushing duplicates out of a list
        subpack_textures = list(set(list_textures(subpack_folder) + pack_textures))
        generate_texture_list_file(subpack_folder, subpack_textures)

if __name__ == "__main__":
    """
    The entry-point of the script.
    """
    main()