import * as JSONC from "jsonc-parser";
import { glob, readFile, writeFile } from "node:fs/promises";

const defSettings = {
  stripSchemas: false,
  minify: false,
}
const argParsed = process.argv[2] ? JSON.parse(process.argv[2]) : {};
const settings = Object.assign({}, defSettings, argParsed);

async function cleanJson(path) {
  const txt = await readFile(path, "utf8");
  let stripped = JSONC.stripComments(txt);
  let modified = txt !== stripped;
  if (settings.stripSchemas || settings.minify) {
    const parsed = JSON.parse(stripped);
    if (settings.stripSchemas && parsed.$schema) {
      delete parsed.$schema;
      modified = true;
      if (!settings.minify) {
        stripped = JSON.stringify(parsed, null, 2);
      } else {
        stripped = JSON.stringify(parsed);
      }
    } else if (settings.minify) {
      stripped = JSON.stringify(parsed);
      modified = true;
    }
  }
  if (modified) {
    writeFile(path, stripped);
  }
}

for (const dir of ["BP", "RP"]) {
  for await (const entry of glob(`${dir}/**/*.json`)) {
    cleanJson(entry);
  }
}
