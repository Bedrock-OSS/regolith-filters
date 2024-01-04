const path = require("path");
const fs = require("fs");
const json5 = require("json5");
const child_process = require("child_process");

//Load config.json file
// We are in .regolith/cache/filters/gametests and config is in root directory
const rootPath = path.resolve(__dirname, "../../../../");
const configPath = path.resolve(rootPath, "config.json");
const config = json5.parse(fs.readFileSync(configPath, "utf-8"));

// We need to get path to the data folder, which is in #/regolith/dataPath
const dataPath = config.regolith.dataPath;

if (!dataPath) {
  throw new Error("dataPath not found in config.json");
}

const gametestsDataPath = path.resolve(path.resolve(rootPath, dataPath), "gametests");

if (fs.existsSync(gametestsDataPath)) {
  console.log("Installing dependencies for gametests in", gametestsDataPath);
  child_process.execSync(`npm install`, {
    cwd: gametestsDataPath, 
    stdio: "inherit"
  });
} else {
  console.log("gametests data folder not found, execute 'npm install' manually in", gametestsDataPath);
}