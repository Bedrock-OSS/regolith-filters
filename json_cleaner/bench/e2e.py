#!/usr/bin/env python3
"""End-to-end benchmark of json_cleaner implementations on synthetic (and
optionally real) Bedrock-like corpora.

Method
------
* A pristine corpus is generated once per scenario. Before every timed run the
  working copy is deleted and recreated from the pristine copy (outside the
  timed region), so every run starts from identical content.
* The reset writes every file, so the page cache is warm when the run starts.
  This is *not* a cold-cache measurement and is not labelled as one. With
  `--warm` every file is additionally opened and read once after the reset,
  which takes the antivirus on-access scan of new files out of the timed
  region (Windows); without it the first run measures mostly that scan.
* The timed region is the whole process (spawn to exit), measured with
  `time.perf_counter()` around `subprocess.run`. This is the user-visible
  filter time, including process start-up.
* Every (scenario, implementation) pair is repeated `--reps` times. Within a
  repetition the implementations run in rotated order to limit ordering
  effects. Median and min/max are reported.
* "second run" is a separate measurement on a corpus that was already cleaned
  by the same implementation (0% of files need a write).

Usage (see README):
  python bench/e2e.py --rust target/release/json_cleaner.exe \
      --node ../old/json_cleaner/json_cleaner.js --work D:/bench_work \
      --threads 1,2,4,8,16,0 --settings comments,minify,schema_minify --reps 5
"""
import argparse
import json
import os
import platform
import random
import shutil
import statistics
import subprocess
import sys
import time

SETTINGS = {
    "comments": {},
    "minify": {"minify": True},
    "schema": {"stripSchemas": True},
    "schema_minify": {"stripSchemas": True, "minify": True},
}

# name -> (file count, approximate size per file in bytes)
CORPORA = {
    "10000x2K": (10000, 2 << 10),
    "5000x8K": (5000, 8 << 10),
    "1000x64K": (1000, 64 << 10),
    "100x1M": (100, 1 << 20),
    "small_50x4K": (50, 4 << 10),
}


def gen_file(rng, size, dirty, minified):
    """Bedrock-like entity JSON. `dirty` adds comments (so the comments-only
    mode has to rewrite the file); `minified` produces a single line with no
    whitespace (so only dirty files change in any mode)."""
    parts = []
    i = 0
    if minified:
        parts.append('{"$schema":"https://example.com/entity.json","format_version":"1.20.80","minecraft:entity":{')
        while sum(len(p) for p in parts) < size:
            c = "" if not dirty or i % 5 else "/*c*/"
            parts.append(f'"minecraft:component_{i}":{{"value":{rng.randint(0, 999)}.5,{c}"id":"ns:thing_{i}","list":[1,2,3],"on":true}},')
            i += 1
        parts.append('"end":0}}')
        return "".join(parts)
    parts.append('{\n    "$schema": "https://example.com/entity.json",\n')
    if dirty:
        parts.append("    // generated entity\n")
    parts.append('    "format_version": "1.20.80",\n    "minecraft:entity": {\n')
    while sum(len(p) for p in parts) < size:
        c = ""
        if dirty and i % 4 == 0:
            c = " // component comment"
        elif dirty and i % 4 == 1:
            c = " /* block */"
        parts.append(
            f'        "minecraft:component_{i}": {{{c}\n'
            f'            "value": {rng.randint(0, 999)}.5,\n'
            f'            "identifier": "namespace:thing_{i}",\n'
            f'            "list": [1, 2, 3, 4],\n'
            f'            "enabled": true\n'
            f"        }},\n"
        )
        i += 1
    parts.append('        "end": 0\n    }\n}\n')
    return "".join(parts)


def make_corpus(root, count, size, dirty_fraction, minified, seed=1):
    rng = random.Random(seed)
    bp = os.path.join(root, "BP")
    rp = os.path.join(root, "RP")
    for d in (bp, rp):
        os.makedirs(d, exist_ok=True)
    dirty_count = int(round(count * dirty_fraction))
    for n in range(count):
        base = bp if n % 2 == 0 else rp
        sub = os.path.join(base, f"entities/group{n % 17}")
        os.makedirs(sub, exist_ok=True)
        dirty = n < dirty_count
        with open(os.path.join(sub, f"entity_{n}.json"), "w", encoding="utf-8", newline="") as f:
            f.write(gen_file(rng, size, dirty, minified))


def reset(work, pristine, warm):
    if os.path.isdir(work):
        shutil.rmtree(work)
    shutil.copytree(pristine, work)
    if warm:
        # Open and read every file once. On Windows with real-time antivirus
        # protection the *first* open of a freshly created file costs tens of
        # milliseconds (an on-access scan) regardless of what the program then
        # does with it; without this step that scan, not the filter, dominates
        # the first run. See benchmarks.md.
        # The scan is parallelizable, so use a thread pool.
        from concurrent.futures import ThreadPoolExecutor

        def read(path):
            with open(path, "rb") as fh:
                fh.read()

        paths = [os.path.join(base, f) for base, _dirs, files in os.walk(work) for f in files]
        with ThreadPoolExecutor(16) as pool:
            list(pool.map(read, paths))


