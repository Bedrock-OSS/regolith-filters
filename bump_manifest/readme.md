# bump_manifest

This filter bumps the minor version of your `manifest.json` file, every time Regolith runs. It sets all format versions to the same version, including:
 - header version (main version)
 - module versions
 - dependency versions

## Why

This filter is useful for multiplayer scenarios, such as realms or multiplayer testing. The manifest version update will force the resource pack to be re-downloaded.

## Using the Filter

Simply add to your filter list, like this:

```json
{
    "filter": "bump_manifest"
}
```

## version.json

This filter uses a file located in your data folder to track current version. By default the file will be located at `packs/data/bump_manifest/version.json`, and will start at `[1, 0, 0]`.

You may edit this file by hand to set your packs current version, for example if you need to update the major version, or to reset the minor version.

Every time the filter runs, the version will update (e.g, `[1, 0, 1`]), and the version will be copied into the manifest file.
