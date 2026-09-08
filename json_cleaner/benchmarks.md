# json_cleaner 3.0.0 – measurements and verification status

## Summary

* On a real Bedrock project (432 JSON files) the new filter runs in about
  **16–20 ms**, the old Node.js filter in about **150 ms**.
* When files are large or mostly unchanged, the new filter is **5–40x
  faster** (100 files of 1 MiB: 0.04–0.26 s vs 2–8.5 s).
* When thousands of files must be rewritten, both are limited by the
  filesystem (about **1.4 ms per rewritten file** on NTFS here), so the gap
  shrinks to 10–30 %.
* The old filter **crashes** on a 10 000-file project when it has to write
  (`EMFILE: too many open files`); the new one does not.
* The JSON scanning itself is 1–5 % of the run time on realistic projects.
  That is why there is no custom SIMD code and no mmap: they could only speed
  up the part that does not matter.
* Default worker count is `min(CPU threads, 8)`; more threads help when files
  are only read, not when they are written.

Everything below was measured on one machine in one session (see
*Environment* in the appendix). The numbers are reproducible with the
commands given but describe this machine, not a universal truth.

## How to read the numbers

Two kinds of measurements are used:

* **Micro-benchmarks** (`cargo bench --bench transform`): the in-memory
  transformation only, one thread, no files. Reported as throughput in MiB/s
  of input. Higher is better.
* **End-to-end** (`bench/e2e.py`): the whole process (start to exit) on a
  directory tree with `BP/` and `RP/`, exactly as Regolith runs it. Reported
  in seconds, median of several repetitions with min..max. Lower is better.

Terms used in the end-to-end tables:

| Term | Meaning |
|---|---|
| `10000x2K`, `5000x8K`, `1000x64K`, `100x1M`, `small_50x4K` | Synthetic corpora: number of files × size per file (Bedrock-like entity JSON). `real` = a private real add-on, 432 files. |
| `dirty=0 / 0.3 / 1` | Fraction of files that contain comments. In the `comments` mode only those files change. In `minify`, `schema` and `schema_minify` every pretty-printed file changes, so those are always "100 % of files written". |
| `first run` | The filter run on a fresh copy of the corpus: this is the measurement that matters. |
| `second run` | The same filter run again on the already cleaned files: nothing has to be written, so this shows the pure read/scan cost. |
| `rust t=1` | New filter, one thread (`JSON_CLEANER_THREADS=1`). |
| `rust auto` | New filter, default thread count (8 on this machine). |
| `node 2.0.2` | Old filter (tag `json_cleaner-2.0.2`, Node.js v22.20.0). |
| `warm` | See *The Windows Defender effect* below. All headline tables are warm. |

## Results

### 1. Old filter vs new filter

Representative rows (warm resets, SATA SSD, 3 repetitions; full tables in the
appendix). Values are `first run / second run` medians in seconds.

| scenario | rust t=1 | rust auto | node 2.0.2 |
|---|---|---|---|
| real project, comments | 0.016 / 0.016 | 0.020 / 0.020 | 0.155 / 0.150 |
| real project, schema_minify | 0.018 / 0.016 | 0.017 / 0.016 | 0.154 / 0.151 |
| 100x1M, dirty=0, comments (nothing to write) | 0.11 / 0.10 | 0.04 / 0.04 | 1.96 / 2.01 |
| 100x1M, dirty=1, schema_minify (all written) | 0.49 / 0.15 | 0.26 / 0.05 | 8.36 / 5.75 |
| 1000x64K, dirty=0.3, comments | 0.67 / 0.26 | 0.51 / 0.15 | 1.74 / 1.35 |
| 1000x64K, dirty=1, schema_minify | 1.47 / 0.30 | 1.49 / 0.10 | 6.26 / 2.88 |
| 5000x8K, dirty=1, comments (all written) | 5.58 / 1.05 | 5.26 / 0.39 | 5.96 / 1.61 |
| 5000x8K, dirty=1, schema_minify | 5.32 / 1.27 | 5.22 / 0.41 | 7.89 / 3.00 |
| 10000x2K, dirty=0, comments | 1.80 / 1.87 | 0.77 / 0.71 | 1.67 / 1.76 |
| 10000x2K, dirty=0.3, comments | 5.35 / 1.91 | 4.40 / 0.78 | 5.15 / 1.87 |
| 10000x2K, dirty=1, any writing mode | 14.2 / 3.2 | 13.1 / 0.76 | crashes (`EMFILE`) |

