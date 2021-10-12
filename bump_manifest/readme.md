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

This filter uses a pack located in your data folder. By default `packs/data/bump_manifest/version.json`. You may edit this file to set your packs current version, or to update the major version. 

By default this file will start at `[1, 0, 0]`, and will update by one minor version each compile: `[1, 0, 1]`

