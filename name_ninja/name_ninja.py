"""
This filter is used to automatically generate entity, block, and item names,
based on a custom 'name' field, or automatically generated based on the entities
identifier. See 'readme.md' for more information.
"""

import sys
import json
from typing import List, NamedTuple
from enum import Enum

from reticulator import *

class AssetType(Enum):
    SPAWN_EGG = 1
    ITEM = 2
    BLOCK = 3
    ENTITY = 4

class NameJsonPath(NamedTuple):
    """Describes a jsonpath candidate when gathering translations.

    path: the JSONPath to read
    should_pop: whether the value should be removed from the underlying JSON once read
    add_affixes: if True, the gathered value will be wrapped with prefix/postfix.
    """
    path: str
    should_pop: bool = False
    add_affixes: bool = False

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

def gather_translations(asset_type: str, assets: List[JsonFileResource], settings: dict, name_jsonpaths: List[NameJsonPath], ignored_namespaces) -> List[Translation]:
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

        # Try loading localization_value from JSON paths
        localization_value = None
        for jp in name_jsonpaths:
            path = jp.path
            should_pop = jp.should_pop

            try:
                # Pop the value if requested
                if should_pop:
                    localization_value = asset.pop_jsonpath(path)
                else:
                    localization_value = asset.get_jsonpath(path)
                # Add affixes if requested
                if localization_value is not None and jp.add_affixes:
                    localization_value = prefix + localization_value + postfix
                # Found a valid name, break
                break
            except AssetNotFoundError:
                pass

        # Try auto_naming using identifier
        if (
                localization_value is None and
                auto_name in [True, "from_entity_name"]):
            localization_value = prefix + format_name(identifier) + postfix

        # If after all strategies no localization value was resolved, skip this asset.
        if localization_value is None:
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

    # Handle backward compatibility
    if "languages" in settings:
        languages = settings["languages"]
        if isinstance(languages, str):
            languages = [languages]
            print("Warning: The 'languages' setting should be an array of strings. A single string was provided and automatically converted to a list.")
        elif not isinstance(languages, list):
            raise ValueError("The 'languages' setting must be a list of strings.")
    else:
        language = settings.get("language", "en_US.lang")
        if isinstance(language, str):
            languages = [language]
            print("Warning: The 'language' setting is deprecated in the latest version. Please use 'languages' instead for future configurations.")
        else:
            raise ValueError("The 'language' setting must be a string if 'languages' is not provided.")

    sort = settings.get("sort", False)
    ignored_namespaces = settings.get("ignored_namespaces", ['minecraft'])
    project = Project("./BP", "./RP")
    behavior_pack = project.behavior_pack
    resource_pack = project.resource_pack

    translations = []

    translations.extend(
        gather_translations(
            AssetType.SPAWN_EGG,
            behavior_pack.entities,
            settings.get("spawn_eggs", {}),
            [
                # First try `spawn_egg_name` and pop it if found (no affixes)
                NameJsonPath("minecraft:entity/description/spawn_egg_name", True, False),
                # Fallback to entity name; add affixes only when auto_name == "from_entity_name"
                NameJsonPath("minecraft:entity/description/name", False, settings.get("spawn_eggs", {}).get("auto_name") == "from_entity_name"),
            ],
            ignored_namespaces,
        )
    )

    translations.extend(
        gather_translations(
            AssetType.ITEM,
            behavior_pack.items,
            settings.get("items", {}),
            [NameJsonPath("minecraft:item/description/name", True, False)],
            ignored_namespaces,
        )
    )

    translations.extend(
        gather_translations(
            AssetType.BLOCK,
            behavior_pack.blocks,
            settings.get("blocks", {}),
            [NameJsonPath("minecraft:block/description/name", True, False)],
            ignored_namespaces,
        )
    )

    translations.extend(
        gather_translations(
            AssetType.ENTITY,
            behavior_pack.entities,
            settings.get("entities", {}),
            [NameJsonPath("minecraft:entity/description/name", True, False)],
            ignored_namespaces,
        )
    )

    for language in languages:
        try:
            language_file = resource_pack.get_language_file(f"texts/{language}")
        except AssetNotFoundError:
            print(f"Warning: {language} file not found, creating...")
            Path(os.path.join(resource_pack.input_path, 'texts')).mkdir(parents=True, exist_ok=True)
            open(os.path.join(resource_pack.input_path, 'texts', language), 'a').close()
            language_file = LanguageFile(filepath=f'texts/{language}', pack=resource_pack)

        for translation in translations:
            language_file.add_translation(translation, overwrite=overwrite)

        if sort:
            language_file.translations.sort(key=lambda t: t.key)

    project.save()

if __name__ == "__main__":
    main()