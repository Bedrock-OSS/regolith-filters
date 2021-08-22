import glob
from pathlib import Path
import json

def save_lang_list(pack_type):
    try:
        languages = []
        for file in glob.glob(f"{pack_type}/texts/*.lang"):
            languages.append(Path(file).stem)
        with open(f"{pack_type}/texts/languages.json", 'w+') as f:
            json.dump(languages, f)
    except Exception as e:
        print(e)

def main():
    save_lang_list("RP")
    save_lang_list("BP")

main()