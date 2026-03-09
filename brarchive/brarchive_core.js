const path = require("path");
const os = require("os");
const fs = require("fs").promises;
const { TextDecoder } = require("util");
const JSON5 = require("json5");

// brarchive format constants
const MAGIC = 0x267052a0b125277dn;
const VERSION = 1;
const ENTRY_NAME_LEN_MAX = 247;

const BANNED_ROOT_DIRS = new Set(["font", "materials", "scripts", "sounds", "subpacks", "texts", "textures"]);

/**
 * Paths relative to pack root (forward slashes). Each pack—including subpacks—is treated as its own root,
 * so "ui/_global_variables.json" excludes that file in both the main pack and in each subpack.
 */
const EXCLUDED_PATHS = new Set(["ui/_global_variables.json"]);

const toNormalizedPath = (p) => path.normalize(p).split(path.sep).join("/").toLowerCase();

const UTF8_DECODER = new TextDecoder("utf-8", { fatal: true });

/**
 * Partitions directory entries into subdirs and files.
 * @param {import("fs").Dirent[]} entries
 * @returns {{ dirnames: string[]; filenames: string[] }}
 */
const partitionEntries = (entries) =>
  entries.reduce(
    (acc, e) => {
      if (e.isDirectory()) acc.dirnames.push(e.name);
      else if (e.isFile()) acc.filenames.push(e.name);
      return acc;
    },
    { dirnames: [], filenames: [] }
  );

/**
 * @param {string} filePath
 * @returns {Promise<boolean>}
 */
const isValidUtf8 = async (filePath) => {
  try {
    const data = await fs.readFile(filePath);
    UTF8_DECODER.decode(data);
    return true;
  } catch {
    return false;
  }
};

/**
 * Finds directories to archive and tracks archived files.
 * @param {string} srcRoot
 * @returns {Promise<{ targets: { dirpath: string; rel: string }[]; archivedFiles: Set<string> }>}
 */
async function findTargets(srcRoot) {
  const targets = [];
  const archivedFiles = new Set();

  const walk = async (currentDir) => {
    const absDir = path.resolve(currentDir);
    const parts = path.normalize(absDir).split(path.sep);

    if (parts.includes("__brarchive")) return;

    const rel = path.relative(srcRoot, absDir) || ".";
    const entries = await fs.readdir(absDir, { withFileTypes: true });
    const { dirnames, filenames } = partitionEntries(entries);

    if (rel === ".") {
      const filtered = dirnames.filter((d) => !BANNED_ROOT_DIRS.has(d) && d !== "__brarchive");
      await Promise.all(filtered.map((d) => walk(path.join(absDir, d))));
      return;
    }

    if (rel.split(path.sep)[0] === "subpacks") return;

    const filesToArchive = filenames.filter((name) => {
      const fileRelPath = toNormalizedPath(path.join(rel, name));
      return !EXCLUDED_PATHS.has(fileRelPath);
    });

    if (filesToArchive.length === 0) {
      await Promise.all(dirnames.map((d) => walk(path.join(absDir, d))));
      return;
    }

    const utf8Checks = await Promise.all(filesToArchive.map((name) => isValidUtf8(path.join(absDir, name))));
    const allUtf8 = utf8Checks.every(Boolean);

    if (allUtf8) {
      targets.push({ dirpath: absDir, rel });
      filesToArchive.forEach((name) => archivedFiles.add(path.resolve(absDir, name)));
    }

    await Promise.all(dirnames.map((d) => walk(path.join(absDir, d))));
  };

  await walk(srcRoot);
  return { targets, archivedFiles };
}

/**
 * Serializes entry map to .brarchive buffer.
 * Entries are sorted lexicographically (BTreeMap order).
 * @param {Map<string, string> | Iterable<[string, string]>} entries
 * @returns {Buffer}
 */
function serializeBrarchive(entries) {
  const sorted = [...entries].sort((a, b) => a[0].localeCompare(b[0]));
  const entryCount = sorted.length;

  const HEADER_SIZE = 16;
  const DESCRIPTOR_SIZE = 1 + ENTRY_NAME_LEN_MAX + 8;

  let totalContentsLen = 0;
  const descriptors = sorted.map(([name, contents]) => {
    const nameBytes = Buffer.from(String(name), "utf8");

    if (nameBytes.length > ENTRY_NAME_LEN_MAX) {
      throw new Error(`Entry name too long (${nameBytes.length} bytes), max is ${ENTRY_NAME_LEN_MAX}`);
    }

    const contentBuf = Buffer.from(String(contents), "utf8");
    const len = contentBuf.length >>> 0;
    const offset = totalContentsLen >>> 0;
    totalContentsLen += len;

    return { nameBytes, contents: contentBuf, offset, len };
  });

  const buf = Buffer.allocUnsafe(HEADER_SIZE + DESCRIPTOR_SIZE * entryCount + totalContentsLen);
  let pos = 0;

  buf.writeBigUInt64LE(MAGIC, pos);
  pos += 8;
  buf.writeUInt32LE(entryCount >>> 0, pos);
  pos += 4;
  buf.writeUInt32LE(VERSION >>> 0, pos);
  pos += 4;

  for (const { nameBytes, offset, len } of descriptors) {
    const nameLen = nameBytes.length;
    buf.writeUInt8(nameLen, pos);
    pos += 1;
    nameBytes.copy(buf, pos);

    if (nameLen < ENTRY_NAME_LEN_MAX) {
      buf.fill(0, pos + nameLen, pos + ENTRY_NAME_LEN_MAX);
    }

    pos += ENTRY_NAME_LEN_MAX;
    buf.writeUInt32LE(offset, pos);
    pos += 4;
    buf.writeUInt32LE(len, pos);
    pos += 4;
  }

  for (const { contents } of descriptors) {
    contents.copy(buf, pos);
    pos += contents.length;
  }

  return buf;
}

