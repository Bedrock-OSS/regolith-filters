#!/usr/bin/env python3
"""Differential comparison with the previous Node.js implementation.

Fetches the old filter from this repository at tag `json_cleaner-2.0.2`
(`git archive`), installs its npm dependencies in a scratch directory (Node.js
is required only for this comparison, never for end users), runs both the old
filter and the given Rust binary on `tests/fixtures/input` for all four
settings combinations and prints every fixture whose output differs.

Usage: python tools/compare_with_old.py <path-to-json_cleaner-binary> [scratch-dir]
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CRATE_DIR = os.path.dirname(HERE)  # json_cleaner/test
REPO = os.path.dirname(os.path.dirname(CRATE_DIR))
OLD_TAG = "json_cleaner-2.0.2"
COMBOS = {
    "comments": {},
    "minify": {"minify": True},
    "schema": {"stripSchemas": True},
    "schema_minify": {"stripSchemas": True, "minify": True},
}


def fetch_old(scratch):
    old = os.path.join(scratch, "old")
    if not os.path.isfile(os.path.join(old, "json_cleaner", "json_cleaner.js")):
        os.makedirs(old, exist_ok=True)
        archive = subprocess.run(["git", "archive", OLD_TAG, "json_cleaner"], cwd=REPO, capture_output=True, check=True).stdout
        subprocess.run(["tar", "-x", "-C", old], input=archive, check=True)
        subprocess.run(["npm", "install", "--silent"], cwd=os.path.join(old, "json_cleaner"), check=True, shell=os.name == "nt")
    return os.path.join(old, "json_cleaner", "json_cleaner.js")


def run(cmd, work, settings):
    args = list(cmd) + ([json.dumps(settings)] if settings else [])
    r = subprocess.run(args, cwd=work, capture_output=True)
    if r.returncode != 0:
        raise SystemExit(f"{args} failed: {r.stderr.decode(errors='replace')}")


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    binary = os.path.abspath(sys.argv[1])
    scratch = sys.argv[2] if len(sys.argv) > 2 else os.path.join(tempfile.gettempdir(), "json_cleaner_compare")
    os.makedirs(scratch, exist_ok=True)
    old_js = fetch_old(scratch)
    inputs = os.path.join(CRATE_DIR, "tests", "fixtures", "input")
    differences = 0
    for combo, settings in COMBOS.items():
        outputs = {}
        for name, cmd in (("old", ["node", old_js]), ("new", [binary])):
            work = os.path.join(scratch, f"work_{name}_{combo}")
            shutil.rmtree(work, ignore_errors=True)
            shutil.copytree(inputs, os.path.join(work, "BP"))
            run(cmd, work, settings)
            outputs[name] = {f: open(os.path.join(work, "BP", f), "rb").read() for f in os.listdir(inputs)}
        for f in sorted(outputs["old"]):
            if outputs["old"][f] != outputs["new"][f]:
                differences += 1
                print(f"{combo}/{f}\n  old: {outputs['old'][f][:100]!r}\n  new: {outputs['new'][f][:100]!r}")
    print(f"{differences} differing (combo, fixture) pairs")


if __name__ == "__main__":
    main()
