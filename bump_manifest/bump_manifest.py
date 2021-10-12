import os
import json
from typing import List

def create_version_file() -> None:
    """
    Creates a version file.
    """

    os.mkdir('./data/')
    os.mkdir('./data/bump_manifest/')
    with open('./data/bump_manifest/version.json', 'a') as file:
        json.dump({'version': [1, 0, 0]}, file)

def get_version() -> str:
    """
    Gets the current version number from the version.json file.
    """

    path = './data/bump_manifest/version.json'

    # Create version file, if it doesn't exist
    if not os.path.exists(path):
        create_version_file()

    with open(path, 'r') as f:
        return json.load(f)['version']

def update_version(version: List[int]):
    """
    Takes in a version string and updates the minor version number by one.
    """

    version[-1] = version[-1] + 1


def update_manifest(manifest: dict):
    """
    Takes in a manifest and updates the minor version number by one.
    """

    version = manifest['header']['version']
    update_version(version)
    manifest['header']['version'] = version

    for module in manifest.get("modules", []):
        module['version'] = version

    for dependency in manifest.get("dependencies", []):
        dependency['version'] = version

    return manifest
    
def main():
    """
    Program execution begins here.
    """

    # Get current version, and update
    version = get_version()
    update_version(version)
    print("Pack updated to version: ", str(version))

    # Write new version to resource pack
    try:
        with open('RP/manifest.json') as manifest_file:
            manifest = json.load(manifest_file)
            json.dump(update_manifest(manifest), manifest_file)
    except FileNotFoundError:
        pass

    # Write new version to resource pack
    try:
        with open('BP/manifest.json') as manifest_file:
            manifest = json.load(manifest_file)
            json.dump(update_manifest(manifest), manifest_file)
    except FileNotFoundError:
        pass

if __name__ == "__main__":
    main()