What this shows:

* Small projects: the new filter is about 8x faster and most of its 16 ms is
  process start-up. Most of Node's 150 ms is Node's own start-up.
* Large files: 5–40x faster, because the new filter scans bytes once and
  writes only when something changed, while the old one always re-parses and
  re-serializes (its "second run" is still 1.3–6 s).
* Many small files that all need a rewrite: the filesystem dominates (about
  1.4 ms per rewritten file, 0.15 ms per read-only file on NTFS here). Both
  filters end up within 10–30 % of each other.
* The old filter starts a read and a write for every file at once and dies
  with `EMFILE` at 10 000 files (on both disks tested).

Every scenario produced byte-identical output from the new filter (1 thread
and 8 threads) and, except in the `schema` mode, identical to the old filter.
In `schema` mode the old filter re-indents with tabs and removes only the
first `$schema` (documented difference, see readme).

### 2. Number of worker threads

Warm, `comments` mode, all files dirty, seconds (median):

| corpus | 1 thread | 2 | 4 | 8 | 16 | auto (8) |
|---|---|---|---|---|---|---|
| 10000x2K first run (all written) | 14.2 | 11.2 | 15.1 | 14.2 | 12.7 | 13.1 |
| 10000x2K second run (read only) | 3.17 | 1.13 | 0.90 | 0.75 | 0.73 | 0.76 |
| 1000x64K first run (all written) | 1.33 | 1.14 | 1.44 | 1.29 | 1.31 | 1.39 |
| 1000x64K second run (read only) | 0.32 | 0.16 | 0.10 | 0.10 | 0.09 | 0.09 |
| small_50x4K first run | 0.035 | 0.029 | 0.028 | 0.030 | 0.032 | 0.028 |

Same on the NVMe disk, 10000x2K: first run 14.2 / 12.3 / 12.3 / 14.4 / – /
13.5 s, second run 2.15 / 0.83 / 0.51 / 0.35 / – / 0.42 s.

What this shows:

* Reading and scanning scales: 4–8 threads are 3–4x faster than one, 16 adds
  nothing.
* Rewriting does not scale: NTFS serializes the write/truncate/timestamp
  work, whatever the thread count.
* On a 50-file project the pool costs nothing measurable.

**Decision:** `default_threads() = min(available_parallelism, 8)`, overridable
with `JSON_CLEANER_THREADS`. Not 1, because with the Defender effect below
threads matter a lot; not 16, because it never helped. Measured on one
machine with two SSDs, so this is a conservative default, not an optimum.

### 3. The Windows Defender effect (why "warm")

This machine has Windows Defender real-time protection with no exclusions.
The *first open* of a file that another process just created or modified
costs **17–32 ms** here (an on-access scan), no matter whether it is opened
read-only or read/write. The second open costs 0.2–0.5 ms, and the actual
rewrite (write, truncate, timestamps, close) 1–2 ms for a 2–64 KiB file.

This is exactly the situation in Regolith: it copies the packs into
`.regolith/tmp` and then the filter opens every file. So on Windows with
Defender, any filter pays this scan, and it dominates everything:

| 1000x64K, dirty=1, comments, *unwarmed* | first run | second run |
|---|---|---|
| rust, 1 thread | 17.65 s | 0.26 s |
| rust, auto (8) | 4.81 s | 0.09 s |
| node 2.0.2 | 7.19 s | 1.24 s |

