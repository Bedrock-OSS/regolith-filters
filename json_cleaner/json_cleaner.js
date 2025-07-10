import * as JSONC from "jsonc-parser";
import { glob, readFile, writeFile } from "node:fs/promises";

async function cleanJson(path) {
  const txt = await readFile(path, "utf8");
  const stripped = JSONC.stripComments(txt);
  if (txt !== stripped) {
    writeFile(path, stripped);
  }
}

for (const dir of ["BP", "RP"]) {
  for await (const entry of glob(`${dir}/**/*.json`)) {
    cleanJson(entry);
  }
}
