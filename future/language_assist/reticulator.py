from __future__ import annotations
from dataclasses import dataclass
import re
import os
import json
from pathlib import Path
import glob
from functools import cached_property
from io import TextIOWrapper
from send2trash import send2trash

# Constants

DOT_MATCHER_REGEX = re.compile(r"\.(?=(?:[^\"']*[\"'][^\"']*[\"'])*[^\"']*$)")

# Globals

def create_nested_directory(path: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)

def freeze(o):
    if isinstance(o,dict):
        return frozenset({ k:freeze(v) for k,v in o.items()}.items())

    if isinstance(o,list):
        return tuple([freeze(v) for v in o])
    
    return o


def make_hash(o):
    """
    makes a hash out of anything that contains only list,dict and hashable types including string and numeric types
    """
    return hash(freeze(o))

# region exceptions
class ReticulatorException(Exception):
    """
    Base class for Reticulator exceptions.
    """

class FloatingAssetError(ReticulatorException):
    """
    Called when a "floating" asset attempts to access its parent pack, for
    example when saving
    """

class AssetNotFoundError(ReticulatorException):
    """
    Called when attempting to access an asset that does not exist, for
    example getting an entity by name
    """

class AmbiguousAssetError(ReticulatorException):
    """
    Called when a path is not unique
    """

#endregion

# region notify classes


# TODO: Replace these with a hash-based edit-detection method?

class NotifyDict(dict):
    """
    A notify dictionary is a dictionary that can notify its parent when its been
    edited.
    """
    def __init__(self, *args, owner: Resource = None, **kwargs):
        self.__owner = owner

        if len(args) > 0:
            for key, value in args[0].items():
                if isinstance(value, dict):
                    args[0][key] = NotifyDict(value, owner=self.__owner)
                if isinstance(value, list):
                    args[0][key] = NotifyList(value, owner=self.__owner)
        super().__init__(*args, **kwargs)


    def get_item(self, attr):
        try:
            return self.__getitem__(attr)
        except:
            return None
    
    def __delitem__(self, v) -> None:
        if(self.__owner != None):
            self.__owner.dirty = True
        return super().__delitem__(v)

    def __setitem__(self, attr, value):
        if isinstance(value, dict):
            value = NotifyDict(value, owner=self.__owner)
        if isinstance(value, list):
            value = NotifyList(value, owner=self.__owner)

        if self.get_item(attr) != value:
            if(self.__owner != None):
                self.__owner.dirty = True

        super().__setitem__(attr, value)

class NotifyList(list):
    """
    A notify list is a list which can notify its owner when it has
    changed.
    """
    def __init__(self, *args, owner: Resource = None, **kwargs):
        self.__owner = owner

        if len(args) > 0:
            for i in range(len(args[0])):
                if isinstance(args[0][i], dict):
                    args[0][i] = NotifyDict(args[0][i], owner=self.__owner)
                if isinstance(args[0][i], list):
                    args[0][i] = NotifyList(args[0][i], owner=self.__owner)

        super().__init__(*args, **kwargs)

    def get_item(self, attr):
        try:
            return self.__getitem__(attr)
        except:
            return None

    def __setitem__(self, attr, value):
        if isinstance(value, dict):
            value = NotifyDict(value, owner=self.__owner)
        if isinstance(value, list):
            value = NotifyList(value, owner=self.__owner)

        if self.__getitem__(attr) != value:
            if(self.__owner != None):
                self.__owner.dirty = True
        
        super().__setitem__(attr, value)

# endregion

class Resource():
    """
    The top resource in the inheritance chain.

    Contains:
     - reference to the Pack (could be blank, if floating resource)
     - reference to the File (could be a few links up the chain)
     - dirty status
     - abstract ability to save
     - list of children resources
    """

    def __init__(self, file: FileResource = None, pack: Pack = None) -> None:
        # Public
        self.pack = pack
        self.file = file
        self._dirty = False

        # Private
        self.__resources: Resource = []

    @property
    def dirty(self):
        return self._dirty

    @dirty.setter
    def dirty(self, dirty):
        self._dirty = dirty

    def register_resource(self, resource):
        """
        Register a child resource. These resources will always be saved first.
        """
        self.__resources.append(resource)

    def _should_save(self):
        """
        Whether the asset can be saved.
        By default, this is related to dirty status
        """
        return self.dirty

    def _should_delete(self):
        return True

    def _save(self, force=False):
        """
        Internal implementation of asset saving.
        
        Should always be implemented.
        """
        raise NotImplementedError()

    def _delete(self, force=False):
        """Internal implementation for asset deletion."""
        raise NotImplementedError()


    def save(self, force=False):
        """
        Save the resource. Should not be overridden.
        """

        # Assets without packs may not save.
        if not self.pack:
            raise FloatingAssetError()

        if self._should_save() or force:
            self.dirty = False
            for resource in self.__resources:
                resource.save(force=force)

            # Internal save handling
            self._save(force=force)
            self.dirty = False

    def delete(self, force=False):
        """
        Deletes the resource. Should not be overridden.
        """

        if self._should_delete() or force:
            # First, delete all resources of children
            for resource in self.__resources:
                resource.delete(force=force)

            # Then delete self
            self._delete(force=force)

            # Then save, respecting points where files may not want to save
            # TODO: Should we force? Or call .save() directly?
            self.save(force=force)