| 10000x2K, dirty=1, comments, *unwarmed*, rust only | 1 thread | 2 | 4 | 8 | 16 |
|---|---|---|---|---|---|
| first run | 200 s | 78 s | 42 s | 31 s | 27 s |

The scan is parallelizable, which is why the old filter (all I/O in flight
at once) beats a single-threaded run here, and why the default is 8 threads.

To compare the two filters rather than the antivirus, the harness has
`--warm`: after every reset it opens and reads each file once (16 threads),
outside the timed region. All tables in this document are warm unless marked
*unwarmed*. Note that the page cache is warm in every run (the reset has just
written the files); nothing here is a cold-cache measurement.

### 4. Scanner backend: scalar vs memchr

Throughput of the in-memory transformation in MiB/s (64 KiB inputs; other
sizes in the appendix):

| input | comments mode: scalar → memchr | minify mode: scalar → memchr |
|---|---|---|
| pretty JSON, no comments | 160 → 1002 | 247 → 450 |
| comment on almost every line | 238 → 560 | 203 → 528 |
| many strings with escapes | 166 → 581 | 207 → 591 |
| already minified | 161 → 243 | 239 → 371 |
| few very long strings | 169 → 26587 | 249 → 14935 |
| single line, a token every 8 bytes | 141 → 339 | 262 → 247 |
| tabs and slashes everywhere | 151 → 356 | 235 → 357 |

The memchr backend is the default. The scalar backend stays as the reference
implementation for the differential tests. The one case where memchr is
slower (single line of tiny tokens in minify mode, about 8 %) is the
adversarial case the harness was built for; it does not occur in Bedrock
packs.

A first version of the minify path used two `memchr3` searches per token
(one for quote/slash/space, one for tab/CR/LF bounded by the first result).
It was *slower than the scalar loop* on pretty JSON (for example 182 vs 250
MiB/s, and 84 vs 218 on the tiny-token line), because an interesting byte
occurs every few bytes and the call overhead dominates. It was replaced by a
256-entry lookup table for the normal state; strings and comments still use
`memchr2` / `memmem`, which is where the long runs are.

The root `$schema` pass is a plain byte loop at about 400 MiB/s: 5 ms per
2 MB of JSON, not worth optimizing next to file I/O.

### 5. Share of scanning in the total time

Derived from the numbers above (no sampling profiler was used; at this ratio
that is sufficient):

| corpus | scanning (CPU, one thread) | whole run |
|---|---|---|
| real project, ~1 MB of JSON | ~2 ms | 16–20 ms |
| 10000x2K (20 MB) | 25–50 ms | 0.7–1.9 s read-only, 5–14 s when written |
| 100x1M (100 MB) | 0.1–0.25 s | 0.04–0.5 s with 8 threads |

Only on very large files does the scanner show up at all, and there the
worker pool hides it.

## Decisions taken from the measurements

* **memchr backend is the default**, scalar kept as reference.
* **Default threads = min(CPU threads, 8)**.
* **Custom SIMD (`std::arch` AVX2/NEON): not implemented.** The precondition
  (scanner still a significant share of end-to-end time) is not met; `memchr`
  already uses AVX2/NEON internally for the long runs.
* **mmap (`memmap2`): not tested.** Per-file cost is dominated by the open
  (Defender) and by write/truncate/timestamp calls, none of which mmap
  changes, and it would add map/unmap plus complications for shrinking
  files on Windows.

## Verification status of the distributed binaries

