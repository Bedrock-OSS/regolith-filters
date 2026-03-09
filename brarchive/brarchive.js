const path = require("path");
const fsSync = require("fs");
const { processPackInPlace } = require("./brarchive_core");

/** @type {{ mode: "replace" | "keep_both"; minify: boolean }} */
const DEFAULT_SETTINGS = {
  mode: "replace",
  minify: true
};

const VALID_MODES = ["replace", "keep_both"];
const PACK_NAMES = ["BP", "RP"];

/**
 * Regolith filter entrypoint. Operates on the Regolith temp directory (cwd = .regolith/tmp)
 * which contains BP and RP.
 * @returns {string[]} Absolute paths to existing pack directories.
 */
const getPackRoots = () =>
  PACK_NAMES.map((name) => path.resolve(process.cwd(), name)).filter(
    (p) => fsSync.existsSync(p) && fsSync.statSync(p).isDirectory()
  );

/**
 * @param {string} raw
 * @returns {string}
 */
const parseSettings = (raw) => (raw ? JSON.parse(raw) : {});

/** @type {import("./brarchive_core").ProcessPackOptions} */
const run = async () => {
  const raw = process.argv[2];
  const settings = { ...DEFAULT_SETTINGS, ...parseSettings(raw) };

  if (!VALID_MODES.includes(settings.mode)) {
    throw new Error(`brarchive: unknown mode '${settings.mode}'. Expected 'replace' or 'keep_both'.`);
  }

  const roots = getPackRoots();
  if (roots.length === 0) {
    throw new Error(
      "brarchive: no BP or RP directory found. Run from Regolith's filter context (cwd = temp directory with BP/RP)."
    );
  }

  const options = {
    removeArchivedFiles: settings.mode === "replace",
    minify: Boolean(settings.minify)
  };

  await Promise.all(roots.map((root) => processPackInPlace(root, options)));
};

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