class FileResource(Resource):
    """
    A resource, which is also a file.
    Contains:
     - File path
     - ability to mark for deletion
    """
    def __init__(self, file_path: str = None, pack: Pack = None) -> None:
        super().__init__(file=self, pack=pack)
        
        # All files must register with their pack
        self.pack.register_resource(self)
        
        # Public
        self.file_path = file_path

        if file_path:
            self.file_name = os.path.basename(file_path)

        # Protected
        self.__hash = self._create_hash()

        # Private
        self.__mark_for_deletion: bool = False

    # Deletion does not actually delete, but rather just prevents saving
    def _delete(self, force = False):
        self.__mark_for_deletion = True

    def _should_delete(self):
        return not self.__mark_for_deletion and super()._should_delete()

    def _should_save(self):
        # Files that have been deleted cannot be saved
        if self.__mark_for_deletion:
            return False

        return self.__hash != self._create_hash() or super()._should_save()

    def _create_hash(self):
        # If a file doesn't want to implement a hash, then the file will always
        # be treated as the same, allowing other checks to take control.
        return 0

class JsonResource(Resource):
    """
    Parent class, which is responsible for all resources which contain
    json data.
    Should not be used directly. Use should JsonFileResource, or JsonSubResource.
    Contains:
     - Data object
     - Method for interacting with the data
    """

    def __init__(self, data: dict = None, file: FileResource = None, pack: Pack = None) -> None:
        super().__init__(file=file, pack=pack)
        self.data = self.convert_to_notify(data)

    def convert_to_notify(self, raw_data):
        if isinstance(raw_data, dict):
            return NotifyDict(raw_data, owner=self)

        if isinstance(raw_data, list):
            return NotifyList(raw_data, owner=self)
        
        return raw_data

    # TODO: Make all these methods into using self.data.

    def __str__(self):
        return json.dumps(self.data, indent=2)

    def remove_value_at(self, json_path, data):
        try:
            keys = DOT_MATCHER_REGEX.split(json_path)
            final = keys.pop().strip("'")
            for key in keys:
                data = data[key.strip("'")]
            del data[final]
        except KeyError:
            raise AssetNotFoundError(json_path, data)
            
    def set_value_at(self, json_path, data: dict, insert_data: dict):
        try:
            keys = DOT_MATCHER_REGEX.split(json_path)
            final = keys.pop().strip("'")
            for key in keys:
                data = data[key.strip("'")]
            
            # If number, then cast
            print(final)
            if '[' in final:
                final = int(final.strip('[]'))

            data[final] = insert_data
        except KeyError:
            raise AssetNotFoundError(json_path, data)


    def get_value_at(self, json_path, data):
        try:
            keys = DOT_MATCHER_REGEX.split(json_path)
            for key in keys:
                data = data[key.strip("'")]
            
            return data
        except KeyError:
            raise AssetNotFoundError(json_path, data)

    def get_data_at(self, json_path, data):
        try:
            keys = DOT_MATCHER_REGEX.split(json_path)

            # Last key should always be be *
            if keys.pop().strip("'") != '*':
                raise AmbiguousAssetError('get_data_at used with non-ambiguous path', json_path)

            for key in keys:
                data = data.get(key.strip("'"), {})
            
            base = json_path.strip("*")

            if isinstance(data, dict):
                for key in data.keys():
                    yield base + f"'{key}'", data[key]
            elif isinstance(data, list):
                for i, element in enumerate(data):
                    yield base + f"[{i}]", element
            else:
                raise AmbiguousAssetError('get_data_at found a single element, not a list or dict.', json_path)
            

        except KeyError as key_error:
            raise AssetNotFoundError(json_path, data) from key_error

class JsonFileResource(FileResource, JsonResource):
    """
    A file, which contains json data. Most files in the addon system
    are of this type, or have it as a resource parent.
    """
    def __init__(self, data: dict = None, file_path: str = None, pack: Pack = None) -> None:
        FileResource.__init__(self, file_path=file_path, pack=pack)
        
        if data != None:
            self.data = NotifyDict(data, owner=self)
        else:
            self.data = NotifyDict(self.pack.load_json(self.file_path), owner=self)

        JsonResource.__init__(self, data=self.data, file=self, pack=pack)

    def _should_save(self):
        return not self.__mark_for_deletion and super()._should_save()

    def _save(self, force):
        self.pack.save_json(self.file_path, self.data)

    def delete(self):
        self.__mark_for_deletion = True

    def _create_hash(self):
        return make_hash(self.data)