| Binary | Built | Tests executed | Fresh `regolith install` + `regolith run` |
|---|---|---|---|
| `json_cleaner-windows-amd64.exe` | yes, locally (x86_64-pc-windows-msvc, rustc 1.94.0) | yes: full `cargo test` on Windows 11 | yes: Regolith 1.7.0, installed from a local HTTPS git server (tag `json_cleaner-3.0.0`), both settings combinations, plus the unsupported-platform fallback |
| `json_cleaner-linux-amd64` | yes, cross-compiled locally (x86_64-unknown-linux-musl, rust-lld, static-pie) | yes: full `cargo test` on Linux x86_64 in WSL2 (glibc build of the same sources) + smoke run of the musl binary | yes: Regolith 1.7.0 linux_amd64 in WSL2, installed from the same server, exec bit preserved (100755) |
| `json_cleaner-linux-arm64` | yes, cross-compiled locally (aarch64-unknown-linux-musl) | **no** (no arm64 hardware here) | no |
| `json_cleaner-windows-arm64.exe` | **no** (no MSVC arm64 toolset installed locally); CI job defined | no | no |
| `json_cleaner-macos-amd64` | **no** (needs a macOS host or SDK); CI job defined | no | no |
| `json_cleaner-macos-arm64` | **no**; CI job defined | no | no |

The GitHub Actions workflow (`.github/workflows/json_cleaner.yml`) builds and
tests each of the six targets natively and, on manual dispatch, commits them
to `bin/` and tags the release. The workflow has **not** been executed yet
(nothing was pushed), so runner labels and the release job are unverified.
macOS minimum versions are the Rust defaults (10.12 for x86_64, 11.0 for
aarch64); the workflow prints `LC_BUILD_VERSION` so this can be checked on
the first run.

### Property testing

`tests/differential.rs` runs 3 × 3000 proptest cases per `cargo test`
(random bytes 0–300 B, JSONC-like token soup up to ~80 tokens, plus a
subsequence check) and a deterministic sweep over lengths 0–1025 including
15/16/17, 31/32/33, 63/64/65 at 8 buffer offsets. It passed on Windows and
Linux (about 45 s per platform in debug mode). No long libFuzzer campaign was
run: there is no custom SIMD backend, and `memchr` is used through its safe
API.

## Appendix

### Environment

| Item | Value |
|---|---|
| CPU | AMD Ryzen 5 5600X (6 cores / 12 threads), `available_parallelism() = 12` |
| RAM | 32 GiB |
| OS | Windows 11 Pro 10.0.26200, Windows Defender real-time protection on |
| Disk "D:" (repository, main end-to-end runs) | Samsung SSD 870 QVO 1 TB (QLC), SATA, NTFS |
| Disk "C:" (second end-to-end run) | Kingston SA2000M8 500 GB, NVMe, NTFS (system volume) |
| Rust | rustc 1.94.0, cargo 1.94.0 (stable, x86_64-pc-windows-msvc) |
| Node.js (old filter) | v22.20.0, jsonc-parser 3.3.1, glob 11 |
| Regolith | 1.7.0 (Windows and Linux/WSL) |
| Linux (WSL2) | Ubuntu, glibc 2.39, kernel 5.15, cargo 1.91.0 |
| Reference sources | Regolith `eeaf064` (2026-05-14), regolith-library `8f63c8c`, old filter tag `json_cleaner-2.0.2` = `e5a0b32` |
| Release profile | `opt-level=3`, `lto="fat"`, `codegen-units=1`, `panic="abort"`, `strip="symbols"`, no `target-cpu=native` |

### Method details

Micro-benchmarks: the transformation is in place, so every iteration starts
from a fresh copy made in Criterion's setup closure (excluded from the
timing, `BatchSize::LargeInput`). Throughput is relative to the input size.
Values are Criterion's median estimate, single-threaded, machine otherwise
idle.

End-to-end: timed region is the whole process (spawn to exit) measured from
Python with `perf_counter`; every timed run starts from a fresh copy of the
pristine corpus (reset outside the timing); implementations run in rotated
order within each repetition; median and min..max are reported. The tables
were recorded in separate chunks over about two hours; no drift was observed
(for example 10 000 rewrites took 14.2 s and 3 000 rewrites plus 7 000 reads
took 5.3 s, both consistent with 1.4 ms per rewrite and 0.15 ms per read),
but cross-table comparisons should still stay at the "same order of
magnitude" level. Commands:

```sh
cargo bench --bench transform
python bench/e2e.py --rust bin/json_cleaner-windows-amd64.exe --node <old>/json_cleaner.js --work D:/bench_work --warm --corpora 10000x2K,5000x8K,1000x64K,100x1M --dirty 0,0.3,1 --settings comments,minify,schema,schema_minify --threads 1,0 --reps 3
python bench/e2e.py --rust bin/json_cleaner-windows-amd64.exe --work D:/bench_work --warm --corpora 10000x2K,1000x64K,small_50x4K --dirty 1 --settings comments --threads 1,2,4,8,16,0 --reps 3
python bench/e2e.py --rust bin/json_cleaner-windows-amd64.exe --node <old>/json_cleaner.js --work D:/bench_work --warm --real <project>/packs --corpora small_50x4K --reps 5
```

### Micro-benchmarks, all sizes (MiB/s)

Comment removal (`minify: false`):

| corpus | 1 KiB scalar | 1 KiB memchr | 8 KiB scalar | 8 KiB memchr | 64 KiB scalar | 64 KiB memchr | 1 MiB scalar | 1 MiB memchr |
|---|---|---|---|---|---|---|---|---|
| commented | 234 | 466 | 247 | 514 | 238 | 560 | 250 | 486 |
| long_strings | 175 | 6437 | 190 | 21342 | 169 | 26587 | 152 | 7754 |
| minified | 190 | 238 | 186 | 251 | 161 | 243 | 123 | 263 |
| pretty | 173 | 812 | 183 | 921 | 160 | 1002 | 139 | 898 |
| search_unfriendly | 187 | 294 | 183 | 344 | 151 | 356 | 122 | 391 |
| short_tokens | 156 | 259 | 156 | 267 | 141 | 339 | 123 | 353 |
| stringy | 166 | 481 | 175 | 521 | 166 | 581 | 121 | 503 |

Minification (`minify: true`), final table-scan finder:

| corpus | 1 KiB scalar | 1 KiB memchr | 8 KiB scalar | 8 KiB memchr | 64 KiB scalar | 64 KiB memchr | 1 MiB scalar | 1 MiB memchr |
|---|---|---|---|---|---|---|---|---|
| commented | 200 | 417 | 202 | 495 | 203 | 528 | 191 | 511 |
| long_strings | 253 | 5922 | 292 | 14311 | 249 | 14935 | 262 | 6326 |
| minified | 225 | 331 | 253 | 358 | 239 | 371 | 234 | 358 |
| pretty | 311 | 396 | 248 | 431 | 247 | 450 | 233 | 417 |
| search_unfriendly | 283 | 283 | 239 | 308 | 235 | 357 | 159 | 336 |
| short_tokens | 263 | 231 | 266 | 246 | 262 | 247 | 209 | 254 |
| stringy | 220 | 522 | 226 | 597 | 207 | 591 | 164 | 578 |

Minification with the abandoned two-search finder (first attempt, replaced):

| corpus | 1 KiB scalar | 1 KiB memchr | 8 KiB scalar | 8 KiB memchr | 64 KiB scalar | 64 KiB memchr | 1 MiB scalar | 1 MiB memchr |
|---|---|---|---|---|---|---|---|---|
| commented | 286 | 107 | 170 | 138 | 190 | 125 | 166 | 209 |
| minified | 201 | 112 | 172 | 111 | 152 | 126 | 196 | 144 |
| pretty | 250 | 182 | 258 | 144 | 199 | 192 | 256 | 206 |
| search_unfriendly | 237 | 126 | 230 | 138 | 176 | 134 | 223 | 145 |
| short_tokens | 218 | 84 | 244 | 89 | 211 | 86 | 228 | 85 |
| stringy | 104 | 158 | 119 | 218 | 160 | 348 | 198 | 322 |

Root `$schema` removal (comment-free input):

| input | 1 KiB | 8 KiB | 64 KiB | 1 MiB |
|---|---|---|---|---|
| pretty | 387 | 400 | 445 | 390 |
| minified | 368 | 394 | 428 | 416 |

