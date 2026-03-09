# Brarchive

This filter archives eligible UTF-8 text directories into `.brarchive` format.

## Getting the Filter

Install with: `regolith install brarchive`. After that, you can place the filter into one of your profiles.

```json
{
  "filter": "brarchive",
  "settings": {
    "mode": "replace",
    "minify": true
  }
}
```

## Documentation

This filter will:

- find directories whose files are all valid UTF-8 (excluding font, materials, scripts, sounds, texts, and textures; subpacks processed as separate roots; `ui/_global_variables.json` excluded by path)
- create `.brarchive` files under `__brarchive` for each eligible directory
- set `header.pack_optimization_version` to `0.1.0` in manifest.json (root packs only; subpacks have no manifest)
- optionally remove original files (replace mode) or keep both (keep_both mode)
- optionally minify JSON content stored inside archives

## Settings

| Setting | Type    | Default   | Description                                                          |
|---------|---------|-----------|----------------------------------------------------------------------|
| `mode`  | string  | "replace" | "replace" removes originals after archiving. "keep_both" keeps both. |
| `minify`| boolean | true      | Minifies JSON content stored in .brarchive files.                    |

#### Default Settings

```json
{
  "mode": "replace",
  "minify": true
}
```

## Changelog

### 1.0.0

- Initial release.
