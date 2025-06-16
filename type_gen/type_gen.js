const fs = require("fs");
const path = require("path");

const settings = {
  outputFile: "Files.d.ts",
  trimCommonPrefix: false,
};

if (process.argv[2]) {
  const parsedSettings = JSON.parse(process.argv[2]);
  Object.assign(settings, parsedSettings);
}

if (!settings.outputFile) {
  console.warn(
    "No output file specified. Please specify an output file in the settings."
  );
  return;
}

// Initial configuration for running script from the project root directory
let packsPath = "./packs/";
let gametestsPath = "./packs/data/gametests/";
// If the script is run as a regolith filter
if (
  process.env.ROOT_DIR &&
  fs.existsSync(process.env.ROOT_DIR + "/config.json")
) {
  let config = JSON.parse(
    fs.readFileSync(process.env.ROOT_DIR + "/config.json", "utf8")
  );
  packsPath = "./";
  gametestsPath = path.normalize(
    process.env.ROOT_DIR + "/" + config.regolith.dataPath + "/gametests/"
  );
}

if (!fs.existsSync(gametestsPath)) {
  console.warn(
    "Could not find gametests directory. Please make sure the gametests directory is present in the dataPath"
  );
  return;
}

// Helper function to convert a string to Title Case and remove the namespace
function toTitleCase(str) {
  const split = str.split(":");
  let result = split[0];
  if (split.length > 1) {
    result = split[1];
  }
  return result // Remove namespace
    .replace(/[-_\./]/g, " ") // Replace dashes, dots and underscores with spaces
    .replace(
      /\w\S*/g,
      (txt) => txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase()
    ) // Convert to Title Case
    .replace(/\s+/g, ""); // Remove spaces
}

// Helper function to get value from an object by path
function getValueByPath(obj, path) {
  return path.split("/").reduce((prev, curr) => prev[curr], obj);
}

// Helper function to create enum declaration
function createEnumDeclaration(enumName, keyValuePairs) {
  if (Object.keys(keyValuePairs).length === 0) {
    return "";
  }
  let enumContent = `export const enum ${enumName} {\r\n`;
  let sortedEntries = Object.entries(keyValuePairs).sort(([keyA], [keyB]) =>
    keyA.localeCompare(keyB)
  );

  if (settings.trimCommonPrefix && sortedEntries.length) {
    // Start with the first key as the candidate prefix
    let commonPrefix = sortedEntries[0][0];

    // Narrow the prefix until it matches every key
    for (const [key] of sortedEntries) {
      // While the key doesn’t start with the current prefix, shorten the prefix
      while (!key.startsWith(commonPrefix) && commonPrefix) {
        commonPrefix = commonPrefix.slice(0, -1);
      }
      if (!commonPrefix) break; // no common prefix left
    }

    // Trim the prefix from each key
    if (commonPrefix) {
      sortedEntries = sortedEntries.map(([key, value]) => [
        key.slice(commonPrefix.length),
        value,
      ]);
    }
  }
  for (const [key, value] of sortedEntries) {
    enumContent += `    ${key} = "${value}",\r\n`;
  }
  enumContent += `}\r\n\r\n`;

  return enumContent;
}

// Helper function to load JSON file
function loadJsonFile(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

// Helper function to load a lang file
function loadLangFile(filePath) {
  const lines = fs.readFileSync(filePath, "utf8").split("\n");
  const syncedLines = [];
  let isSyncing = false;
  for (const line of lines) {
    if (line.startsWith("## #sync")) {
      isSyncing = true;
    } else if (line.startsWith("## #endsync")) {
      isSyncing = false;
    } else if (
      isSyncing &&
      line.trim().length > 0 &&
      line.trim().charAt(0) !== "#"
    ) {
      syncedLines.push(line);
    }
  }
  return syncedLines.map((x) =>
    x
      .trim()
      .split("=", 2)
      .map((y) => y.trim())
  );
}

function readdirSyncRecursive(dir) {
  let files = [];
  let foldersToProcess = [dir];
  while (foldersToProcess.length > 0) {
    const folder = foldersToProcess.shift();
    const folderFiles = fs.readdirSync(folder);
    for (const file of folderFiles) {
      const filePath = path.join(folder, file);
      if (fs.statSync(filePath).isDirectory()) {
        foldersToProcess.push(filePath);
      } else {
        files.push(filePath);
      }
    }
  }
  return files;
}

// Recursive function to get all JSON files from a directory
function getJsonFiles(dir) {
  let jsonFiles = [];
  if (!fs.existsSync(dir)) {
    return jsonFiles;
  }
  const files = fs.readdirSync(dir);

  files.forEach((file) => {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);

    if (stat.isDirectory()) {
      jsonFiles = jsonFiles.concat(getJsonFiles(filePath));
    } else if (path.extname(file) === ".json") {
      jsonFiles.push(filePath);
    }
  });

  return jsonFiles;
}