class JsonSubResource(JsonResource):
    """
    A sub resource represents a chunk of json data, within a file.
    """
    def __init__(self, parent: Resource = None, json_path: str = None, data: dict = None) -> None:
        super().__init__(data = data, pack = parent.pack, file = parent.file)
        self.parent = parent
        self.json_path = json_path
        self.id = self.get_id_from_jsonpath(json_path)
        self.data = self.convert_to_notify(data)
        self.__resources: JsonSubResource = []
        self.parent.register_resource(self)


    def get_id_from_jsonpath(self, json_path):
        keys = DOT_MATCHER_REGEX.split(json_path)
        return keys[len(keys) - 1].replace("'", "")


    def convert_to_notify(self, raw_data):
        if isinstance(raw_data, dict):
            return NotifyDict(raw_data, owner=self)
        if isinstance(raw_data, list):
            return NotifyList(raw_data, owner=self)
        else:
            return raw_data

    @property
    def dirty(self):
        return self._dirty
    
    @dirty.setter
    def dirty(self, dirty):
        self._dirty = dirty
        self.parent.dirty = dirty

    def register_resource(self, resource: JsonSubResource) -> None:
        self.__resources.append(resource)
        
    def save(self, force=False):
        if self._dirty or force:
            for resource in self.__resources:
                resource.save(force=force)
            
            self.set_value_at(self.json_path, self.parent.data, self.data)
            self._dirty = False

    def delete(self):
        self.parent.dirty = True
        self.remove_value_at(self.json_path, self.parent.data)

@dataclass
class Translation:
    key: str
    value: str
    comment: str

class LanguageFile(FileResource):
    def __init__(self, file_path: str = None, pack: Pack = None) -> None:
        super().__init__(file_path=file_path, pack=pack)
        self.__translations: list[Translation] = []   
    
    def contains_translation(self, key: str) -> bool:
        """
        Whether the language file contains the specified key.
        """

        for translation in self.translations:
            if translation.key == key:
                return True
        return False

    def delete_translation(self, key: str) -> None:
        """
        Deletes a translation based on key, if it exists.
        """
        for translation in self.translations:
            if translation.key == key:
                self.dirty = True
                self.translations.remove(translation)
                return

    def add_translation(self, translation: Translation, overwrite: bool = True) -> bool:
        """
        Adds a new translation key. Overwrites by default.
        """

        # We must complain about duplicates, unless
        if not overwrite and self.contains_translation(translation.key):
            self.dirty = True
            self.__translations.append(translation)
            return True
        
        return False
    
    def _save(self, force=False):
        path = os.path.join(self.pack.output_path, self.file_path)
        create_nested_directory(path)
        with open(path, 'w', encoding='utf-8') as file:
            for translation in self.translations:
                file.write(f"{translation.key}={translation.value}\t##{translation.comment}\n")

    @cached_property
    def translations(self) -> list[Translation]:
        with open(os.path.join(self.pack.input_path, self.file_path), "r", encoding='utf-8') as language_file:
            for line in language_file.readlines():
                language_regex = "^([^#\n]+?)=([^#]+)#*?([^#]*?)$"
                if match := re.search(language_regex, line):
                    groups = match.groups()
                    self.__translations.append(
                        Translation(
                            key = groups[0].strip() if len(groups) > 0 else "",
                            value = groups[1].strip() if len(groups) > 1 else "",
                            comment = groups[2].strip() if len(groups) > 2 else "",
                        )
                    )
                else:
                    print("NOGO", line)
        return self.__translations


class Pack():
    def __init__(self, input_path: str, project=None):
        self.resources = []
        self.__language_files = []
        self.__project = project
        self.input_path = input_path
        self.output_path = input_path

    @cached_property
    def project(self) -> Project:
        return self.__project

    def set_output_location(self, output_path: str) -> None:
        self.output_path = output_path

    def load_json(self, local_path):
        return self.get_json_from_path(os.path.join(self.input_path, local_path))

    def save_json(self, local_path, data):
        return self.__save_json(os.path.join(self.output_path, local_path), data)

    def delete_file(self, local_path):
        try:
            send2trash(os.path.join(self.output_path, local_path))
        except:
            pass

    def save(self, force=False):
        for resource in self.resources:
            resource.save(force=force)

    def register_resource(self, resource):
        self.resources.append(resource)

    def get_language_file(self, file_name:str) -> LanguageFile:
        for language_file in self.language_files:
            if language_file.file_name == file_name:
                return language_file
        raise AssetNotFoundError(file_name)

    @cached_property
    def language_files(self) -> list[LanguageFile]:
        base_directory = os.path.join(self.input_path, "texts")
        for local_path in glob.glob(base_directory + "/**/*.lang", recursive=True):
            local_path = os.path.relpath(local_path, self.input_path)
            self.__language_files.append(LanguageFile(file_path = local_path, pack = self))
            
        return self.__language_files

    ## TODO: Move these static methods OUT
    @staticmethod
    def get_json_from_path(path:str) -> dict:
        with open(path, "r") as fh:
            return Pack.__get_json_from_file(fh)

    @staticmethod
    def __get_json_from_file(fh:TextIOWrapper) -> dict:
        try:
            return json.load(fh)
        except:
            try:
                fh.seek(0)
                contents = ""
                for line in fh.readlines():
                    cleanedLine = line.split("//", 1)[0]
                    if len(cleanedLine) > 0 and line.endswith("\n") and "\n" not in cleanedLine:
                        cleanedLine += "\n"
                    contents += cleanedLine
                while "/*" in contents:
                    preComment, postComment = contents.split("/*", 1)
                    contents = preComment + postComment.split("*/", 1)[1]
                return json.loads(contents)
            except Exception as e:
                print(e)
                return {}
    
    @staticmethod
    def __save_json(file_path, data):
        dir_name = os.path.dirname(file_path)

        if not os.path.exists(dir_name):
            os.makedirs(os.path.dirname(file_path))

        with open(file_path, "w+") as f:
            return json.dump(data, f, indent=2)

