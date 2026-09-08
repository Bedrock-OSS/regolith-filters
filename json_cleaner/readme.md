# Json Cleaner

This small utility filter is intended to be used as the first filter in your Regolith project. It goes through your packs, removing comments from your JSON files and allowing later filters to read the JSON safely without worrying about comments.

Additionally it can strip root-level `$schema` fields, which Bedrock considers an error, and minify JSON files.

Version 3.0.0 has been rewritten in Rust by AI.

## Using the Filter

```json
{
    "filter": "json_cleaner",
    "settings": {
        "stripSchemas": true,
        "minify": true
    }
}
```

## Settings

| Setting        | Type      | Default | Description                                                                 |
|----------------|-----------|---------|-----------------------------------------------------------------------------|
| `stripSchemas` | `boolean` | `false` | Removes `$schema` fields from the root object of every JSON file.           |
| `minify`       | `boolean` | `false` | Minifies JSON files by removing whitespace outside of strings.              |

Comments are always removed. Unknown settings are ignored. A setting with a wrong type (for example `"minify": "true"`) or a settings argument that is not a JSON object stops the filter with an error before any file is touched.

## Supported platforms

Regolith 1.2.0 or later is required (the filter relies on the `when` field with the `os` and `arch` variables).

| Platform        | Binary                               |
|-----------------|--------------------------------------|
| Windows x64     | `bin/json_cleaner-windows-amd64.exe` |
| Windows arm64   | `bin/json_cleaner-windows-arm64.exe` |
| Linux x64       | `bin/json_cleaner-linux-amd64` (static, musl) |
| Linux arm64     | `bin/json_cleaner-linux-arm64` (static, musl) |
| macOS x64       | `bin/json_cleaner-macos-amd64`       |
| macOS arm64     | `bin/json_cleaner-macos-arm64`       |

Which binaries have actually been executed and tested where is listed in [test/benchmarks.md](test/benchmarks.md).

## What exactly happens to a file

The filter never parses your JSON into a data model. It scans the raw bytes and only *removes* bytes, so everything it keeps is preserved byte for byte:

* numbers keep their exact spelling (`1.0`, `1.00`, `1e+5`, `-0`, `0.00000000000000001`, `123456789012345678901234567890`);
* strings keep their escape sequences (`"\u0061"` stays `"\u0061"`), encoding and any non-UTF-8 bytes;
* property order, trailing commas and everything else stay as they are;
* keys are never rewritten, nothing is sorted, nothing is re-indented.

Removed:

* `// line` comments (up to, but not including, the line break) and `/* block */` comments (including line breaks inside them). An unterminated block comment is removed up to the end of the file.
* With `minify`: spaces, tabs, CR and LF outside of strings.
* With `stripSchemas`: every property of the *root object* whose decoded name is exactly `$schema` (`"$schema"` counts too), together with the separator that has to go. Nested `$schema` properties, root arrays and root primitives are left alone. The removal never introduces a structural error: `{"$schema":"x",}` becomes `{}`, `{"a":1,"$schema":"x"}` becomes `{"a":1}`, an existing trailing comma after a kept property stays. If the root object cannot be scanned safely (unbalanced brackets, missing value, unterminated string), `$schema` removal is skipped for that file and only comments/whitespace are removed.

Comment markers inside strings (`"http://a//b"`, `"/* text */"`) are of course not comments.

### Invalid input

For valid JSON with comments (JSONC) the result is valid JSON with the same meaning. For anything else the filter still never crashes and produces a deterministic result, but makes no promise about the meaning: it does not repair, validate or reject files. For example `1/*x*/2` minifies to `12`; an unterminated string is kept as is up to the end of the file.

### Files, timestamps and errors

* Only regular files with a `.json` extension (compared case-insensitively) inside `BP/` and `RP/` are processed. A missing `BP` or `RP` directory is fine. Symbolic links are not followed, even when `BP` or `RP` itself is a link.
* A file whose content does not change is not written at all: no write, no truncation, no timestamp update. (Merely reading the file may update its access time, as with any program.)
* A file whose content changes is rewritten in place and its modification time (and access time where the platform allows it) is restored exactly, so tools that rely on timestamps keep working. The file keeps its identity (no temporary file and rename). This means that an I/O error in the middle of a write can leave a partially rewritten file. The change time (`ctime` on Unix) is not preserved. Nothing is fsynced.
* Every file is opened for reading and writing, so a read-only file is an error even if it would not have needed a change.
* Any failure to walk a directory, open, read, write, truncate a file or restore its modification time is reported with the path and the operation, all files that could be processed are still processed, and the filter exits with a non-zero code so that Regolith stops.
* Files are processed in parallel (one file per task, a small fixed worker pool). The filter assumes nothing else modifies the packs while it runs.

## Differences from version 2.x (Node.js)

The rewrite fixes several bugs of the old implementation. The observable differences are:

* Non-UTF-8 bytes are preserved. 2.x decoded every file as UTF-8 and replaced invalid bytes with U+FFFD.
* With `minify`, property names are kept verbatim. 2.x decoded escapes in keys (`"\u0024schema"` became `"$schema"`, `"\/x"` became `"/x"`, an invalid `"\x61"` became `"61"`).
* With `minify`, invalid input is no longer silently truncated or "repaired" (2.x dropped everything after the first value, appended `}` to unterminated strings and cut strings at raw line breaks).
* With `stripSchemas`, *all* root `$schema` properties are removed (2.x removed only the first), the rest of the file is not re-indented (2.x re-indented the affected lines with tabs), and `{"$schema":"x",}` becomes `{}` instead of the broken `{,}`.
* With `stripSchemas`, a file whose root object cannot be scanned safely is left structurally untouched (2.x could destroy such a file, e.g. `{"$schema":[1,"k":2}` became `{`).
* Comment removal without `minify` is byte-identical to 2.x for every fixture in `test/tests/fixtures` except the non-UTF-8 one (see `test/tools/compare_with_old.py`).
* `.JSON` files (upper case extension) are processed on every platform; 2.x processed them on Windows and macOS only.
* A settings argument that is not a JSON object, or a setting with a wrong type, is an error (2.x ignored wrong types and treated any truthy value as `true`).
* Large projects work: 2.x started a read and a write for every file at once and died with `EMFILE: too many open files` on a 10 000-file project; 3.x uses a small fixed worker pool.

## Where the source code is

The whole Rust crate (`Cargo.toml`, `src/`, `tests/`, `benches/`, `bench/`, `tools/`, `benchmarks.md`) lives in the `test/` directory of this filter, not next to `filter.json`.

The name is deliberate. Regolith installs a filter by copying its whole directory into `.regolith/cache/filters/<name>` and then deletes the top-level `test` folder (that folder is reserved for a filter's own tests and is never used at run time). Putting the crate in `test/` therefore keeps the sources, the several hundred test fixtures and the benchmarks out of every user's `.regolith/cache`: only what the filter needs to run is installed, that is `filter.json`, the prebuilt binaries in `bin/`, `schema.json`, `completion.md` and this readme. Nothing in `test/` is needed to use the filter; it is needed only to build, test or release it.

```
json_cleaner/
├── filter.json      installed
├── bin/             installed: prebuilt binaries, one per platform
├── schema.json      installed: settings schema
├── completion.md    installed
├── readme.md        installed
└── test/            NOT installed: the Rust crate (sources, tests, benchmarks, tools)
```

## Development

Requirements: a stable Rust toolchain (1.75 or newer). Nothing else.

All commands below are run inside `test/` (see *Where the source code is* above):

```sh
cd test
cargo test                                      # unit, fixture, differential (proptest), filesystem and CLI tests
cargo clippy --all-targets -- -D warnings
cargo fmt --check
cargo build --release                           # target/release/json_cleaner[.exe]
cargo bench --bench transform                   # Criterion micro-benchmarks of the scanner
python bench/e2e.py --rust target/release/json_cleaner.exe --work /path/on/the/disk/to/measure [--node path/to/old/json_cleaner.js]
python tools/compare_with_old.py target/release/json_cleaner.exe   # differential run against 2.0.2 (needs git, node, npm)
```

The binary takes the settings as its first argument, exactly as Regolith passes them, and works on `BP/` and `RP/` in the current directory. Developer overrides, which are not part of the settings contract:

| Variable               | Meaning                                                            |
|------------------------|--------------------------------------------------------------------|
| `JSON_CLEANER_THREADS` | Number of worker threads (`0` or unset: automatic, `1`: sequential) |
| `JSON_CLEANER_BACKEND` | `memchr` (default) or `scalar` (the reference scanner)             |
| `JSON_CLEANER_VERBOSE` | Print a one-line summary on success                                |

Code layout (inside `test/`): `src/transform.rs` (comment/whitespace scanner, scalar reference + memchr backend), `src/schema.rs` (root `$schema` remover), `src/process.rs` (per-file I/O and timestamp handling), `src/run.rs` (directory walk and worker pool), `src/settings.rs`, `src/main.rs`.

### Releasing binaries

Regolith installs a filter by cloning this repository at the tag `json_cleaner-<version>` and copying this directory, so the binaries have to be committed under `bin/` (the same mechanism as the `jsonte` filter). The GitHub Actions workflow `.github/workflows/json_cleaner.yml`:

1. runs `cargo fmt --check`, `clippy`, `test` and `build --release` on every change;
2. builds *and tests* every distributed target natively on a runner of the same architecture;
3. when started manually with a `release_version` input, downloads the six binaries, commits them to `bin/`, tags `json_cleaner-<version>` and pushes.

The Linux and macOS binaries must be committed with the executable bit (`100755`). On Windows run `git update-index --chmod=+x bin/json_cleaner-linux-* bin/json_cleaner-macos-*` before committing by hand; the workflow does `chmod +x` on a Linux runner. Distributed binaries are never built with `-C target-cpu=native`.

# Changelog

### 3.0.0

Rewrite as a native binary (Rust), no runtime required. Lexical, byte-preserving transformation; exact modification-time preservation; unchanged files are not written; root `$schema` removal handles every occurrence and escaped names; parallel processing. See *Differences from version 2.x* above and `test/benchmarks.md` for measurements.

### 2.0.2

Switch to the `glob` package for compatibility.

### 2.0.1

Fix float encoding issues in json_cleaner by @ink0rr in #65

### 2.0.0

Complete rewrite to NodeJS by @ink0rr in #63
Add `stripSchemas` option to remove `$schema` fields from root objects
Add `minify` option to minify the JSON

### 1.1.1

Fix encoding when saving file in json_cleaner.

### 1.1.0

Fix encoding issues in json_cleaner and handle errors better.

### 1.0.0

The initial release of the Json Cleaner filter.