/**
 * Minifies JSON content for archive storage. Non-JSON or parse failures return original.
 * @param {string} fileName
 * @param {string} contents
 * @param {boolean} minify
 * @returns {string}
 */
const maybeMinifyContent = (fileName, contents, minify) => {
  if (!minify) return contents;
  if (path.extname(fileName).toLowerCase() !== ".json") return contents;

  try {
    const parsed = JSON5.parse(contents);
    return JSON.stringify(parsed);
  } catch {
    return contents;
  }
};

/**
 * Encodes a directory into a single .brarchive file.
 * @param {string} dirpath
 * @param {string} outRoot
 * @param {string} rel
 * @param {boolean} [minify=false]
 */
async function encodeDirectoryToBrarchive(dirpath, outRoot, rel, minify = false) {
  const archivePath = path.join(outRoot, rel) + ".brarchive";
  const entries = await fs.readdir(dirpath, { withFileTypes: true });

  const fileEntries = entries.filter((e) => {
    if (!e.isFile()) return false;

    const fileRelPath = toNormalizedPath(path.join(rel, e.name));
    return !EXCLUDED_PATHS.has(fileRelPath);
  });

  if (fileEntries.length === 0) return;

  const map = new Map();
  await Promise.all(
    fileEntries.map(async (entry) => {
      const filePath = path.join(dirpath, entry.name);
      const contents = await fs.readFile(filePath, "utf8");
      const stored = maybeMinifyContent(entry.name, contents, minify);
      map.set(entry.name, stored);
    })
  );

  await fs.mkdir(path.dirname(archivePath), { recursive: true });
  await fs.writeFile(archivePath, serializeBrarchive(map));
}

/**
 * Removes empty directories under root. Skips directories in skipDirNames.
 * @param {string} root
 * @param {Set<string>} [skipDirNames]
 */
async function cleanupEmptyDirs(root, skipDirNames = new Set()) {
  const walk = async (dir) => {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    let hasContent = false;

    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (skipDirNames.has(entry.name)) continue;

        const childEmpty = await walk(fullPath);

        if (!childEmpty) hasContent = true;
      } else {
        hasContent = true;
      }
    }

    if (dir !== root && !hasContent) {
      try {
        await fs.rmdir(dir);
      } catch {
        // ignore
      }
      return true;
    }
    return !hasContent;
  };

  await walk(root);
}

/**
 * Copies non-archived files from srcRoot to dstRoot.
 * @param {string} srcRoot
 * @param {string} dstRoot
 * @param {Set<string>} archivedFiles
 * @param {boolean} [skipSubpacks=true]
 */
async function copyNonArchivedFiles(srcRoot, dstRoot, archivedFiles, skipSubpacks = true) {
  const walk = async (currentDir) => {
    const absDir = path.resolve(currentDir);

    if (path.normalize(absDir).split(path.sep).includes("__brarchive")) return;

    const relDir = path.relative(srcRoot, absDir) || ".";
    const entries = await fs.readdir(absDir, { withFileTypes: true });
    const { dirnames, filenames } = partitionEntries(entries);

    const filteredDirs = relDir === "." && skipSubpacks ? dirnames.filter((d) => d !== "subpacks") : dirnames;

    const destDir = relDir === "." ? dstRoot : path.join(dstRoot, relDir);
    const toCopy = filenames.filter((name) => !archivedFiles.has(path.resolve(absDir, name)));

    if (toCopy.length > 0) {
      await fs.mkdir(destDir, { recursive: true });
      await Promise.all(toCopy.map((name) => fs.copyFile(path.join(absDir, name), path.join(destDir, name))));
    }

    await Promise.all(filteredDirs.map((d) => walk(path.join(absDir, d))));
  };

  await walk(srcRoot);
}

/**
 * Runs encode jobs in parallel with a worker pool.
 * @param {Array<{ dirpath: string; rel: string; outRoot: string; minify?: boolean }>} jobs
 */
