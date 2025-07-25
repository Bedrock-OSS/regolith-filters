// @ts-check
const fs = require("fs");
const path = require("path");
const { randomUUID } = require("crypto");
const { glob, globSync } = require("glob");
const json5 = require("json5");
const { spawnSync } = require("child_process");

const projectRoot = process.env.ROOT_DIR;

let uuidFile = "data/gametests/uuid.txt";
if (projectRoot) {
  uuidFile = path.join(projectRoot, "packs", uuidFile);
} else {
  console.error("No project root found");
  process.exit(1);
}
let defaultUUID = /** @type {string} */ (randomUUID());
if (fs.existsSync(uuidFile)) {
  defaultUUID = fs.readFileSync(uuidFile).toString();
} else {
  fs.writeFileSync(uuidFile, defaultUUID);
}

const defLaunchConfig = {
  mode: "listen",
  port: 19144,
};

const launchConfigConsts = {
  type: "minecraft-js",
  request: "attach",
  sourceMapRoot: "${workspaceFolder}/.regolith/tmp/BP/scripts/",
  generatedSourceRoot: "${workspaceFolder}/.regolith/tmp/BP/scripts/",
  localRoot: "${workspaceFolder}/packs/data/gametests/src/",
  name: "(gametests) Debug with Minecraft",
};

const defSettings = {
  buildOptions: {
    external: [""], // Empty string to mark as string[]
    entryPoints: ["data/gametests/src/main.ts"],
    target: "es2020",
    format: "esm",
    bundle: true,
    minify: true,
  },
  moduleUUID: defaultUUID,
  modules: ["@minecraft/server@1.0.0"],
  moduleType: "script",
  language: "javascript",
  manifest: "BP/manifest.json",
  outfile: "BP/scripts/main.js",
  outdir: "BP/scripts",
  debugBuild: false,
  injectSourceMapping: false,
  disableManifestModification: false,
};
// Reset external property so that it does not cause issues
defSettings.buildOptions.external = [];

/** @type {typeof defSettings} */
const argParsed = process.argv[2] ? JSON.parse(process.argv[2]) : {};
const settings = Object.assign({}, defSettings, argParsed);
settings.buildOptions = Object.assign({}, defSettings.buildOptions, settings.buildOptions);

// find all `*.esbuild.config.js` files in the project
const configFiles = globSync("**/*.esbuild.config.js", {
  ignore: ["**/node_modules/**"],
  cwd: 'data/gametests',
});

for (const configFile of configFiles) {
  const configPath = path.join(process.cwd(), 'data', 'gametests', configFile);
  console.log(`Loading config file ${configFile}`);
  const config = require(configPath).config;
  if (!config) {
    console.warn(`No config function exported found for ${configFile}`);
    continue;
  }
  config(settings);
}

if (settings.debugBuild) {
  settings.buildOptions.sourcemap = true;
  // It is generated in the `.regolith/tmp/BP/scripts` directory, so we need to exit to the project root and back to the actual source
  settings.buildOptions.sourceRoot = "../../../../packs/data/gametests";
  if (projectRoot && fs.existsSync(path.join(projectRoot, ".vscode", "launch.json"))) {
    const configPath = path.join(projectRoot, ".vscode", "launch.json");
    const config = json5.parse(fs.readFileSync(configPath, "utf8"));
    if (config && config.configurations) {
      let found = false;
      for (const c of config.configurations) {
        if (c.name === "(gametests) Debug with Minecraft") {
          let changed = ensureLaunchConfiguration(c);
          if (changed) {
            fs.writeFileSync(configPath, JSON.stringify(config, null, 4));
          }
          found = true;
          break;
        }
      }
      if (!found) {
        const newConfig = Object.assign({}, launchConfigConsts, defLaunchConfig);
        ensureLaunchConfiguration(newConfig);
        config.configurations.push(newConfig);
        fs.writeFileSync(configPath, JSON.stringify(config, null, 4));
      }
    }
  }
}

function ensureLaunchConfiguration(config) {
  let changed = false;
  for (const k in launchConfigConsts) {
    if (config[k] !== launchConfigConsts[k]) {
      config[k] = launchConfigConsts[k];
      changed = true;
    }
  }
  if (settings.moduleUUID) {
    if (config.targetModuleUuid !== settings.moduleUUID) {
      config.targetModuleUuid = settings.moduleUUID;
      changed = true;
    }
  } else if (config.targetModuleUuid) {
    delete config.targetModuleUuid;
    changed = true;
  }

  return changed;
}