// Function to create the enum from JSON files
function createEnumFromJsonFiles(enumName, valueGetter, directory) {
  const jsonFiles = getJsonFiles(directory);
  const enumEntries = {};

  jsonFiles.forEach((file) => {
    const data = loadJsonFile(file);
    const identifierPath = valueGetter(data);

    if (identifierPath) {
      const enumKey = toTitleCase(identifierPath);
      enumEntries[enumKey] = identifierPath;
    }
  });

  return createEnumDeclaration(enumName, enumEntries);
}

// List entities
let enumContent = createEnumFromJsonFiles(
  "Entities",
  (obj) => getValueByPath(obj, "minecraft:entity/description/identifier"),
  packsPath + "BP/entities/"
);

// List items
enumContent += createEnumFromJsonFiles(
  "Items",
  (obj) => getValueByPath(obj, "minecraft:item/description/identifier"),
  packsPath + "BP/items/"
);

// List blocks
enumContent += createEnumFromJsonFiles(
  "Blocks",
  (obj) => getValueByPath(obj, "minecraft:block/description/identifier"),
  packsPath + "BP/blocks/"
);

// List sounds
if (fs.existsSync(packsPath + "RP/sounds/sound_definitions.json")) {
  let obj = loadJsonFile(packsPath + "RP/sounds/sound_definitions.json")[
    "sound_definitions"
  ];
  let pairs = {};
  for (const key of Object.keys(obj)) {
    pairs[toTitleCase(key)] = key;
  }
  enumContent += createEnumDeclaration("Sounds", pairs);
}

// List language keys
if (fs.existsSync(packsPath + "RP/texts/en_US.lang")) {
  let obj = loadLangFile(packsPath + "RP/texts/en_US.lang");
  let pairs = {};
  for (const [key, value] of obj) {
    pairs[
      toTitleCase(
        key
          .split(".")
          .map((x) => (x.includes(":") ? x.split(":", 2)[1] : x))
          .join(".")
      )
    ] = key;
  }
  enumContent += createEnumDeclaration("LangKeys", pairs);
}

// List structures
if (fs.existsSync(packsPath + "BP/structures")) {
  let obj = fs.readdirSync(packsPath + "BP/structures");
  let pairs = {};
  for (const namespace of obj) {
    if (fs.statSync(packsPath + `BP/structures/${namespace}`).isDirectory()) {
      let files = fs.readdirSync(packsPath + `BP/structures/${namespace}`);
      for (const file of files) {
        if (file.endsWith(".mcstructure")) {
          let id = file.split(".")[0];
          pairs[toTitleCase(`${namespace}:${id}`)] = `${namespace}:${id}`;
        }
      }
    }
  }
  enumContent += createEnumDeclaration("Structures", pairs);
}

// List loot tables. Every loot table is just a path to a file in `./packs/BP/loot_tables`. Recursively search for .json files.
if (fs.existsSync(packsPath + "BP/loot_tables")) {
  let obj = readdirSyncRecursive(packsPath + "BP/loot_tables").map((x) =>
    path.relative(packsPath + "BP/loot_tables", x).replace(/\\/g, "/")
  );
  let pairs = {};
  for (const file of obj) {
    if (file.endsWith(".json")) {
      const split = file.split(".");
      split.length -= 1;
      let id = split.join(".");
      pairs[toTitleCase(id)] = id;
    }
  }
  enumContent += createEnumDeclaration("LootTables", pairs);
}

// List particles
enumContent += createEnumFromJsonFiles(
  "Particles",
  (obj) => getValueByPath(obj, "particle_effect/description/identifier"),
  packsPath + "RP/particles/"
);

// Write to .d.ts file
const outputFilePath = gametestsPath + "src/" + settings.outputFile;

let existingContent = "";
if (fs.existsSync(outputFilePath)) {
  existingContent = fs.readFileSync(outputFilePath, "utf8");
}

if (existingContent !== enumContent) {
  fs.writeFileSync(outputFilePath, enumContent, "utf8");
  console.log(
    `Enum written to ${path.relative(process.env.ROOT_DIR, outputFilePath)}`
  );
}