class Project():
    def __init__(self, behavior_path: str, resource_path: str):
        self.__behavior_path = behavior_path
        self.__resource_path = resource_path
        self.__resource_pack = None
        self.__behavior_pack = None

    @cached_property
    def resource_pack(self) -> ResourcePack:
        self.__resource_pack = ResourcePack(self.__resource_path, project=self)
        return self.__resource_pack

    @cached_property
    def behavior_pack(self) -> BehaviorPack:
        self.__behavior_pack = BehaviorPack(self.__behavior_path, project=self)
        return self.__behavior_pack

    def save(self, force=False):
        self.__behavior_pack.save(force=force)
        self.__resource_pack.save(force=force)

# Forward Declares
class BehaviorPack(Pack): pass
class ResourcePack(Pack): pass
class ResourcePack(Pack):
    def __init__(self, input_path: str, project: Project = None):
        super().__init__(input_path, project=project)
        self.__animation_controller_files = []
        self.__animation_files = []
        self.__entities = []
        self.__model_files = []
        self.__render_controllers = []
        self.__items = []
        
    
    @cached_property
    def animation_controller_files(self) -> list[AnimationControllerFileRP]:
        base_directory = os.path.join(self.input_path, "animation_controllers")
        for local_path in glob.glob(base_directory + "/**/*.json", recursive=True):
            local_path = os.path.relpath(local_path, self.input_path)
            self.__animation_controller_files.append(AnimationControllerFileRP(file_path = local_path, pack = self))
            
        return self.__animation_controller_files

    @cached_property
    def animation_files(self) -> list[AnimationFileRP]:
        base_directory = os.path.join(self.input_path, "animations")
        for local_path in glob.glob(base_directory + "/**/*.json", recursive=True):
            local_path = os.path.relpath(local_path, self.input_path)
            self.__animation_files.append(AnimationFileRP(file_path = local_path, pack = self))
            
        return self.__animation_files

    @cached_property
    def entities(self) -> list[EntityFileRP]:
        base_directory = os.path.join(self.input_path, "entity")
        for local_path in glob.glob(base_directory + "/**/*.json", recursive=True):
            local_path = os.path.relpath(local_path, self.input_path)
            self.__entities.append(EntityFileRP(file_path = local_path, pack = self))
            
        return self.__entities

    @cached_property
    def model_files(self) -> list[ModelFileRP]:
        base_directory = os.path.join(self.input_path, "models")
        for local_path in glob.glob(base_directory + "/**/*.json", recursive=True):
            local_path = os.path.relpath(local_path, self.input_path)
            self.__model_files.append(ModelFileRP(file_path = local_path, pack = self))
            
        return self.__model_files

    @cached_property
    def render_controllers(self) -> list[RenderControllerFileRP]:
        base_directory = os.path.join(self.input_path, "render_controllers")
        for local_path in glob.glob(base_directory + "/**/*.json", recursive=True):
            local_path = os.path.relpath(local_path, self.input_path)
            self.__render_controllers.append(RenderControllerFileRP(file_path = local_path, pack = self))
            
        return self.__render_controllers

    @cached_property
    def items(self) -> list[ItemFileRP]:
        base_directory = os.path.join(self.input_path, "items")
        for local_path in glob.glob(base_directory + "/**/*.json", recursive=True):
            local_path = os.path.relpath(local_path, self.input_path)
            self.__items.append(ItemFileRP(file_path = local_path, pack = self))
            
        return self.__items

    
    @cached_property
    def animation_controllers(self) -> list[AnimationControllerRP]:
        children = []
        for file in self.animation_controller_files:
            for child in file.animation_controllers:
                children.append(child)
        return children

    @cached_property
    def models(self) -> list[Model]:
        children = []
        for file in self.model_files:
            for child in file.models:
                children.append(child)
        return children

    
    def get_animation_controller_file(self, file_name:str) -> AnimationControllerFileRP:
        for child in self.animation_controller_files:
            if child.file_name == file_name:
                return child
        raise AssetNotFoundError(file_name)

    def get_animation_file(self, file_name:str) -> AnimationFileRP:
        for child in self.animation_files:
            if child.file_name == file_name:
                return child
        raise AssetNotFoundError(file_name)

    def get_entity(self, identifier:str) -> EntityFileRP:
        for child in self.entities:
            if child.identifier == identifier:
                return child
        raise AssetNotFoundError(identifier)

    def get_model_file(self, file_name:str) -> ModelFileRP:
        for child in self.model_files:
            if child.file_name == file_name:
                return child
        raise AssetNotFoundError(file_name)

    
    def get_animation_controller(self, id:str) -> AnimationControllerRP:
        for file_child in self.animation_controller_files:
            for child in file_child.animation_controllers:
                if child.id == id:
                    return child
        raise AssetNotFoundError(id)

    def get_model(self, identifier:str) -> Model:
        for file_child in self.model_files:
            for child in file_child.models:
                if child.identifier == identifier:
                    return child
        raise AssetNotFoundError(identifier)

    
