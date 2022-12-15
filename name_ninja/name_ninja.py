"""
This filter is used to automatically generate entity, block, and item names,
based on a custom 'name' field, or automatically generated based on the entities
identifier. See 'readme.md' for more information.
"""

import sys
import json
from typing import List
from enum import Enum

from reticulator import *

class AssetType(Enum):
    SPAWN_EGG = 1
    ITEM = 2
    BLOCK = 3
    ENTITY = 4

def generate_localization_key(asset_type: AssetType, asset: JsonResource):
    """
    Generates the localization key for the asset type. May depend on format version,
    or other things.
    """

    # All assets that we are generating names for have a 'identifier' key.
    identifier = asset.identifier

    if asset_type == AssetType.ENTITY:
        key = "entity.identifier.name"
    elif asset_type == AssetType.ITEM:
        # TODO: What should happen if 1.16.100 items have DisplayName component?

        # Handle the different formats for items
        if FormatVersion(asset.format_version) < FormatVersion('1.16.100'):
            key = "item.identifier.name"
        else:
            key = "item.identifier"
    elif asset_type == AssetType.BLOCK:
        key = "tile.identifier.name"
    elif asset_type == AssetType.SPAWN_EGG:
        key = "item.spawn_egg.entity.identifier.name"

    # Finally, do the replacement and return
    return key.replace("identifier", identifier)

def format_name(name: str):
    """
    Formats a name based on the entity's identifier, removing the namespace.
    """
    return name.split(":")[1].replace("_", " ").title()

def gather_translations(asset_type: str, assets: List[JsonFileResource], settings: dict, name_jsonpath: str, ignored_namespaces) -> List[Translation]:
    """
    Gathers translations from the behavior pack.
    """
    auto_name = settings.get('auto_name', False)
    prefix = settings.get('prefix', '')
    postfix = settings.get('postfix', '')

    translations : List[Translation] = []

    for asset in assets:
        try:
            identifier = asset.identifier
        except AssetNotFoundError:
            print(f"Warning: {asset.filepath} has no identifier, skipping...")
            continue

        # Skip assets that are in ignored namespaces (e.g. minecraft:zombie)
        if identifier.split(':')[0] in ignored_namespaces:
            continue
        
        localization_key = generate_localization_key(asset_type, asset)

        # Allow for generate_localization_key to return None (skip)
        if localization_key is None:
            continue

        # Try/except to handle the case where the asset doesn't have a name.
        # If this happens, we optionally name the entity automatically.
        try:
            # Since we process spawn_eggs before entities, we should ensure that spawn_eggs don't delete the name key
            if asset_type == AssetType.SPAWN_EGG:
                localization_value = asset.get_jsonpath(name_jsonpath)
            else:
                localization_value = asset.pop_jsonpath(name_jsonpath)
        except AssetNotFoundError:
            if auto_name:
                localization_value = prefix + format_name(identifier) + postfix
            else:
                continue
        
        translations.append(Translation(localization_key, localization_value, ""))
    
    return translations

def main():
    """
    The entry point for the script.
    """
    try:
        settings = json.loads(sys.argv[1])
    except IndexError:
        print("Warning: No settings provided. Using default settings.")
        settings = {}

    # Detect settings, and set defaults if not provided.
    overwrite = settings.get("overwrite", False)
    language = settings.get("language", "en_US.lang")
    sort = settings.get("sort", False)
    ignored_namespaces = settings.get("ignored_namespaces", ['minecraft'])
    project = Project("./BP", "./RP")
    behavior_pack = project.behavior_pack
    resource_pack = project.resource_pack

    translations = []

    translations.extend(gather_translations(AssetType.SPAWN_EGG, behavior_pack.entities, settings.get("spawn_eggs", {}), "minecraft:entity/description/name", ignored_namespaces))
    translations.extend(gather_translations(AssetType.ITEM, behavior_pack.items, settings.get("items", {}), "minecraft:item/description/name", ignored_namespaces))
    translations.extend(gather_translations(AssetType.BLOCK, behavior_pack.blocks, settings.get("blocks", {}), "minecraft:block/description/name", ignored_namespaces))
    translations.extend(gather_translations(AssetType.ENTITY, behavior_pack.entities, settings.get("entities", {}), "minecraft:entity/description/name", ignored_namespaces))

    try:
        language_file = resource_pack.get_language_file("texts/" + language)
    except AssetNotFoundError:
        print(f"Warning: {language} file not found, creating...")
        Path(os.path.join(resource_pack.input_path, 'texts')).mkdir(parents=True, exist_ok=True)
        open(os.path.join(resource_pack.input_path, 'texts', language), 'a').close()
        language_file = LanguageFile(filepath=f'texts/{language}', pack=resource_pack)

    for translation in translations:
        language_file.add_translation(translation, overwrite = overwrite)

    if sort:
        language_file.translations.sort(key=lambda t: t.key)
    project.save()

if __name__ == "__main__":
    main()