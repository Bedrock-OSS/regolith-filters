# Json Cleaner

This small utility filter is intended to be used as the first filter in your Regolith Project. It will go through your packs, reading and saving every json file.

This is useful since this will strip all the comments from the json, allowing future filters to read the json safely without worrying about comments.

## Using the Filter

```json
{
    "filter": "json_cleaner"
}
```

# Changelog

### 1.0.0

The initial release of the Json Cleaner filter.

### 1.1.0

Fix encoding issues in json_cleaner and handle errors better.

### 1.1.1

Fix encoding when saving file in json_cleaner.