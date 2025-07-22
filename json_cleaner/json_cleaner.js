import * as JSONC from "jsonc-parser";
import { glob, readFile, writeFile } from "node:fs/promises";

const defSettings = {
  stripSchemas: false,
  minify: false,
};
const argParsed = process.argv[2] ? JSON.parse(process.argv[2]) : {};
const settings = Object.assign({}, defSettings, argParsed);

function minifyJSON(txt) {
  let res = "";
  JSONC.visit(txt, {
    onObjectBegin: () => {
      res += "{";
    },
    onObjectProperty: (name) => {
      res += `"${name}"`;
    },
    onObjectEnd: () => {
      res += "}";
    },
    onArrayBegin: () => {
      res += "[";
    },
    onArrayEnd: () => {
      res += "]";
    },
    onLiteralValue: (_, offset, length) => {
      res += txt.slice(offset, offset + length);
    },
    onSeparator: (sep) => {
      res += sep;
    },
  });
  return res;
}

async function cleanJson(path) {
  const txt = await readFile(path, "utf8");
  let res = txt;

  if (settings.stripSchemas) {
    try {
      // This might throw if the top-level JSON is not an object
      const edits = JSONC.modify(res, ["$schema"], undefined, {
        formattingOptions: { keepLines: true },
      });
      res = JSONC.applyEdits(res, edits);
    } catch {
      // Ignore the errors
    }
  }

  res = settings.minify ? minifyJSON(res) : JSONC.stripComments(res);

  if (txt !== res) {
    writeFile(path, res);
  }
}

for (const dir of ["BP", "RP"]) {
  for await (const entry of glob(`${dir}/**/*.json`)) {
    cleanJson(entry);
  }
}
