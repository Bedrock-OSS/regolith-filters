"""
This filter is used to automatically generate entity, block, and item names,
based on a custom 'name' field, or automatically generated based on the entities
identifier.
"""

import sys
import json
from typing import List

from reticulator import *

def format_name(name: str):
    """
    Formats a name based on the entity's identifier, removing the namespace.
    """
    return name.split(":")[1].replace("_", " ").title()

def gather_translations(assets: List[JsonFileResource], settings: dict, name_jsonpath: str, localization_key_format: str, remove_field: bool) -> List[Translation]:
    """
    Gathers translations from the behavior pack.
    """
    auto_name = settings.get('auto_name', False)
    prefix = settings.get('prefix', '')
    postfix = settings.get('postfix', '')

    translations : List[Translation] = []

    for asset in assets:
        # A little bit of magic here: All assets are expected to have an identifier
        identifier = asset.identifier
        localization_key = localization_key_format.replace("identifier", identifier)

        try:
            if remove_field:
                name = asset.pop_value_at(name_jsonpath)
            else:
                name = asset.get_value_at(name_jsonpath)
        except KeyError:
            if auto_name:
                name = prefix + format_name(identifier) + postfix
            else:
                continue
        
        translations.append(Translation(localization_key, name, "Generated via Regolith."))
    
    return translations


def main():
    """
    The entry point for the script.
    """
    try:
        settings = json.loads(sys.argv[1])
    except IndexError:
        settings = {}

    overwrite = settings.get("overwrite", False)
    language = settings.get("language", "en_US.lang")
    sort = settings.get("sort", False)

    project = Project("./BP", "./RP")
    behavior_pack = project.behavior_pack
    resource_pack = project.resource_pack

    translations = []

    translations.extend(gather_translations(behavior_pack.entities, settings.get("entities", {}), "minecraft:entity/description/name", "entity.identifier.name", False))
    translations.extend(gather_translations(behavior_pack.items, settings.get("items", {}), "minecraft:item/description/name", "item.identifier", True))
    translations.extend(gather_translations(behavior_pack.blocks, settings.get("blocks", {}), "minecraft:block/description/name", "tile.identifier.name", True))
    translations.extend(gather_translations(behavior_pack.entities, settings.get("spawn_eggs", {}), "minecraft:entity/description/name", "item.spawn_egg.entity.identifier.name", True))

    try:
        language_file = resource_pack.get_language_file(language)
    except AssetNotFoundError:
        print(f"Warning: {language} file not found, creating...")
        Path(os.path.join(resource_pack.input_path, 'texts')).mkdir(parents=True, exist_ok=True)
        open(os.path.join(resource_pack.input_path, 'texts', language), 'a').close()
        language_file = LanguageFile(file_path=f'texts/{language}', pack=resource_pack)

    for translation in translations:
        language_file.add_translation(translation, overwrite = overwrite)

    if sort:
        language_file.translations.sort(key=lambda t: t.key)
    project.save()

if __name__ == "__main__":
    main()