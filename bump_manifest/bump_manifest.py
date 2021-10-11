import os
import json

def create_version_file() -> None:
    """
    Creates a version file if it doesn't exist.
    """

    os.mkdir('data/')
    os.mkdir('data/bump_manifest/')
    with open('data/bump_manifest/version.json', 'a') as file:
        json.dump({'version': '0.0.0'}, file)

def get_version() -> str:
    """
    Gets the current version number from the version.json file.
    """

    path = 'data/bump_manifest/'

    # Create version file, if it doesn't exist
    if not os.path.exists(path):
        create_version_file()

    with open(path, 'r') as f:
        return json.load(f)['version']

def update_version(version: str) -> str:
    """
    Takes in a version string and updates the minor version number by one.
    """

    split = version.split('.')
    split[-1] = str(int(split[-1]) + 1)
    return '.'.join(split)

def main():
    """
    Program execution begins here.
    """

    version = get_version()
    new_version = update_version(version)

    with open('RP/manifest.json') as manifest:
        pass

if __name__ == "__main__":
    main()