class BehaviorPack(Pack):
    def __init__(self, input_path: str, project: Project = None):
        super().__init__(input_path, project=project)
        self.__features_file = []
        self.__feature_rules_files = []
        self.__spawn_rules = []
        self.__recipes = []
        self.__entities = []
        self.__animation_controller_files = []
        self.__loot_tables = []
        self.__items = []
        
    
    @cached_property
    def features_file(self) -> list[FeaturesFileBP]:
        base_directory = os.path.join(self.input_path, "features")
        for local_path in glob.glob(base_directory + "/**/*.json", recursive=True):
            local_path = os.path.relpath(local_path, self.input_path)
            self.__features_file.append(FeaturesFileBP(file_path = local_path, pack = self))
            
        return self.__features_file

    @cached_property
    def feature_rules_files(self) -> list[FeatureRulesFileBP]:
        base_directory = os.path.join(self.input_path, "feature_rules")
        for local_path in glob.glob(base_directory + "/**/*.json", recursive=True):
            local_path = os.path.relpath(local_path, self.input_path)
            self.__feature_rules_files.append(FeatureRulesFileBP(file_path = local_path, pack = self))
            
        return self.__feature_rules_files

    @cached_property
    def spawn_rules(self) -> list[SpawnRuleFile]:
        base_directory = os.path.join(self.input_path, "spawn_rules")
        for local_path in glob.glob(base_directory + "/**/*.json", recursive=True):
            local_path = os.path.relpath(local_path, self.input_path)
            self.__spawn_rules.append(SpawnRuleFile(file_path = local_path, pack = self))
            
        return self.__spawn_rules

    @cached_property
    def recipes(self) -> list[RecipeFile]:
        base_directory = os.path.join(self.input_path, "recipes")
        for local_path in glob.glob(base_directory + "/**/*.json", recursive=True):
            local_path = os.path.relpath(local_path, self.input_path)
            self.__recipes.append(RecipeFile(file_path = local_path, pack = self))
            
        return self.__recipes

    @cached_property
    def entities(self) -> list[EntityFileBP]:
        base_directory = os.path.join(self.input_path, "entities")
        for local_path in glob.glob(base_directory + "/**/*.json", recursive=True):
            local_path = os.path.relpath(local_path, self.input_path)
            self.__entities.append(EntityFileBP(file_path = local_path, pack = self))
            
        return self.__entities

    @cached_property
    def animation_controller_files(self) -> list[AnimationControllerFile]:
        base_directory = os.path.join(self.input_path, "animation_controllers")
        for local_path in glob.glob(base_directory + "/**/*.json", recursive=True):
            local_path = os.path.relpath(local_path, self.input_path)
            self.__animation_controller_files.append(AnimationControllerFile(file_path = local_path, pack = self))
            
        return self.__animation_controller_files

    @cached_property
    def loot_tables(self) -> list[LootTableFile]:
        base_directory = os.path.join(self.input_path, "loot_tables")
        for local_path in glob.glob(base_directory + "/**/*.json", recursive=True):
            local_path = os.path.relpath(local_path, self.input_path)
            self.__loot_tables.append(LootTableFile(file_path = local_path, pack = self))
            
        return self.__loot_tables

    @cached_property
    def items(self) -> list[ItemFileBP]:
        base_directory = os.path.join(self.input_path, "items")
        for local_path in glob.glob(base_directory + "/**/*.json", recursive=True):
            local_path = os.path.relpath(local_path, self.input_path)
            self.__items.append(ItemFileBP(file_path = local_path, pack = self))
            
        return self.__items

    
    
    def get_feature_rules_file(self, identifier:str) -> FeatureRulesFileBP:
        for child in self.feature_rules_files:
            if child.identifier == identifier:
                return child
        raise AssetNotFoundError(identifier)

    def get_spawn_rule(self, identifier:str) -> SpawnRuleFile:
        for child in self.spawn_rules:
            if child.identifier == identifier:
                return child
        raise AssetNotFoundError(identifier)

    def get_recipe(self, identifier:str) -> RecipeFile:
        for child in self.recipes:
            if child.identifier == identifier:
                return child
        raise AssetNotFoundError(identifier)

    def get_entity(self, identifier:str) -> EntityFileBP:
        for child in self.entities:
            if child.identifier == identifier:
                return child
        raise AssetNotFoundError(identifier)

    
    