function entryPathify(str) {
  return str.split("/").slice(1).join("/");
}
const bundle = settings.buildOptions.bundle;
let entry = "";
const out = settings.outfile ?? "BP/scripts/main.js"
settings.buildOptions.outfile = out;
entry = entryPathify(out);
if (!bundle) {
  entry = entryPathify(out);
  delete settings.buildOptions.outfile;
  settings.buildOptions.outdir = settings.outdir ?? "BP/scripts";
}

const external = bundle ? settings.buildOptions.external : [];

// Ensure types for settings
const typeMap = {
  buildOptions: "object",
  moduleUUID: "string",
  modules: "array",
  outfile: "string",
  outdir: "string",
  moduleType: "string",
  language: "string",
  manifest: "string",
};
const throwTypeError = (k) => {
  throw new TypeError(`${k}: ${JSON.stringify(settings[k])} is not an ${typeMap[k]}`);
};
for (let k in typeMap) {
  if (typeMap[k] === "array") {
    if (!Array.isArray(settings[k])) throwTypeError(k);
  } else if (typeMap[k] === "object") {
    if (typeof settings[k] !== "object" || Array.isArray(settings[k])) throwTypeError(k);
  } else if (typeof settings[k] !== typeMap[k]) throwTypeError(k);
}

// Add script module dependencies to manifest
const parsedModules = [];
for (let module of settings.modules) {
  const match = module.match(/(@[^@]+)@(.+)/);
  if (!match) {
    throw "Invalid module provided in settings, please follow the format '<module>@<version>' or '<module>'";
  }
  const name = match[1];
  let version = match[2];

  if (!version) throw `No version provided for module '${name}'`;
  const versionMatch = version.match(/\d+\.\d+\.\d+(?:-beta)?/);
  if (!versionMatch || versionMatch[0] !== version) {
    throw `Version '${version}' is not a valid module version`;
  }
  external.push(name);
  parsedModules.push({ name, version });
}

if (!settings.disableManifestModification) {
  console.log("Modifying manifest.json");
  const manifestStr = fs.readFileSync("BP/manifest.json", "utf8");
  /** @type {{
    format_version: number; 
    header: {
      name: string;
      description: string;
      uuid: string;
      version: [number, number, number];
      min_engine_version: [number, number, number];
    };
    modules: {
      description?: string; 
      type: string; 
      language?: string; 
      entry?: string; 
      uuid: string; 
      version: string | [number, number, number];
    }[]; 
    dependencies: ({module_name: string; version: string} | {uuid: string; version: [number, number, number]})[];
  }} */
  const manifest = JSON.parse(manifestStr);

  // Ensure manifest contains dependencies array
  if (!manifest.dependencies) manifest.dependencies = [];

  // Add script module dependencies to manifest
  for (let module of parsedModules) {
    const name = module.name;
    let version = module.version;

    let exists = false;
    if (
      manifest.dependencies.findIndex((v) => {
        if (typeof v.version !== "string") return;
        //@ts-ignore
        if (v.module_name !== name) return;
        exists = true;
        return v.version !== version;
      }) !== -1
    ) {
      throw `Module '${name}' already exists in manifest with a different version`;
    }

    if (!exists) {
      manifest.dependencies.push({
        module_name: name,
        version: version,
      });
    } else {
      console.warn(`Module ${name} already exists in the manifest and will not be added again`);
    }
  }

  // Ensure manifest contains a modules array
  if (!manifest.modules) manifest.modules = [];

  // Add script module to manifest
  let hasModule = false;
  if (
    manifest.modules.findIndex((v) => {
      if (v.type !== settings.moduleType) return;
      hasModule = true;
      if (v.uuid !== settings.moduleUUID) return true;
      if (v.entry !== entry) return true;
    }) !== -1
  ) {
    throw `Existing manifest module of type ${settings.moduleType} found with different properties`;
  }

  if (!hasModule) {
    manifest.modules.push({
      description: "Scripting module",
      type: settings.moduleType,
      uuid: settings.moduleUUID,
      language: settings.language,
      version: manifest.format_version === 3 ? "0.0.1" : [0, 0, 1],
      entry,
    });
  } else {
    console.warn(`Existing manifest module found with matching properties and will not be added again`);
  }

  console.log("Saving manifest.json");
  fs.writeFileSync(settings.manifest, JSON.stringify(manifest, null, 4));
}

// After the build, generate a mapping JSON file
const { SourceMapConsumer, SourceMapGenerator } = require("source-map");

/**
 * This function reads the sourcemap file generated by esbuild (assumed to be at
 * `<outfile>.map`), decodes its mappings, and writes out a JSON file (named
 * `sourceMapping.json` in the same directory) where each generated line maps to an
 * array of original source positions.
 */
