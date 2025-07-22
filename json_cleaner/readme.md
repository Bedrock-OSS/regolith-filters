# Json Cleaner

This small utility filter is intended to be used as the first filter in your Regolith Project. It will go through your packs, removing comments from your JSON files and allowing future filters to read the json safely without worrying about comments.

Additionally it can strip `$schema` fields, that are considered an error by Bedrock and minify JSON files.

## Using the Filter

```json
{
    "filter": "json_cleaner",
    "settings": {
        "stripSchemas": true,
        "minify": true
    }
}
```

## Settings

| Setting                       | Type                                                     | Default                                                 | Description                                                                                                                                         |
|-------------------------------|----------------------------------------------------------|---------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|
| `stripSchemas`              | `boolean`                                                | `false`                                                 | Removes `$schema` fields from root of every JSON file.                                                                                               |
| `minify`                    | `boolean`                                                | `false`                                                 | Minifies JSON files by removing unnecessary whitespace.                                                                                                   |

# Changelog

### 2.0.0

Complete rewrite to NodeJS by @ink0rr in #63
Add `stripSchemas` option to remove `$schema` fields from root objects
Add `minify` option to minify the JSON

### 1.1.1

Fix encoding when saving file in json_cleaner.

### 1.1.0

Fix encoding issues in json_cleaner and handle errors better.

### 1.0.0

The initial release of the Json Cleaner filter.