import glob
import shutil
import os


def main():
    flatten_directory("BP/features")
    flatten_directory("BP/biomes")


def flatten_directory(directory: str):
    """
    Flattens the directory, by copying all files in the directory to the root directory.
    Does not handle files with the same name.
    """
    # Flatten directory
    for file in glob.glob(f"{directory}/**/*.json"):
        from_location = os.path.abspath(file)
        to_location = os.path.abspath(os.path.join(directory, os.path.basename(file)))
        shutil.move(from_location, to_location)

    # Remove empty directories
    for folder in glob.glob("BP/features/**/*"):
        if os.path.isdir(folder):
            shutil.rmtree(folder)
main()