async function generateSourceMapping() {
  const outPath = path.resolve(settings.outfile ?? "BP/scripts/main.js");
  const sourcemapPath = outPath + ".map"; // e.g. /absolute/path/to/BP/scripts/main.js.map

  if (!fs.existsSync(sourcemapPath)) {
    console.warn("Sourcemap file not found: " + sourcemapPath);
    return;
  }

  const sourcemapContent = fs.readFileSync(sourcemapPath, "utf8");

  await SourceMapConsumer.with(sourcemapContent, null, consumer => {
    // Create an object mapping each generated line to a single mapping object
    // containing just the source file and the original line.
    const mapping = {};

    consumer.eachMapping(mappingEntry => {
      // Only process mappings with an original source.
      if (!mappingEntry.source) return;

      // Remove the unwanted prefix from the source path.
      let source = mappingEntry.source;
      // Get index of '/data/gametests/' and slice the string from the end of it.
      const prefix = "/data/gametests/";
      if (source.indexOf(prefix) !== -1) {
        source = source.slice(source.indexOf(prefix) + prefix.length);
      }

      // For each generated line, record only the first mapping encountered.
      const genLine = mappingEntry.generatedLine;
      if (mapping[genLine] === undefined) {
        mapping[genLine] = {
          source: source,
          originalLine: mappingEntry.originalLine
        };
      }
    });
    mapping.metadata = {
      filePath: (settings.outfile ?? "BP/scripts/main.js").substring('BP/scripts/'.length),
      offset: 1
    }
    // Inject the source mapping file into the generated JS file
    const fileContents =
      "var globalSourceMapping = " + JSON.stringify(mapping) + ";\n" + fs.readFileSync(outPath);
    fs.writeFileSync(outPath, fileContents);
    console.log("Injected source mapping file to " + outPath);
  });
}
/**
 * Adjusts the sourcemap file so that all generated line numbers are offset by `lineOffset`.
 *
 * @param {string} mapPath - The path to the sourcemap file (e.g. 'BP/scripts/main.js.map').
 * @param {number} lineOffset - The number of lines to offset the generated mappings.
 */
async function adjustSourceMap(mapPath, lineOffset) {
  // Read the original sourcemap content.
  const mapContent = fs.readFileSync(mapPath, 'utf8');
  
  // Create a consumer for the original sourcemap.
  await SourceMapConsumer.with(mapContent, null, consumer => {
    // Create a new generator for the updated sourcemap.
    const generator = new SourceMapGenerator({ file: consumer.file });

    // Iterate over each mapping in the original sourcemap.
    consumer.eachMapping(mapping => {
      // Add the mapping to the new generator with an offset on the generated line.
      generator.addMapping({
        generated: {
          line: mapping.generatedLine + lineOffset,
          column: mapping.generatedColumn,
        },
        original: mapping.originalLine != null ? {
          line: mapping.originalLine,
          column: mapping.originalColumn,
        } : null,
        source: mapping.source,
        name: mapping.name,
      });
    });

    // Copy over any source content if available.
    consumer.sources.forEach(source => {
      const content = consumer.sourceContentFor(source);
      if (content) {
        generator.setSourceContent(source, content);
      }
    });

    // Convert the generator back to a sourcemap string.
    const newMap = generator.toString();
    fs.writeFileSync(mapPath, newMap, 'utf8');
    console.log(`Source map adjusted by an offset of ${lineOffset} and written to ${mapPath}`);
  });
}

function runInShell(cmd, cwd, showStdio) {
  return spawnSync("cmd", ["/c", cmd], {
    cwd: cwd,
    stdio: showStdio ? 'inherit' : undefined
  })
}

// Check if packages need to be installed
const result = runInShell("npm ls --production --depth=0 --silent", path.join(process.cwd(), "data", "gametests"), false);
if (result.status === 1) {
  console.log("Installing packages...");
  runInShell("npm i", path.join(process.cwd(), "data", "gametests"), true);
  runInShell("npm i", path.join(projectRoot, "packs", "data", "gametests"), true);
}

glob(settings.buildOptions.entryPoints).then(async (paths) => {
  settings.buildOptions.entryPoints = paths;
  require("./moveFiles.js");
  await require("./build.js").run(settings);

  // If debugBuild and injectSourceMapping is enabled, inject additional mapping data
  if (settings.debugBuild && settings.injectSourceMapping) {
    await generateSourceMapping();
    await adjustSourceMap(settings.outfile + ".map", 1);
  }
});