class FeatureRulesFileBP(JsonFileResource):
    def __init__(self, data: dict = None, file_path: str = None, pack: Pack = None) -> None:
        super().__init__(data = data, file_path = file_path, pack = pack)
        
    
    @property
    def identifier(self):
        return self.get_value_at("minecraft:feature_rules.description.identifier", self.data)
    
    @identifier.setter
    def identifier(self, identifier):
        return self.set_value_at("minecraft:feature_rules.description.identifier", self.data, identifier)

    @property
    def format_version(self):
        return self.get_value_at("format_version", self.data)
    
    @format_version.setter
    def format_version(self, format_version):
        return self.set_value_at("format_version", self.data, format_version)

    
    
    
    
class RenderControllerFileRP(JsonFileResource):
    def __init__(self, data: dict = None, file_path: str = None, pack: Pack = None) -> None:
        super().__init__(data = data, file_path = file_path, pack = pack)
        
    
    
    
    
    
class AnimationControllerFileRP(JsonFileResource):
    def __init__(self, data: dict = None, file_path: str = None, pack: Pack = None) -> None:
        super().__init__(data = data, file_path = file_path, pack = pack)
        self.__animation_controllers = []
        
    
    
    @cached_property
    def animation_controllers(self) -> list[AnimationControllerRP]:
        for path, data in self.get_data_at("animation_controllers.*", self.data):
            self.__animation_controllers.append(AnimationControllerRP(parent = self, json_path = path, data = data))
        return self.__animation_controllers
    
    
    def get_animation_controller(self, id:str) -> AnimationControllerRP:
        for child in self.animation_controllers:
            if child.id == id:
                return child
        raise AssetNotFoundError(id)

    
    
class RecipeFile(JsonFileResource):
    def __init__(self, data: dict = None, file_path: str = None, pack: Pack = None) -> None:
        super().__init__(data = data, file_path = file_path, pack = pack)
        
    
    @property
    def identifier(self):
        return self.get_value_at("('minecraft:recipe_shaped'|'minecraft:recipe_shapeless'|'minecraft:recipe_brewing_mix'|'minecraft:recipe_furnace'|'minecraft:recipe_brewing_container').description.identifier", self.data)
    
    @identifier.setter
    def identifier(self, identifier):
        return self.set_value_at("('minecraft:recipe_shaped'|'minecraft:recipe_shapeless'|'minecraft:recipe_brewing_mix'|'minecraft:recipe_furnace'|'minecraft:recipe_brewing_container').description.identifier", self.data, identifier)

    @property
    def format_version(self):
        return self.get_value_at("format_version", self.data)
    
    @format_version.setter
    def format_version(self, format_version):
        return self.set_value_at("format_version", self.data, format_version)

    
    
    
    
class SpawnRuleFile(JsonFileResource):
    def __init__(self, data: dict = None, file_path: str = None, pack: Pack = None) -> None:
        super().__init__(data = data, file_path = file_path, pack = pack)
        
    
    @property
    def identifier(self):
        return self.get_value_at("'minecraft:spawn_rules.description'.identifier", self.data)
    
    @identifier.setter
    def identifier(self, identifier):
        return self.set_value_at("'minecraft:spawn_rules.description'.identifier", self.data, identifier)

    @property
    def format_version(self):
        return self.get_value_at("format_version", self.data)
    
    @format_version.setter
    def format_version(self, format_version):
        return self.set_value_at("format_version", self.data, format_version)

    
    
    
    
class LootTableFile(JsonFileResource):
    def __init__(self, data: dict = None, file_path: str = None, pack: Pack = None) -> None:
        super().__init__(data = data, file_path = file_path, pack = pack)
        self.__pools = []
        
    
    
    @cached_property
    def pools(self) -> list[LootTablePool]:
        for path, data in self.get_data_at("pools.*", self.data):
            self.__pools.append(LootTablePool(parent = self, json_path = path, data = data))
        return self.__pools
    
    
    
    
class ItemFileRP(JsonFileResource):
    def __init__(self, data: dict = None, file_path: str = None, pack: Pack = None) -> None:
        super().__init__(data = data, file_path = file_path, pack = pack)
        self.__components = []
        
    
    @property
    def identifier(self):
        return self.get_value_at("'minecraft:item'.description.identifier", self.data)
    
    @identifier.setter
    def identifier(self, identifier):
        return self.set_value_at("'minecraft:item'.description.identifier", self.data, identifier)

    @property
    def format_version(self):
        return self.get_value_at("format_version", self.data)
    
    @format_version.setter
    def format_version(self, format_version):
        return self.set_value_at("format_version", self.data, format_version)

    
    @cached_property
    def components(self) -> list[Component]:
        for path, data in self.get_data_at("'minecraft:item'.components.*", self.data):
            self.__components.append(Component(parent = self, json_path = path, data = data))
        return self.__components
    
    
    
    
