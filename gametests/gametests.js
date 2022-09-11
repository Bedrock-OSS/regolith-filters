const fs = require("fs");
const { randomUUID } = require("crypto");

const defSettings = {
  moduleUUID: randomUUID(),
  modules: ["mojang-gametest", "mojang-minecraft"],
  outfile: "BP/scripts/main.js",
  moduleType: "script",
  manifest: "BP/manifest.json",
  buildOptions: {
    entryPoints: ["data/gametests/src/main.ts"],
    external: [],
    target: "es2020",
    format: "esm",
    bundle: true,
    minify: true,
  },
};
const settings = Object.assign(
  {},
  defSettings,
  process.argv[2] ? JSON.parse(process.argv[2]) : {}
);
settings.buildOptions = Object.assign(
  {},
  defSettings.buildOptions,
  settings.buildOptions
);
settings.buildOptions.outfile = settings.outfile;
settings.buildOptions.external.push(...settings.modules);

const typeMap = {
  buildOptions: "object",
  moduleUUID: "string",
  modules: "array",
  outfile: "string",
  moduleType: "string",
  manifest: "string",
};
const throwTypeError = (k) => {
  throw new TypeError(
    `${k}: ${JSON.stringify(settings[k])} is not an ${typeMap[k]}`
  );
};
for (let k in typeMap) {
  if (typeMap[k] === "array") {
    if (!Array.isArray(settings[k])) throwTypeError(k);
  } else if (typeMap[k] === "object") {
    if (typeof settings[k] !== "object" || Array.isArray(settings[k]))
      throwTypeError(k);
  } else if (typeof settings[k] !== typeMap[k]) throwTypeError(k);
}

console.log("Modifying manifest.json");
let manifest = fs.readFileSync("BP/manifest.json", "utf8");
manifest = JSON.parse(manifest);

// Required dependencies
if (!manifest.dependencies) {
  manifest.dependencies = [];
}
const MODULEINFO = {
  "mojang-gametest": {
    description: "mojang-gametest",
    uuid: "6f4b6893-1bb6-42fd-b458-7fa3d0c89616",
    version: "1.0.0-beta",
  },
  "mojang-minecraft": {
    description: "mojang-minecraft",
    uuid: "b26a4d4c-afdf-4690-88f8-931846312678",
    version: "1.0.0-beta",
  },
  "mojang-minecraft-ui": {
    description: "mojang-minecraft-ui",
    uuid: "2bd50a27-ab5f-4f40-a596-3641627c635e",
    version: "1.0.0-beta",
  },
  "mojang-net": {
    description: "mojang-net",
    uuid: "777b1798-13a6-401c-9cba-0cf17e31a81b",
    version: "1.0.0-beta",
  },
  "mojang-minecraft-server-admin": {
    description: "mojang-minecraft-server-admin",
    uuid: "53d7f2bf-bf9c-49c4-ad1f-7c803d947920",
    version: "1.0.0-beta",
  },
};
for (let module of settings.modules) {
  if (!Object.keys(MODULEINFO).includes(module)) {
    console.log(`Unknown gametest module provided "${module}"`);
    process.exit(1);
  }
  manifest.dependencies.push(MODULEINFO[module]);
}

// GameTests module
if (!manifest.modules) {
  manifest.modules = [];
}
const entry = settings.outfile.split("/").slice(1).join("/");
manifest.modules.push({
  description: "Scripting module",
  type: settings.moduleType,
  uuid: settings.moduleUUID,
  version: [0, 0, 1],
  entry,
});

console.log("Saving manifest.json");
fs.writeFileSync(settings.manifest, JSON.stringify(manifest, null, 4));

require("./moveFiles.js");
require("./build.js").run(settings);
