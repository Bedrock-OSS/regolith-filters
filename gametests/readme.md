# Gametests

This filter is for injecting into a pack a gametest module and code mainly for actual map testing. 

The advantage of using this specific filter is that without running this filter, no gametest content will be in the final pack (for example, dev and QA profile might include gametests and package profile might not).

## Getting the Filter

Install with: `regolith install gametests`. After that, you can place the filter into one of your profiles.

```json
{
    "filter": "gametests",
    // Following settings are set by default
    "settings": {
        "moduleUUID": null,
        "buildOptions": {
            "external": ["mojang-minecraft", "mojang-minecraft-ui", "mojang-gametest"],
            "entryPoints": ["data/gametests/src/index.ts"],
            "outfile": "BP/scripts/index.js",
            "target": "es2020",
            "format": "esm",
            "bundle": true,
            "minify": true,
        },
    }
}
```

## Documentation

This filter will:
 - build the project into a single JS file using esbuild
 - copy compiled code to behavior pack
 - copy all files from `extra_files` folder into behavior pack (useful for test structures)
 - inject gametest module and required dependencies into behavior pack manifest

The filter also has included support for importing JSON files using JSON5 parser.

## Settings

| Setting        | Type                                                     | Default                                                | Description                                                         |
| -------------- | -------------------------------------------------------- | ------------------------------------------------------ | ------------------------------------------------------------------- |
| `buildOptions` | [buildOptions](https://esbuild.github.io/api/#build-api) | [defBuildOpts](#default-build-options)                 | Specifies build options for esbuild                                 |
| `moduleUUID`   | string                                                   | A randomly generated UUID each time the filter is ran. | Removes all files matching the glob path after building             |

#### Default Build Options

```js
{
    external: ["mojang-minecraft", "mojang-minecraft-ui", "mojang-gametest"],
    entryPoints: ["src/main.ts"],
    outfile: "../../BP/scripts/main.js",
    target: "es2020",
    format: "esm",
    bundle: true,
    minify: true
}
```

## Changelog

### 1.0.0

The first release of Gametests filter.