const runEncodeWorkers = async (jobs) => {
  const workerCount = Math.min(os.cpus()?.length ?? 4, jobs.length);
  let index = 0;

  const worker = async () => {
    while (true) {
      const i = index++;
      if (i >= jobs.length) break;

      const { dirpath, rel, outRoot, minify = false } = jobs[i];

      await encodeDirectoryToBrarchive(dirpath, outRoot, rel, minify);
    }
  };

  await Promise.all(Array.from({ length: workerCount }, worker));
};

/**
 * Sets pack_optimization_version in manifest.json (required for brarchive).
 * @param {string} packRoot
 * @param {{ requireManifest?: boolean }} [opts] - If requireManifest is false, skips when manifest missing (subpacks).
 */
async function setPackOptimizationVersion(packRoot, opts = {}) {
  const { requireManifest = true } = opts;
  const manifestPath = path.join(packRoot, "manifest.json");
  let raw;

  try {
    raw = await fs.readFile(manifestPath, "utf8");
  } catch (err) {
    if (err.code === "ENOENT") {
      if (requireManifest) {
        throw new Error(`brarchive: manifest.json not found at ${manifestPath}. Ensure the pack has a manifest.`);
      }

      return;
    }
    throw err;
  }

  const manifest = JSON.parse(raw);
  const header = manifest.header ?? (manifest.header = {});

  header.pack_optimization_version = "0.1.0";

  await fs.writeFile(manifestPath, JSON.stringify(manifest, null, 4), "utf8");
}

/**
 * Full copy mode: srcRoot -> dstRoot.
 * @param {string} srcRoot
 * @param {string} dstRoot
 */
async function processPack(srcRoot, dstRoot) {
  const absSrc = path.resolve(srcRoot);
  const absDst = path.resolve(dstRoot);
  const outRoot = path.join(absDst, "__brarchive");

  await fs.mkdir(outRoot, { recursive: true });

  const { targets, archivedFiles } = await findTargets(absSrc);

  if (targets.length > 0) {
    const jobs = targets.map(({ dirpath, rel }) => ({
      dirpath,
      rel,
      outRoot
    }));
    await runEncodeWorkers(jobs);
  }

  await cleanupEmptyDirs(outRoot);
  await copyNonArchivedFiles(absSrc, absDst, archivedFiles, true);

  const subpacksPath = path.join(absSrc, "subpacks");
  const entries = await fs
    .readdir(subpacksPath, { withFileTypes: true })
    .catch((err) => (err.code === "ENOENT" ? [] : Promise.reject(err)));

  const subpackDirs = entries.filter((e) => e.isDirectory());

  await Promise.all(
    subpackDirs.map((e) => processPack(path.join(subpacksPath, e.name), path.join(absDst, "subpacks", e.name)))
  );
}

/**
 * @typedef {{ removeArchivedFiles?: boolean; minify?: boolean; isRootPack?: boolean }} ProcessPackOptions
 */

/**
 * Process a pack root in place: create __brarchive with .brarchive files.
 * Sets header.pack_optimization_version = "0.1.0" in manifest.json.
 * @param {string} root - Pack root path (e.g. "BP" or "RP").
 * @param {ProcessPackOptions} [options]
 */
async function processPackInPlace(root, options = {}) {
  const { removeArchivedFiles = false, minify = false, isRootPack = true } = options;
  const absRoot = path.resolve(root);

  await setPackOptimizationVersion(absRoot, { requireManifest: isRootPack });

  const outRoot = path.join(absRoot, "__brarchive");

  await fs.mkdir(outRoot, { recursive: true });

  const { targets, archivedFiles } = await findTargets(absRoot);

  if (targets.length > 0) {
    const jobs = targets.map(({ dirpath, rel }) => ({
      dirpath,
      rel,
      outRoot,
      minify
    }));

    await runEncodeWorkers(jobs);
  }

  await cleanupEmptyDirs(outRoot);

  if (removeArchivedFiles && archivedFiles.size > 0) {
    await Promise.all(
      [...archivedFiles].map((p) =>
        fs.unlink(p).catch((err) => {
          if (err.code !== "ENOENT") throw err;
        })
      )
    );
    await cleanupEmptyDirs(absRoot, new Set(["__brarchive"]));
  }

  const subpacksPath = path.join(absRoot, "subpacks");
  const entries = await fs
    .readdir(subpacksPath, { withFileTypes: true })
    .catch((err) => (err.code === "ENOENT" ? [] : Promise.reject(err)));

  const subpackDirs = entries.filter((e) => e.isDirectory());

  await Promise.all(
    subpackDirs.map((e) => processPackInPlace(path.join(subpacksPath, e.name), { ...options, isRootPack: false }))
  );
}

module.exports = {
  findTargets,
  serializeBrarchive,
  encodeDirectoryToBrarchive,
  processPack,
  processPackInPlace
};