class ItemFileBP(JsonFileResource):
    def __init__(self, data: dict = None, file_path: str = None, pack: Pack = None) -> None:
        super().__init__(data = data, file_path = file_path, pack = pack)
        self.__components = []
        
    
    @property
    def identifier(self):
        return self.get_value_at("'minecraft:item'.description.identifier", self.data)
    
    @identifier.setter
    def identifier(self, identifier):
        return self.set_value_at("'minecraft:item'.description.identifier", self.data, identifier)

    
    @cached_property
    def components(self) -> list[Component]:
        for path, data in self.get_data_at("'minecraft:item'.components", self.data):
            self.__components.append(Component(parent = self, json_path = path, data = data))
        return self.__components
    
    
    
    
class EntityFileRP(JsonFileResource):
    def __init__(self, data: dict = None, file_path: str = None, pack: Pack = None) -> None:
        super().__init__(data = data, file_path = file_path, pack = pack)
        self.__animations = []
        
    
    @property
    def identifier(self):
        return self.get_value_at("'minecraft:client_entity'.description.identifier", self.data)
    
    @identifier.setter
    def identifier(self, identifier):
        return self.set_value_at("'minecraft:client_entity'.description.identifier", self.data, identifier)

    
    @cached_property
    def animations(self) -> list[AnimationRP]:
        for path, data in self.get_data_at("'minecraft:client_entity'.description.animations.*", self.data):
            self.__animations.append(AnimationRP(parent = self, json_path = path, data = data))
        return self.__animations
    
    
    
    
class AnimationFileRP(JsonFileResource):
    def __init__(self, data: dict = None, file_path: str = None, pack: Pack = None) -> None:
        super().__init__(data = data, file_path = file_path, pack = pack)
        self.__animations = []
        
    
    @property
    def format_version(self):
        return self.get_value_at("format_version", self.data)
    
    @format_version.setter
    def format_version(self, format_version):
        return self.set_value_at("format_version", self.data, format_version)

    
    @cached_property
    def animations(self) -> list[AnimationRP]:
        for path, data in self.get_data_at("animations.*", self.data):
            self.__animations.append(AnimationRP(parent = self, json_path = path, data = data))
        return self.__animations
    
    
    
    
class EntityFileBP(JsonFileResource):
    def __init__(self, data: dict = None, file_path: str = None, pack: Pack = None) -> None:
        super().__init__(data = data, file_path = file_path, pack = pack)
        self.__component_groups = []
        self.__components = []
        self.__events = []
        
    
    @property
    def format_version(self):
        return self.get_value_at("format_version", self.data)
    
    @format_version.setter
    def format_version(self, format_version):
        return self.set_value_at("format_version", self.data, format_version)

    @property
    def identifier(self):
        return self.get_value_at("'minecraft:entity'.description.identifier", self.data)
    
    @identifier.setter
    def identifier(self, identifier):
        return self.set_value_at("'minecraft:entity'.description.identifier", self.data, identifier)

    
    @cached_property
    def component_groups(self) -> list[ComponentGroup]:
        for path, data in self.get_data_at("'minecraft:entity'.component_groups.*", self.data):
            self.__component_groups.append(ComponentGroup(parent = self, json_path = path, data = data))
        return self.__component_groups
    
    @cached_property
    def components(self) -> list[Component]:
        for path, data in self.get_data_at("'minecraft:entity'.components.*", self.data):
            self.__components.append(Component(parent = self, json_path = path, data = data))
        return self.__components
    
    @cached_property
    def events(self) -> list[Event]:
        for path, data in self.get_data_at("'minecraft:entity'.events.*", self.data):
            self.__events.append(Event(parent = self, json_path = path, data = data))
        return self.__events
    
    
    def get_component_group(self, id:str) -> ComponentGroup:
        for child in self.component_groups:
            if child.id == id:
                return child
        raise AssetNotFoundError(id)

    def get_component(self, id:str) -> Component:
        for child in self.components:
            if child.id == id:
                return child
        raise AssetNotFoundError(id)

    
    def create_component_group(self, name: str, data: dict) -> ComponentGroup:
        self.set_value_at("'minecraft:entity'.component_groups." + name, self.data, data)
        new_object = ComponentGroup(self, "'minecraft:entity'.component_groups." + name, data)
        self.__component_groups.append(new_object)
        return new_object

    def create_component(self, name: str, data: dict) -> Component:
        self.set_value_at("'minecraft:entity'.components." + name, self.data, data)
        new_object = Component(self, "'minecraft:entity'.components." + name, data)
        self.__components.append(new_object)
        return new_object

    
class ModelFileRP(JsonFileResource):
    def __init__(self, data: dict = None, file_path: str = None, pack: Pack = None) -> None:
        super().__init__(data = data, file_path = file_path, pack = pack)
        self.__models = []
        
    
    
    @cached_property
    def models(self) -> list[Model]:
        for path, data in self.get_data_at("'minecraft:geometry'.*", self.data):
            self.__models.append(Model(parent = self, json_path = path, data = data))
        return self.__models
    
    
    
    