### End-to-end, old vs new, all scenarios (warm, SATA SSD, reps 3)

`first / second` run medians in seconds.

| scenario | rust t=1 | rust auto | node 2.0.2 |
|---|---|---|---|
| 10000x2K dirty=0 comments | 1.80 / 1.87 | 0.77 / 0.71 | 1.67 / 1.76 |
| 10000x2K dirty=0.3 comments | 5.35 / 1.91 | 4.40 / 0.78 | 5.15 / 1.87 |
| 10000x2K dirty=1 (any writing mode) | see thread sweep | see thread sweep | **fails: `EMFILE`** |
| 5000x8K dirty=1 comments | 5.58 / 1.05 | 5.26 / 0.39 | 5.96 / 1.61 |
| 5000x8K dirty=1 minify | 5.37 / 1.28 | 5.24 / 0.41 | 6.39 / 1.90 |
| 5000x8K dirty=1 schema | 5.72 / 1.37 | 5.32 / 0.44 | 8.35 / 3.13 |
| 5000x8K dirty=1 schema_minify | 5.32 / 1.27 | 5.22 / 0.41 | 7.89 / 3.00 |
| 1000x64K dirty=0 comments | 0.35 / 0.23 | 0.13 / 0.13 | 1.41 / 1.35 |
| 1000x64K dirty=0 minify | 1.57 / 0.27 | 1.16 / 0.12 | 3.75 / 1.76 |
| 1000x64K dirty=0 schema | 1.57 / 0.47 | 1.41 / 0.13 | 5.29 / 3.60 |
| 1000x64K dirty=0 schema_minify | 1.58 / 0.30 | 1.34 / 0.16 | 6.59 / 2.95 |
| 1000x64K dirty=0.3 comments | 0.67 / 0.26 | 0.51 / 0.15 | 1.74 / 1.35 |
| 1000x64K dirty=0.3 minify | 1.50 / 0.27 | 1.25 / 0.10 | 3.81 / 1.71 |
| 1000x64K dirty=0.3 schema | 1.42 / 0.36 | 1.42 / 0.13 | 4.82 / 3.73 |
| 1000x64K dirty=0.3 schema_minify | 1.42 / 0.31 | 1.45 / 0.14 | 5.69 / 3.37 |
| 1000x64K dirty=1 comments | 1.27 / 0.30 | 1.49 / 0.10 | 2.58 / 1.31 |
| 1000x64K dirty=1 minify | 1.33 / 0.28 | 1.42 / 0.10 | 3.52 / 1.65 |
| 1000x64K dirty=1 schema | 1.38 / 0.36 | 1.39 / 0.11 | 5.35 / 3.21 |
| 1000x64K dirty=1 schema_minify | 1.47 / 0.30 | 1.49 / 0.10 | 6.26 / 2.88 |
| 100x1M dirty=0 comments | 0.11 / 0.10 | 0.04 / 0.04 | 1.96 / 2.01 |
| 100x1M dirty=0 minify | 0.32 / 0.08 | 0.18 / 0.03 | 4.25 / 3.08 |
| 100x1M dirty=0 schema | 0.33 / 0.22 | 0.18 / 0.07 | 6.59 / 6.22 |
| 100x1M dirty=0 schema_minify | 0.36 / 0.16 | 0.19 / 0.05 | 8.43 / 6.08 |
| 100x1M dirty=0.3 comments | 0.20 / 0.10 | 0.11 / 0.04 | 2.07 / 1.97 |
| 100x1M dirty=0.3 minify | 0.31 / 0.09 | 0.19 / 0.04 | 4.23 / 2.91 |
| 100x1M dirty=0.3 schema | 0.39 / 0.24 | 0.16 / 0.06 | 6.38 / 6.05 |
| 100x1M dirty=0.3 schema_minify | 0.37 / 0.13 | 0.19 / 0.05 | 8.46 / 6.00 |
| 100x1M dirty=1 comments | 0.25 / 0.10 | 0.20 / 0.04 | 2.29 / 1.90 |
| 100x1M dirty=1 minify | 0.36 / 0.15 | 0.16 / 0.05 | 4.30 / 2.93 |
| 100x1M dirty=1 schema | 0.45 / 0.22 | 0.22 / 0.10 | 6.52 / 5.97 |
| 100x1M dirty=1 schema_minify | 0.49 / 0.15 | 0.26 / 0.05 | 8.36 / 5.75 |
| small_50x4K dirty=1 comments (reps 5) | 0.037 / 0.025 | 0.029 / 0.019 | 0.188 / 0.180 |
| small_50x4K dirty=1 minify (reps 5) | 0.036 / 0.026 | 0.030 / 0.018 | 0.210 / 0.194 |
| small_50x4K dirty=1 schema (reps 5) | 0.035 / 0.028 | 0.035 / 0.020 | 0.221 / 0.208 |
| small_50x4K dirty=1 schema_minify (reps 5) | 0.038 / 0.024 | 0.028 / 0.020 | 0.207 / 0.186 |
| real project, comments (reps 5) | 0.016 / 0.016 | 0.020 / 0.020 | 0.155 / 0.150 |
| real project, minify (reps 5) | 0.017 / 0.016 | 0.018 / 0.016 | 0.150 / 0.143 |
| real project, schema (reps 5) | 0.016 / 0.017 | 0.015 / 0.015 | 0.153 / 0.154 |
| real project, schema_minify (reps 5) | 0.018 / 0.016 | 0.017 / 0.016 | 0.154 / 0.151 |

