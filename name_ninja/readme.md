# Name Ninja

This filter is used to automatically generate entity, block, spawn egg, and item names, based on a custom 'name' field, or on the entities identifier.

Simply add a `name` field into the description of a file:

```jsonc
{
  "format_version": "1.17.0",
  "minecraft:entity": {
    "description": {
      "identifier": "sirlich:frog",
      "name": "🐸 South American Horned Toad",
      "is_spawnable": true,
      "is_summonable": true,
      "is_experimental": false,
    },
    // rest of file
}
```

This will add a translation line such as: `entity.sirlich:frog.name=🐸 South American Horned Toad   ## Generated via Regolith` to your language file of choice.

## Using this Filter

1) Install 'Python'. We have prepared [installation instructions](https://bedrock-oss.github.io/regolith/guide/python-filters).
2) Install `name_ninja` by using `regolith install name_ninja` from within a regolith project directory.
3) Add the `name_ninja` filter to a [profile of your choice.](https://bedrock-oss.github.io/regolith/guide/getting-started#adding-your-first-filter)

## Example Project

An example project for this filter is contained within the `tests` folder of this repository. It shows different possible ways to name your assets:
 - Directly inside of the language files is always allowed
 - By submitting a "name" field into any BP description
 - By turning on 'auto_name', and allowing Regolith to generate the names fully from scratch

## Configuration

Here is a filter, with all options fully defined. These options will be explained bellow.

```json
{
	"filter": "name_ninja",
	"settings": {
		"language": "en_GB.lang",
		"overwrite": true,
		"sort": true,
		"ignored_identifiers": ["minecraft"],
		"entities": {
			"auto_name": true,
			"prefix": "§1",
			"postfix": "§r"
		},
		"blocks": {
			"auto_name": true,
			"prefix": "§2",
			"postfix": "§r"
		},
		"items": {
			"auto_name": true,
			"prefix": "§3",
			"postfix": "§r"
		},
		"spawn_eggs": {
			"auto_name": true,
			"prefix": "§4",
			"postfix": " Spawn Egg§r"
		}
	}
}
```

| Property  | Default    | Description                                                                                         |
|-----------|------------|-----------------------------------------------------------------------------------------------------|
| language  | en_US.lang | The language file where you want to place the translations.                                         |
| overwrite | False      | Whether languages codes should overwrite/replace translations already defined in the language file. |
| sort      | False      | Whether to sort the language file, on export. Useful for grouping assets.                           |
| ignored_namespaces | ['minecraft'] | A list of namespaces which you would like to ignore. |

As you can see, the settings for `entities`, `blocks`,  `items` and `spawn_eggs` are always the same. The approach simply gives you more flexibility per asset-type.

| Property  | Default | Description                                                                                                                                 |
|-----------|---------|---------------------------------------------------------------------------------------------------------------------------------------------|
| auto_name | False   | Whether to give assets without a 'name' property an auto-generated name. For example `sirlich:woolly_mammoth` would become "Woolly Mammoth" |
| prefix    | ""      | A prefix that is appended to the start of the translation. Useful for giving color codes to your names.                                     |
| postfix   | ""      | A postfix that is appended to the end of the translation. Useful for resetting color codes from your names.                                 |

# Changelog

### 1.0.0

The first release of Name Ninja

### 1.1.0

 - Restructured code to use `reticulator` as a proper library dependency
 - Fix name field for `1.10` format items
 - Add `ignored_namespaces` option, which defaults to ['minecraft']
 - Now prints a warning, and gracefully handles assets without identifiers

### 1.2.0

 - Updated 'reticulator' to 0.0.17-beta
 - Corrected a few bugs in the name ninja code especially regarding when using the name key

### 1.2.1

 - Updated 'reticulator' to 0.0.18-beta
 - Fixed associated issue with translations 'stacking' in the export, rather than replacing. 

### 1.2.2

 - Updated 'reticulator' to 0.1.3-beta
 - Updated 'dpath' to 2.1.2
 - Fixed issue of duplicated keys in lang file while using 'overwrite'.

### 1.2.3

 - Fixed issue where it wouldn't create a the lang file if missing
 - Fixed issue where it would fail if an identifier did not exist
