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
    "modules": ["@minecraft/server@1.0.0"],
    "outfile": "BP/scripts/main.js",
    "manifest": "BP/manifest.json",
    "buildOptions": {
      "entryPoints": ["data/gametests/src/main.ts"],
      "target": "es2020",
      "format": "esm",
      "bundle": true,
      "minify": true
    }
  }
}
```

Example of a multi-file build without bundling:

```json
{
  "filter": "gametests",
  "settings": {
    "modules": ["@minecraft/server@1.16.0"],
    "outfile": "BP/scripts/main.js",
    "outdir": "BP/scripts",
    "manifest": "BP/manifest.json",
    "buildOptions": {
      "entryPoints": ["data/gametests/src/**/*.ts"],
      "target": "es2020",
      "format": "esm",
      "bundle": false,
      "minify": false
    }
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

## Build-time evaluation (comptime)

The filter supports evaluating code while the pack is being built through the virtual `comptime` module. The callback runs in Node.js at build time, the `comptime(...)` call is replaced with its serialized result, and any imports or top-level declarations that were only used by comptime callbacks are removed from the compiled script.

```ts
import { comptime } from "comptime";
import { execSync } from "child_process";

export interface GitMeta {
  commit: string | null;
  branch: string | null;
  dirty: boolean;
}

export const GIT_META = comptime<GitMeta>(() => {
  const commit = runGit("rev-parse HEAD") || null;
  const branch = runGit("symbolic-ref --short HEAD") || null;
  const dirty = runGit("status --short") !== "";
  return { commit, branch, dirty };
});

function runGit(args: string): string {
  try {
    return execSync(`git ${args}`, { stdio: ["pipe", "pipe", "ignore"] }).toString().trim();
  } catch {
    return "";
  }
}
```

compiles to:

```js
const GIT_META = { commit: "e3a6dcce3a35f913e8c2d72892ee97eb9071aa21", branch: "main", dirty: false };
```

Notes:

- Callbacks may be async (the awaited value is inlined) and may only use imports and top-level declarations of their module — they cannot close over runtime values such as function parameters.
- Results must be serializable: primitives, plain objects, arrays, `Date`, `RegExp`, `Map` and `Set` are supported. Functions, symbols and class instances are not.
- Helpers may live in other files; modules imported by comptime callbacks may themselves use `comptime()`.
- Since callbacks run in Node.js at build time, they can use Node APIs (`child_process`, `fs`, ...). Install `@types/node` in `data/gametests` if you want typings for them.
- Anything a callback writes to stdout/stderr (including stderr forwarded from child processes) is prefixed with `[comptime <file>]` in the build output, so it is not mistaken for output of the filter itself. Output of child processes started with `stdio: "inherit"` bypasses the prefix.
- Typings for the `comptime` module ship in `data/gametests/types/comptime.d.ts`. If your project was created with an older version of this filter, copy that file from this repository and add `"types"` to the `include` array of `data/gametests/tsconfig.json`.
- The feature can be turned off with the `comptime` filter setting.

## Dropping logging calls (dropLabels)

esbuild's [dropLabels](https://esbuild.github.io/api/#drop-labels) option removes labeled statements, which is handy for stripping logging from release builds — but it only empties the function body, while every call site (including the evaluation of its arguments) stays in the compiled script.

This filter goes one step further: when a function's body consists **entirely** of statements labeled with dropped labels, the function is treated as a marker, and all calls to it are removed as well — including their arguments. Imports and declarations that only existed for those calls are also removed.

```ts
// log.ts
export function debug(...args: unknown[]) {
  LOGGING: {
    console.warn("[debug]", ...args);
  }
}
```

```ts
// main.ts
import { debug } from "./log";

debug("spawned entities:", JSON.stringify(expensiveReport()));
```

With `"buildOptions": { "dropLabels": ["LOGGING"] }` (e.g. only in your release profile), the compiled script contains neither the `debug` call nor the `expensiveReport()` evaluation, and the import of `log.ts` is removed. Without `dropLabels`, everything works normally.

Class methods are supported the same way. A logging library like [bedrock-boost](https://github.com/Bedrock-OSS/bedrock-boost), whose `Logger` methods are wrapped in `LOGGING:` labels, gets its call sites removed across all the common shapes:

```ts
import { Logger } from "@bedrock-oss/bedrock-boost";

const log = Logger.getLogger("main");           // instance in a variable
log.info("expensive:", JSON.stringify(data));    // removed, argument included

class Renderer {
  private log = Logger.getLogger("renderer");    // instance in a property
  render() {
    this.log.debug("frame");                     // removed
  }
}

Logger.getLogger("once").warn("chained");        // removed
export const log2 = Logger.getLogger("shared");  // importing modules drop log2.info(...) too
```

`Logger.getLogger(...)` itself survives — its body is only partially labeled, so it is not a marker.

Notes:

- A function or method is only treated as a marker when *every* statement of its body is labeled with a dropped label — it provably compiles to a no-op. Bodies with a mix of labeled and unlabeled statements only get the usual esbuild treatment.
- Calls in expression position are replaced with `(void 0)`, which is exactly what the emptied function would have returned.
- Argument expressions are removed together with the call, so release builds must not rely on their side effects.
- Works with named, aliased, default and namespace imports, local functions and classes, marked functions and classes shipped in `node_modules`, and logger instances shared between modules via `export const log = ...`.
- Calls inside comptime callbacks are not affected — they run at build time, where logging stays useful.
- Instance tracking is name-based within each module: a binding assigned from `new Logger(...)` or a static factory like `Logger.getLogger(...)` is assumed to stay a logger. There is no type inference — a variable reassigned to something else with an identically named method would be mismatched.
- The behavior can be turned off with the `dropLabeledCalls` filter setting while still using `dropLabels` itself.

## Automatic module dependencies (`modules: "auto"`)

Instead of maintaining the module list in two places (filter settings and `data/gametests/package.json`), set `"modules": "auto"` to derive it from the `dependencies` of `data/gametests/package.json`. The npm version is mapped to the manifest version automatically (e.g. `2.0.0-beta.1.21.90-stable` becomes `2.0.0-beta`).

`"modules": "auto-dev"` additionally includes `devDependencies`. A typical setup keeps `@minecraft/server-gametest` in `devDependencies`, uses `"auto-dev"` in the development/QA profile and `"auto"` in the release profile — test-only modules then never end up in the released manifest. If the release bundle still imports a dev-only module, the filter prints a warning, because the pack would fail to load it in game.

Engine modules (typings-only packages such as `@minecraft/server`) are added to the manifest and marked external; runtime libraries such as `@minecraft/math` and `@minecraft/vanilla-data` are recognized automatically and bundled as usual.

## Settings

| Setting                       | Type                                                     | Default                                                 | Description                                                                                                                                         |
|-------------------------------|----------------------------------------------------------|---------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|
| `buildOptions`                | [buildOptions](https://esbuild.github.io/api/#build-api) | [Default Build Options](#default-build-options)         | Specifies build options for esbuild                                                                                                                 |
| `moduleUUID`                  | string                                                   | Random UUID generated the first time the filter is ran. | The UUID to place inside the manifest module                                                                                                        |
| `modules`                     | string[] \| "auto" \| "auto-dev"                         | ["@minecraft/server@1.0.0"]                             | The scripting modules to inject as dependencies, follows the format '`<module>@<version>`'. `"auto"` derives them from the dependencies of `data/gametests/package.json`, `"auto-dev"` also includes devDependencies |
| `outfile`                     | string                                                   | "BP/scripts/main.js"                                    | The path to place the built script file at when buildOptions.bundle is enabled. This property is also used as the entry point for the script module |
| `outdir`                      | string                                                   | "BP/scripts"                                            | The path to build to when buildOptions.bundle is disabled                                                                                           |
| `moduleType`                  | string                                                   | "script"                                                | The manifest module type to inject                                                                                                                  |
| `manifest`                    | string                                                   | "BP/manifest.json"                                      | The manifest to edit                                                                                                                                |
| `debugBuild`                  | boolean                                                  | false                                                   | Enables source maps and adds launch configuration to `.vscode/launch.json` if it exists                                                             |
| `injectSourceMapping`                  | boolean                                                  | false                                                   | Injects source mapping into a compiled script file. Requires debugBuild to be enabled.                                                             |
| `disableManifestModification` | boolean                                                  | false                                                   | Disables adding dependencies and script module to the manifest.                                                                                     |
| `comptime`                    | boolean                                                  | true                                                    | Enables build-time evaluation of `comptime()` calls imported from the virtual `comptime` module.                                                    |
| `dropLabeledCalls`            | boolean                                                  | true                                                    | When a function's body consists entirely of labels removed by `buildOptions.dropLabels`, calls to it (including their arguments) are removed too.   |
| `skipDependencyCheck`         | boolean                                                  | false                                                   | Skips checking whether `data/gametests`' npm dependencies are installed. Has no effect when `modules` is `"auto"` or `"auto-dev"`, since resolving them requires the installed packages. |

#### Default Build Options

```js
{
    entryPoints: ["data/gametests/src/main.ts"],
    target: "es2020",
    format: "esm",
    bundle: true,
    minify: true
}
```

## Modifying config with a JS file

You can modify the settings of this filter by creating a file named `*.esbuild.config.js` in `data/gametests` folder. The file should export a function `config` that takes in the current settings. Other filters ran before this filter can place their config files in data/gametests folder and they will be loaded. The config files are loaded in alphabetical order, so if you want to override a setting, make sure your config file is loaded after the other filter's config file.

```js
// Example config file
module.exports = {
  config: (settings) => {
    // Modify settings here
    settings.buildOptions.entryPoints = ["data/gametests/extra_src/**/*.ts"];
  },
};
```

## Changelog
### 1.9.0
 - Added the `skipDependencyCheck` setting (default `false`), letting projects that keep no dependencies in `data/gametests/package.json` skip the `npm ls`/`npm i` check that otherwise runs on every build. Has no effect when `modules` is `"auto"` or `"auto-dev"`.
### 1.8.0
 - Added build-time evaluation via the virtual `comptime` module. `comptime(fn)` calls are evaluated in Node.js during the build and replaced with their serialized result; imports and top-level declarations used only by comptime callbacks are removed from the compiled script. See [Build-time evaluation (comptime)](#build-time-evaluation-comptime).
 - Added the `comptime` setting (default `true`) to toggle the feature.
 - Output written to stdout/stderr during comptime evaluation is prefixed with `[comptime <file>]`.
 - Calls to functions and class methods whose body consists entirely of labels removed by `buildOptions.dropLabels` are now removed as well, including their arguments and imports that only existed for them. Logger classes (e.g. bedrock-boost's `Logger`) are tracked through static factories, instance variables and properties, and instances shared between modules. See [Dropping logging calls (dropLabels)](#dropping-logging-calls-droplabels). Can be turned off with the `dropLabeledCalls` setting.
 - Added `"modules": "auto"` and `"modules": "auto-dev"`, deriving the manifest script dependencies from the dependencies (and, for `auto-dev`, devDependencies) of `data/gametests/package.json`. A warning is printed when the compiled script imports a dev-only module that was excluded from the manifest. See [Automatic module dependencies](#automatic-module-dependencies-modules-auto).
 - Fixed automatic package installation on macOS and Linux (it silently did nothing on non-Windows systems before).
 - Fixed the configuration examples in this readme, which used module names and a `moduleUUID` value that the filter rejects.
### 1.7.4
 - Add support for manifest V3
### 1.7.3
 - Automate dependency updates
### 1.7.2
 - Adjust source map when `injectSourceMapping` is enabled
### 1.7.1
 - Improved cleaning the path of the source file.
### 1.7.0
 - Added `injectSourceMapping` setting, that injects source mapping into a compiled script file. Requires debugBuild to be enabled. The default value is `false`.
 - Updated list of modules in the schema.
### 1.6.1
 - Renamed `debug_build` to `debugBuild` in the schema to match the other settings' name.
 - Added `disableManifestModification` setting, that disables adding dependencies and script module to the manifest. The default value is `false`.
### 1.6.0
 - Added `debug_build` setting, that helps with connecting the debugger to the Minecraft client. When enabled, the build will include source maps and will add a correct launch configuration to `.vscode/launch.json` if it exists. The default value is `false`.
 - Fixed generating the module UUID, when `moduleUUID` is not set in the settings.

### 1.5.3
Fixed the issue that caused the filter to fail when used in Regolith that uses the `use_project_app_data_storage` option (issue #53).

### 1.5.2

- Updated the default tsconfig to include `resolveJsonModule` set to `true`.

### 1.5.1

- Updated the example script to use the new `@minecraft/server` and `@minecraft/server-gametest` versions

### 1.5.0

- Added a way to modify settings with a JS file. The file should be named `*.esbuild.config.js` and export a function `config` that takes in the current settings. Other filters ran before this filter can place their config files in data/gametests folder and they will be loaded. The config files are loaded in alphabetical order, so if you want to override a setting, make sure your config file is loaded after the other filter's config file.
- Added a setup script, that will try to install dependencies of the script API module.

### 1.4.2

- Updated esbuild to 0.19.8

### 1.4.1

- Added missing `outdir` and `outfile` defaults

### 1.4.0

- Swapped from a hardcoded list of supported module versions to a pattern match
- Made specifying module versions in settings required
- Added glob support to `buildOptions.entryPoints`
- Added support for `outdir`, used when `buildOptions.bundle` is disabled

### 1.3.3

- Added new `@minecraft/server` and `@minecraft/server-ui` versions
- Fixed modules not being added to `buildOptions.external` if it was already specified in the filter settings

### 1.3.2

- Added new `@minecraft/server` versions

### 1.3.1

- Fixed full module string being added to the `buildOptions.external` property instead of just the module name

### 1.3.0

- `settings.modules` now takes an array of strings in the format of `<module_name>@<version>` or `<module_name>`, this change allows you to use a specific version of a script module
- A warning is now printed when using an unknown module rather than throwing an error.
- An error is thrown if you do not specify a version with an unknown module
- Updated to use new dependency format `{module_name: string, version: string}`
- Updated example script to use 1.19.60 beta script modules
- Updated the schema to include some enums for module suggestions in VSCode
- Added handling for attempting to add modules when manifest modules already exist

### 1.2.0

Update versioning introduced in 1.19.30.20 beta

### 1.1.0

- Removed the modules from data as it was causing long run times, likely due to needing to move all those files when regolith runs. The only modules kept were the mojang- typings. This change should decrease the amount of time regolith takes to run when using this filter.
- Removed eslint and such since the modules were removed, kept `.prettierrc.json` as the vscode extension works with it
- Moved building script to filter folder instead of data folder since the esbuild and json5 node_modules are no longer stored in data
- Added a check to moving extra_files as it would cause an error before if a user decided to remove the folder

Following changes are in preparation for client scripts, if they ever come out

- Added manifest setting to allow the user to specify the manifest path
- extra_files now needs a folder to specify whether to output to BP or RP, so what was previously `extra_files/test/jsonFile.json` would now need to be `extra_files/BP/test/jsonFile.json`

These changes also fix the infinite loop issue cause by the post-install script in #36 (the script no longer exists as the node modules are no longer installed in the data folder by default)

### 1.0.3

- Added `settings.moduleType` option to specify the type of module (`javascript` before 1.19 and `script` after 1.19, `javascript` by default)

### 1.0.2

- Fixed `settings.buildOptions.outfile` referencing the invalid setting `settings.out`, now references `settings.outfile` instead [#35](https://github.com/Bedrock-OSS/regolith-filters/pull/35)
- `settings.buildOptions` should now properly merge with defaults rather than entirely replacing them [#35](https://github.com/Bedrock-OSS/regolith-filters/pull/35)

### 1.0.1

- Added `outfile` setting, used to determine where the resulting build file will be located [#33](https://github.com/Bedrock-OSS/regolith-filters/pull/33)
- Added `modules` setting to choose which gametest modules to inject into the manifest dependencies, as well as which to allow during building [#33](https://github.com/Bedrock-OSS/regolith-filters/pull/33)
- customizing `buildOptions` will now overwrite each individual property, rather than overwriting `buildOptions` as a whole. This allows for use cases where a user may not want to entirely overwrite the `buildOptions` [#33](https://github.com/Bedrock-OSS/regolith-filters/pull/33)

### 1.0.0

The first release of Gametests filter.