NVMe disk, `1000x64K`, reps 3:

| scenario | rust t=1 | rust auto | node 2.0.2 |
|---|---|---|---|
| dirty=0.3 comments | 0.58 / 0.19 | 0.45 / 0.07 | 1.75 / 1.41 |
| dirty=0.3 schema_minify | 1.56 / 0.23 | 1.46 / 0.09 | 5.95 / 3.49 |
| dirty=1 comments | 1.56 / 0.21 | 1.52 / 0.06 | 2.85 / 1.22 |
| dirty=1 schema_minify | 1.40 / 0.26 | 1.48 / 0.06 | 6.39 / 3.38 |

### End-to-end thread sweeps with spread (median, min..max, seconds)

Warm, SATA SSD, `comments`, dirty=1, reps 3:

| corpus | threads | first run | min..max | second run | min..max |
|---|---|---|---|---|---|
| 10000x2K | 1 | 14.20 | 13.56..14.38 | 3.17 | 2.12..3.28 |
| 10000x2K | 2 | 11.19 | 10.98..11.47 | 1.13 | 1.02..1.17 |
| 10000x2K | 4 | 15.06 | 14.25..15.47 | 0.90 | 0.76..0.92 |
| 10000x2K | 8 | 14.16 | 13.10..14.20 | 0.75 | 0.74..0.76 |
| 10000x2K | 16 | 12.72 | 12.47..12.91 | 0.73 | 0.64..0.74 |
| 10000x2K | auto (8) | 13.11 | 12.99..13.46 | 0.76 | 0.74..0.82 |
| 1000x64K | 1 | 1.33 | 1.29..1.34 | 0.32 | 0.23..0.40 |
| 1000x64K | 2 | 1.14 | 0.74..1.30 | 0.16 | 0.13..0.69 |
| 1000x64K | 4 | 1.44 | 1.43..1.48 | 0.10 | 0.09..0.12 |
| 1000x64K | 8 | 1.29 | 1.23..1.41 | 0.10 | 0.09..0.11 |
| 1000x64K | 16 | 1.31 | 1.29..1.35 | 0.09 | 0.08..0.10 |
| 1000x64K | auto (8) | 1.39 | 1.35..1.39 | 0.09 | 0.09..0.16 |
| small_50x4K | 1 | 0.035 | 0.034..0.074 | 0.024 | 0.024..0.026 |
| small_50x4K | 2 | 0.029 | 0.029..0.029 | 0.017 | 0.017..0.018 |
| small_50x4K | 4 | 0.028 | 0.026..0.028 | 0.018 | 0.018..0.018 |
| small_50x4K | 8 | 0.030 | 0.028..0.039 | 0.019 | 0.018..0.025 |
| small_50x4K | 16 | 0.032 | 0.027..0.046 | 0.019 | 0.017..0.028 |
| small_50x4K | auto (8) | 0.028 | 0.028..0.032 | 0.019 | 0.017..0.019 |

