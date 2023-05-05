# JSON Convert

This filter tries to convert all JSON files in your addon from [JSON5](https://json5.org/) or [Hjson](https://hjson.github.io/) to standard JSON. 

## Getting the Filter

Install with: `regolith install json_convert`. After that, you can place the filter into one of your profiles.

```json
{
    "filter": "json_convert"
}
```

## Documentation


By default, any file with extensions `.json5`, `.hjson` and `.json` will be converted. You can change this by adding a `include` array to the filter settings. The array should contain a list of glob patterns that will be used to match files. For example, to only convert `.json5` files, you can use the following settings:

```json
{
    "filter": "json_convert",
    "settings": {
        "include": ["**/*.json5"]
    }
}
```

By default, all files are pretty-printed. You can disable this by setting `pretty` to `false` in the filter settings.

```json
{
    "filter": "json_convert",
    "settings": {
        "pretty": false
    }
}
```

To change extension of converted files, use `extension_map` setting. For example, to convert all `.json5` files to `.json` files, you can use the following settings:

```json
{
    "filter": "json_convert",
    "settings": {
        "extension_map": {
            "json5": "json"
        }
    }
}
```

By default all `json5` and `hjson` extenstions are converted to `json` extension and all other files keep their original extension.


## Changelog

### 1.0.0

The first release of JSON Convert.
