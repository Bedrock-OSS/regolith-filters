import os
import json
from typing import List
from pathlib import Path

def create_version_file() -> None:
    """
    Creates a version file.
    """

    Path("./data/bump_manifest/").mkdir(parents=True, exist_ok=True)

    with open('./data/bump_manifest/version.json', 'a') as file:
        json.dump({'version': [1, 0, 0]}, file)

def get_version() -> str:
    """
    Gets the current version number from the version.json file.

    Saves new version back to the file.
    """

    path = './data/bump_manifest/version.json'

    # Create version file, if it doesn't exist
    if not os.path.exists(path):
        create_version_file()

    # Read version file
    with open(path, 'r') as f:
        data = json.load(f)

    # Update version file
    data['version'] = data['version'][-1] + 1
    with open(path, 'w') as f:
        json.dump(f)

    return data['version']


def update_manifest(manifest: dict, version: List[int] = None) -> dict:
    """
    Takes in a manifest and updates the minor version number by one.
    """

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

    # Get current version, and update the file
    version = get_version()

    print("Pack updated to version: ", str(version))

    # Write new version to resource pack
    try:
        with open('./RP/manifest.json', 'r') as manifest_file:
            manifest = json.load(manifest_file)

        with open('./RP/manifest.json', 'w') as manifest_file:
            json.dump(update_manifest(manifest, version), manifest_file, indent=4)
    except FileNotFoundError:
        pass

    # Write new version to resource pack
    try:
        with open('./BP/manifest.json', 'r') as manifest_file:
            manifest = json.load(manifest_file)

        with open('./BP/manifest.json', 'w') as manifest_file:
            json.dump(update_manifest(manifest, version), manifest_file, indent=4)

    except FileNotFoundError:
        pass

if __name__ == "__main__":
    main()