class AnimationControllerFile(JsonFileResource):
    def __init__(self, data: dict = None, file_path: str = None, pack: Pack = None) -> None:
        super().__init__(data = data, file_path = file_path, pack = pack)
        self.__animation_controllers = []
        
    
    
    @cached_property
    def animation_controllers(self) -> list[AnimationController]:
        for path, data in self.get_data_at("animation_controllers.*", self.data):
            self.__animation_controllers.append(AnimationController(parent = self, json_path = path, data = data))
        return self.__animation_controllers
    
    
    
    
class AnimationControllerRP(JsonSubResource):
    def __init__(self, data: dict = None, parent: Resource = None, json_path: str = None ) -> None:
        super().__init__(data=data, parent=parent, json_path=json_path)
        
        
    
    
    
    
    
class LootTablePool(JsonSubResource):
    def __init__(self, data: dict = None, parent: Resource = None, json_path: str = None ) -> None:
        super().__init__(data=data, parent=parent, json_path=json_path)
        
        
    
    
    
    
    
class AnimationControllerState(JsonSubResource):
    def __init__(self, data: dict = None, parent: Resource = None, json_path: str = None ) -> None:
        super().__init__(data=data, parent=parent, json_path=json_path)
        
        
    
    
    
    
    
class Model(JsonSubResource):
    def __init__(self, data: dict = None, parent: Resource = None, json_path: str = None ) -> None:
        super().__init__(data=data, parent=parent, json_path=json_path)
        
        self.__bones = []
        
    
    @cached_property
    def bones(self) -> list[Bone]:
        for path, data in self.get_data_at("bones.*", self.data):
            self.__bones.append(Bone(parent = self, json_path = path, data = data))
        return self.__bones
    
    
    @property
    def identifier(self):
        return self.get_value_at("description.identifier", self.data)
    
    @identifier.setter
    def identifier(self, identifier):
        return self.set_value_at("description.identifier", self.data, identifier)

    
    
    
class AnimationRP(JsonSubResource):
    def __init__(self, data: dict = None, parent: Resource = None, json_path: str = None ) -> None:
        super().__init__(data=data, parent=parent, json_path=json_path)
        
        
    
    
    
    
    
class AnimationController(JsonSubResource):
    def __init__(self, data: dict = None, parent: Resource = None, json_path: str = None ) -> None:
        super().__init__(data=data, parent=parent, json_path=json_path)
        
        self.__states = []
        
    
    @cached_property
    def states(self) -> list[AnimationControllerState]:
        for path, data in self.get_data_at("states.*", self.data):
            self.__states.append(AnimationControllerState(parent = self, json_path = path, data = data))
        return self.__states
    
    
    
    
    
class ComponentGroup(JsonSubResource):
    def __init__(self, data: dict = None, parent: Resource = None, json_path: str = None ) -> None:
        super().__init__(data=data, parent=parent, json_path=json_path)
        
        self.__components = []
        
    
    @cached_property
    def components(self) -> list[Component]:
        for path, data in self.get_data_at("*", self.data):
            self.__components.append(Component(parent = self, json_path = path, data = data))
        return self.__components
    
    
    
    
    def create_component(self, name: str, data: dict) -> Component:
        self.set_value_at("." + name, self.data, data)
        new_object = Component(self, "." + name, data)
        self.__components.append(new_object)
        return new_object

    
class Component(JsonSubResource):
    def __init__(self, data: dict = None, parent: Resource = None, json_path: str = None , component_group: ComponentGroup = None) -> None:
        super().__init__(data=data, parent=parent, json_path=json_path)
        
        
    
    
    
    
    
class Event(JsonSubResource):
    def __init__(self, data: dict = None, parent: Resource = None, json_path: str = None ) -> None:
        super().__init__(data=data, parent=parent, json_path=json_path)
        
        self.__groups_to_add = []
        self.__groups_to_remove = []
        
    
    @cached_property
    def groups_to_add(self) -> list[ComponentGroup]:
        for path, data in self.get_data_at("add.component_groups.*", self.data):
            self.__groups_to_add.append(ComponentGroup(parent = self, json_path = path, data = data))
        return self.__groups_to_add
    
    @cached_property
    def groups_to_remove(self) -> list[ComponentGroup]:
        for path, data in self.get_data_at("remove.component_groups.*", self.data):
            self.__groups_to_remove.append(ComponentGroup(parent = self, json_path = path, data = data))
        return self.__groups_to_remove
    
    
    
    
    
class Bone(JsonSubResource):
    def __init__(self, data: dict = None, parent: Resource = None, json_path: str = None ) -> None:
        super().__init__(data=data, parent=parent, json_path=json_path)
        
        self.__cubes = []
        
    
    @cached_property
    def cubes(self) -> list[Cube]:
        for path, data in self.get_data_at("cubes.*", self.data):
            self.__cubes.append(Cube(parent = self, json_path = path, data = data))
        return self.__cubes
    
    
    
    
    
class Cube(JsonSubResource):
    def __init__(self, data: dict = None, parent: Resource = None, json_path: str = None ) -> None:
        super().__init__(data=data, parent=parent, json_path=json_path)
        
        
    
    
    
    
    