Warm, NVMe, `10000x2K`, `comments`, dirty=1, reps 3:

| threads | first run | min..max | second run | min..max |
|---|---|---|---|---|
| 1 | 14.18 | 13.25..14.82 | 2.15 | 1.43..2.45 |
| 2 | 12.33 | 11.80..12.66 | 0.83 | 0.80..1.14 |
| 4 | 12.32 | 11.23..12.54 | 0.51 | 0.47..0.66 |
| 8 | 14.38 | 14.23..14.57 | 0.35 | 0.28..0.40 |
| auto (8) | 13.54 | 13.11..14.20 | 0.42 | 0.29..0.45 |

Unwarmed (Defender scan inside the timed region), SATA SSD, `comments`,
dirty=1, reps 5, rust only:

| corpus | threads | first run | min..max | second run | min..max |
|---|---|---|---|---|---|
| 10000x2K | 1 | 200.1 | 177.8..204.0 | 3.38 | 3.35..3.54 |
| 10000x2K | 2 | 77.7 | 69.7..82.7 | 1.52 | 1.23..1.66 |
| 10000x2K | 4 | 42.3 | 39.4..44.1 | 1.33 | 1.23..1.74 |
| 10000x2K | 8 | 30.6 | 30.3..33.6 | 1.00 | 0.88..1.06 |
| 10000x2K | 16 | 27.2 | 27.1..27.9 | 0.75 | 0.74..0.85 |
| 10000x2K | auto (8) | 31.6 | 31.2..31.7 | 0.98 | 0.92..1.04 |
| 1000x64K | 1 | 31.7 | 31.5..32.1 | 0.43 | 0.36..0.55 |
| 1000x64K | 2 | 15.1 | 14.2..16.3 | 0.16 | 0.15..0.17 |
| 1000x64K | 4 | 9.0 | 8.4..10.1 | 0.14 | 0.13..0.21 |
| 1000x64K | 8 | 5.7 | 5.2..6.0 | 0.14 | 0.12..0.16 |
| 1000x64K | 16 | 4.3 | 4.0..4.6 | 0.11 | 0.11..0.14 |
| 1000x64K | auto (8) | 5.5 | 5.3..5.6 | 0.12 | 0.11..0.19 |
| small_50x4K | 1 | 0.115 | 0.092..0.697 | 0.041 | 0.030..0.195 |
| small_50x4K | 2 | 0.091 | 0.066..0.118 | 0.026 | 0.021..0.031 |
| small_50x4K | 4 | 0.060 | 0.052..0.079 | 0.026 | 0.023..0.044 |
| small_50x4K | 8 | 0.066 | 0.052..0.087 | 0.034 | 0.020..0.039 |
| small_50x4K | 16 | 0.078 | 0.051..0.099 | 0.032 | 0.030..0.055 |
| small_50x4K | auto (8) | 0.083 | 0.061..0.110 | 0.040 | 0.022..0.043 |

Unwarmed, old filter included, `1000x64K`, dirty=1, `comments`, reps 3:

| implementation | first run | min..max | second run | min..max |
|---|---|---|---|---|
| rust, 1 thread | 17.65 | 17.44..17.67 | 0.264 | 0.249..0.278 |
| rust, auto (8) | 4.81 | 4.46..5.12 | 0.088 | 0.083..0.107 |
| node 2.0.2 | 7.19 | 6.87..7.33 | 1.235 | 1.191..1.332 |
