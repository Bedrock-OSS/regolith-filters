import glob
import zipfile
import os

def main():
    for file in glob.glob("**/*.kra"):
        with zipfile.ZipFile(file) as z:
            with open(file.replace('.kra', '.png'), 'wb') as f:
                f.write(z.read('preview.png'))
        os.remove(file)

main()