def run_impl(impl, work, settings, env):
    args = list(impl["cmd"])
    if settings:
        args.append(json.dumps(settings))
    t0 = time.perf_counter()
    r = subprocess.run(args, cwd=work, capture_output=True, env=env)
    dt = time.perf_counter() - t0
    if r.returncode != 0:
        raise RuntimeError(f"{impl['name']} failed ({r.returncode}): {r.stderr.decode(errors='replace')[:500]}")
    return dt


def corpus_signature(root):
    """Hash of every file's content, to check all implementations agree."""
    import hashlib
    h = hashlib.sha256()
    for base, _dirs, files in sorted(os.walk(root)):
        for f in sorted(files):
            p = os.path.join(base, f)
            h.update(os.path.relpath(p, root).encode())
            with open(p, "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rust", required=True, help="path to the Rust binary")
    ap.add_argument("--node", help="path to the old json_cleaner.js (with node_modules installed)")
    ap.add_argument("--work", required=True, help="scratch directory (on the disk you want to measure)")
    ap.add_argument("--corpora", default="10000x2K,5000x8K,1000x64K,100x1M,small_50x4K")
    ap.add_argument("--real", help="directory containing BP/ and RP/ of a real project (content is not copied anywhere else)")
    ap.add_argument("--settings", default="comments,minify,schema_minify")
    ap.add_argument("--dirty", default="0,0.3,1", help="fractions of files containing comments")
    ap.add_argument("--threads", default="1,0", help="JSON_CLEANER_THREADS values for the Rust binary (0 = auto)")
    ap.add_argument("--backends", default="memchr")
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--warm", action="store_true", help="open+read every file once after each reset, outside the timed region (see reset())")
    ap.add_argument("--json", help="write raw results here")
    a = ap.parse_args()

    impls = []
    for t in a.threads.split(","):
        for b in a.backends.split(","):
            impls.append({"name": f"rust t={t} {b}", "cmd": [a.rust],
                          "env": {"JSON_CLEANER_THREADS": t, "JSON_CLEANER_BACKEND": b}})
    if a.node:
        impls.append({"name": "node 2.0.2", "cmd": ["node", a.node], "env": {}})

    os.makedirs(a.work, exist_ok=True)
    results = []
    scenarios = []
    for corpus in a.corpora.split(","):
        count, size = CORPORA[corpus]
        for dirty in [float(x) for x in a.dirty.split(",")]:
            scenarios.append((corpus, count, size, dirty, False))
    if a.real:
        scenarios.append(("real", None, None, None, None))

    print(f"# {platform.platform()} | {platform.processor()} | python {platform.python_version()}")
    print(f"# cpus={os.cpu_count()} work={os.path.abspath(a.work)} reps={a.reps} warm={a.warm}")
    for corpus, count, size, dirty, minified in scenarios:
        pristine = os.path.join(a.work, f"pristine_{corpus}_{dirty}")
        work = os.path.join(a.work, "work")
        if corpus == "real":
            if os.path.isdir(pristine):
                shutil.rmtree(pristine)
            os.makedirs(pristine)
            for d in ("BP", "RP"):
                src = os.path.join(a.real, d)
                if os.path.isdir(src):
                    shutil.copytree(src, os.path.join(pristine, d))
        elif not os.path.isdir(pristine):
            make_corpus(pristine, count, size, dirty, minified)
        for setting_name in a.settings.split(","):
            settings = SETTINGS[setting_name]
            label = f"{corpus} dirty={dirty} {setting_name}"
            timings = {impl["name"]: {"first": [], "second": []} for impl in impls}
            signatures = {}
            for rep in range(a.reps):
                order = impls[rep % len(impls):] + impls[:rep % len(impls)]
                for impl in order:
                    env = dict(os.environ, **impl["env"])
                    reset(work, pristine, a.warm)
                    first = run_impl(impl, work, settings, env)
                    if rep == 0:
                        signatures[impl["name"]] = corpus_signature(work)
                    second = run_impl(impl, work, settings, env)
                    timings[impl["name"]]["first"].append(first)
                    timings[impl["name"]]["second"].append(second)
            print(f"\n## {label}")
            print("| implementation | first run median (s) | min..max | second run median (s) | min..max |")
            print("|---|---|---|---|---|")
            for impl in impls:
                t = timings[impl["name"]]
                f, s = t["first"], t["second"]
                print(f"| {impl['name']} | {statistics.median(f):.3f} | {min(f):.3f}..{max(f):.3f} | "
                      f"{statistics.median(s):.3f} | {min(s):.3f}..{max(s):.3f} |")
                results.append({"scenario": label, "impl": impl["name"], "first": f, "second": s,
                                "signature": signatures[impl["name"]]})
            sigs = set(signatures.values())
            note = "identical" if len(sigs) == 1 else f"DIFFERENT ({signatures})"
            print(f"output of all implementations: {note}")
            sys.stdout.flush()
    if a.json:
        with open(a.json, "w") as f:
            json.dump(results, f, indent=1)


if __name__ == "__main__":
    main()
