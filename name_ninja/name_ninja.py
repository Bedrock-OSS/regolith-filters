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

# TODO: Consider moving this into Reticulator
class FormatVersion():
    def __init__(self, version: str) -> None:
        elements = version.split('.')

        # Pack with extra data if it's missing
        for i in range(3 - len(elements)):
            elements.append('0')
        
        self.major = int(elements[0])
        self.minor = int(elements[1])
        self.patch = int(elements[2])

    def __repr__(self) -> str:
        return f'{self.major}.{self.minor}.{self.patch}'
        
    def __eq__(self, other):
        return self.major == other.major and self.minor == other.minor and self.patch == other.patch

    def __gt__(self, other):
        if self.major > other.major:
            return True
        elif self.major < other.major:
            return False

        if self.minor > other.minor:
            return True
        elif self.minor < other.minor:
            return False

        if self.patch > other.patch:
            return True
        elif self.patch < other.patch:
            return False
        
        return self != other

def gather_translations(asset_type: str, settings: dict, ignored_namespaces):
    auto_name = settings.get('auto_name', False)
    prefix = settings.get('prefix', '')
    postfix = settings.get('postfix', '')

    # Generate path name
    match asset_type:
        case AssetType.ITEM:
            asset_path = './BP/items/**/*.json'
            json_path =  "minecraft:item/description"
        case AssetType.BLOCK:
            asset_path = './BP/blocks/**/*.json'
            json_path =  "minecraft:block/description"
        case AssetType.ENTITY:
            asset_path = './BP/entities/**/*.json'
            json_path =  "minecraft:entity/description"
        case AssetType.SPAWN_EGG:
            asset_path = './BP/entities/**/*.json'
            json_path =  "minecraft:entity/description"
        case _:
            return

    asset_paths = glob.glob(asset_path, recursive=True)
    translations : List[Translation] = []

    for asset_file in asset_paths:
        # Open asset and collect information
        with open(asset_file) as io:
            file = json.load(io)

            # Get format version
            try: 
                format_version = dpath.util.get(file, 'format_version')
            except(KeyError):
                print(f"Warning: {asset_file} has no format_version, skipping...")
                continue
            
            # Get identifier
            try: 
                identifier = dpath.util.get(file, f'{json_path}/identifier')
            except(KeyError):
                print(f"Warning: {asset_file} has no identifier, skipping...")
                continue
            
            # Get name (if not auto_name)
            try:
                name = dpath.util.get(file, f'{json_path}/name')
                if asset_type != AssetType.SPAWN_EGG:
                    dpath.util.delete(file, f'{json_path}/name')
            except(KeyError):
                if auto_name:
                    pass
                else:
                    print(f"Warning: {asset_file} has no name key, skipping...")
                    continue
        
        # Skip assets that are in ignored namespaces (e.g. minecraft:zombie)
        if identifier.split(':')[0] in ignored_namespaces:
            continue

        # GET LOCALISATION KEY
        localization_key = generate_localization_key(asset_type, format_version).replace("identifier", identifier)

        # Use settings if auto_name enabled
        if auto_name:
            localization_value = prefix + format_name(identifier) + postfix
        else:
            localization_value = name

        translations.append(Translation(localization_key, localization_value, ""))

    return translations

def generate_localization_key(asset_type: AssetType, format_version):
    """
    Generates the localization key for the asset type. May depend on format version,
    or other things.
    """

    if asset_type == AssetType.ENTITY:
        key = "entity.identifier.name"
    elif asset_type == AssetType.ITEM:
        # TODO: What should happen if 1.16.100 items have DisplayName component?

        # Handle the different formats for items
        if FormatVersion(format_version) < FormatVersion('1.16.100'):
            key = "item.identifier.name"
        else:
            key = "item.identifier"
    elif asset_type == AssetType.BLOCK:
        key = "tile.identifier.name"
    elif asset_type == AssetType.SPAWN_EGG:
        key = "item.spawn_egg.entity.identifier.name"

    # Finally, do the replacement and return
    return key

def format_name(name: str):
    """
    Formats a name based on the entity's identifier, removing the namespace.
    """
    return name.split(":")[1].replace("_", " ").title()

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
    languages = settings.get("languages", ["en_US.lang"])
    sort = settings.get("sort", False)
    ignored_namespaces = settings.get("ignored_namespaces", ['minecraft'])
    project = Project("./BP", "./RP")
    bp = project.behavior_pack
    resource_pack = project.resource_pack

    translations = []

    translations.extend(gather_translations(AssetType.ITEM,settings.get("items", {}), ignored_namespaces))
    translations.extend(gather_translations(AssetType.BLOCK,settings.get("blocks", {}), ignored_namespaces))
    translations.extend(gather_translations(AssetType.SPAWN_EGG,settings.get("spawn_eggs", {}), ignored_namespaces))
    translations.extend(gather_translations(AssetType.ENTITY,settings.get("entities", {}), ignored_namespaces))

    if isinstance(languages, str):
        languages = [languages]
    for language in languages:
        try:
            language_file = resource_pack.get_language_file("texts/" + language)
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