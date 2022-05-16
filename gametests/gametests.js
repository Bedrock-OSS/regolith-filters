const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const { randomUUID } = require("crypto");

const DIRECTORY = "data/gametests/";

const defSettings = {
  removeGlob: "",
  ignoreGlob: [],
  moduleUUID: randomUUID(),
  buildOptions: {
    external: ["mojang-minecraft", "mojang-minecraft-ui", "mojang-gametest"],
    entryPoints: ["src/index.ts"],
    outfile: "../../BP/scripts/index.js",
    target: "es2020",
    format: "esm",
    bundle: true,
    minify: true,
  },
};
const settings = Object.assign(
  defSettings,
  process.argv[2] ? JSON.parse(process.argv[2]) : {}
);

const typeMap = {
  removeGlob: "string",
  ignoreGlob: "array",
  buildOptions: "object",
  moduleUUID: "string",
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

/**
 * Source: https://stackoverflow.com/a/22185855/6459649
 * Look ma, it's cp -R.
 * @param {string} src  The path to the thing to copy.
 * @param {string} dest The path to the new copy.
 */
var copyRecursiveSync = function (src, dest) {
  var exists = fs.existsSync(src);
  var stats = exists && fs.statSync(src);
  var isDirectory = exists && stats.isDirectory();
  if (isDirectory) {
    if (!fs.existsSync(dest)) {
      fs.mkdirSync(dest);
    }
    fs.readdirSync(src).forEach(function (childItemName) {
      copyRecursiveSync(
        path.join(src, childItemName),
        path.join(dest, childItemName)
      );
    });
  } else {
    fs.copyFileSync(src, dest);
  }
};

console.log("Building npm package");
let package = fs.readFileSync(DIRECTORY + "package.json", "utf8");
package = JSON.parse(package);
if (!package.scripts.build) {
  console.log('Could not find "build" script inside package.json');
  process.exit(1);
}
try {
  execSync("npm run build", { stdio: "inherit", cwd: DIRECTORY, env: {...process.env, settings: JSON.stringify(settings)} });
} catch (e) {
  console.log("Failed to run build", e);
  process.exit(1);
}

console.log("Copying extra files");
copyRecursiveSync(DIRECTORY + "extra_files", "BP");

console.log("Modifying manifest.json");
let manifest = fs.readFileSync("BP/manifest.json", "utf8");
manifest = JSON.parse(manifest);

// Required dependencies
if (!manifest.dependencies) {
  manifest.dependencies = [];
}
manifest.dependencies.push({
  "uuid": "b26a4d4c-afdf-4690-88f8-931846312678",
  "version": [0, 1, 0]
})
manifest.dependencies.push({
  "uuid": "6f4b6893-1bb6-42fd-b458-7fa3d0c89616",
  "version": [0, 1, 0]
})

// GameTests module
if (!manifest.modules) {
  manifest.modules = [];
}
manifest.modules.push(
{
  "description": "GameTests module",
  "type": "javascript",
  "uuid": settings.moduleUUID,
  "version": [0, 0, 1],
  "entry": "scripts/main.js"
});

console.log("Saving manifest.json");
fs.writeFileSync("BP/manifest.json", JSON.stringify(manifest, null, 4));