// Tests restore permissions they changed; the lint suggests a different API.
#![allow(clippy::permissions_set_readonly_false)]

//! Filesystem behaviour: exact timestamp preservation for rewritten files,
//! no write at all for unchanged files, error reporting and directory walking.

use std::fs::{self, File, FileTimes};
use std::path::{Path, PathBuf};
use std::time::{Duration, SystemTime};

use json_cleaner::process::{process_file, Options, Outcome};
use json_cleaner::run::{run, RunConfig};
use json_cleaner::settings::Settings;
use json_cleaner::transform::Backend;

fn opts(strip_schemas: bool, minify: bool) -> Options {
    Options {
        settings: Settings {
            strip_schemas,
            minify,
        },
        backend: Backend::DEFAULT,
    }
}

/// Creates a file with the given content and an artificial, odd timestamp
/// (well in the past, with a sub-second part) so that a lost timestamp is
/// impossible to miss. Returns the timestamps as the filesystem stored them.
fn create(path: &Path, content: &[u8]) -> (SystemTime, SystemTime) {
    fs::write(path, content).unwrap();
    let mtime = SystemTime::UNIX_EPOCH + Duration::new(1_600_000_000, 123_456_789);
    let atime = SystemTime::UNIX_EPOCH + Duration::new(1_500_000_000, 987_654_321);
    let file = File::options().write(true).open(path).unwrap();
    file.set_times(FileTimes::new().set_modified(mtime).set_accessed(atime))
        .unwrap();
    drop(file);
    let meta = fs::metadata(path).unwrap();
    (meta.modified().unwrap(), meta.accessed().unwrap())
}

fn temp_dir() -> tempfile::TempDir {
    tempfile::tempdir().unwrap()
}

#[test]
fn rewritten_files_keep_exact_timestamps() {
    let cases: [(&str, Options, &[u8], &[u8]); 4] = [
        (
            "comments",
            opts(false, false),
            b"{\n // c\n \"a\": 1\n}",
            b"{\n \n \"a\": 1\n}",
        ),
        (
            "minify",
            opts(false, true),
            b"{\n \"a\": 1 // c\n}\n",
            b"{\"a\":1}",
        ),
        (
            "schema",
            opts(true, false),
            b"{\"$schema\": \"x\", \"a\": 1}",
            b"{\"a\": 1}",
        ),
        (
            "all",
            opts(true, true),
            b"{ // c\n \"$schema\": \"x\",\n \"a\": 1.50\n}",
            b"{\"a\":1.50}",
        ),
    ];
    let dir = temp_dir();
    for (name, o, input, expected) in cases {
        let path = dir.path().join(format!("{name}.json"));
        let (mtime, atime) = create(&path, input);
        // Make sure the artificial timestamp is not "now".
        assert!(SystemTime::now().duration_since(mtime).unwrap() > Duration::from_secs(3600));

        let mut buf = Vec::new();
        let outcome = process_file(&path, &o, &mut buf).unwrap();
        assert_eq!(
            outcome,
            Outcome::Rewritten {
                removed: input.len() - expected.len()
            }
        );

        // Check the timestamps before reading the content back: the read
        // itself may update atime (NTFS with last-access updates, relatime).
        let meta = fs::metadata(&path).unwrap();
        assert_eq!(meta.len(), expected.len() as u64);
        assert_eq!(meta.modified().unwrap(), mtime, "{name}: mtime changed");
        assert_eq!(meta.accessed().unwrap(), atime, "{name}: atime changed");
        assert_eq!(fs::read(&path).unwrap(), expected, "{name}");
    }
}

#[test]
fn unchanged_files_are_not_written() {
    let dir = temp_dir();
    let inputs: [(&str, Options, &[u8]); 4] = [
        ("clean", opts(false, false), b"{\n  \"a\": 1\n}\n"),
        ("minified", opts(false, true), b"{\"a\":1}"),
        ("noschema", opts(true, true), b"{\"a\":{\"$schema\":1}}"),
        ("empty", opts(true, true), b""),
    ];
    for (name, o, input) in inputs {
        let path = dir.path().join(format!("{name}.json"));
        let (mtime, _atime) = create(&path, input);
        #[cfg(unix)]
        let ctime_before = {
            use std::os::unix::fs::MetadataExt;
            let m = fs::metadata(&path).unwrap();
            (m.ctime(), m.ctime_nsec())
        };
        // Give a possible (wrong) write a chance to produce a different ctime.
        std::thread::sleep(Duration::from_millis(20));

        let mut buf = Vec::new();
        let outcome = process_file(&path, &o, &mut buf).unwrap();
        assert_eq!(outcome, Outcome::Unchanged, "{name}");
        assert_eq!(fs::read(&path).unwrap(), input);
        let meta = fs::metadata(&path).unwrap();
        assert_eq!(meta.modified().unwrap(), mtime, "{name}");
        // On Unix any write, truncation or timestamp update bumps ctime,
        // which cannot be set from user space: an unchanged ctime proves that
        // no such operation happened, not merely that mtime was restored.
        #[cfg(unix)]
        {
            use std::os::unix::fs::MetadataExt;
            assert_eq!(
                (meta.ctime(), meta.ctime_nsec()),
                ctime_before,
                "{name}: file was touched"
            );
        }
    }
}

#[test]
fn read_only_file_is_an_error_with_path_and_operation() {
    let dir = temp_dir();
    let path = dir.path().join("ro.json");
    create(&path, b"{}");
    let mut perms = fs::metadata(&path).unwrap().permissions();
    perms.set_readonly(true);
    fs::set_permissions(&path, perms).unwrap();
    #[cfg(unix)]
    if unsafe_is_root() {
        return; // root ignores permission bits
    }

    let mut buf = Vec::new();
    let err = process_file(&path, &opts(false, false), &mut buf).unwrap_err();
    assert_eq!(err.op, "open");
    assert_eq!(err.path, path);
    let msg = err.to_string();
    assert!(msg.contains("ro.json") && msg.contains("open"), "{msg}");

    let mut perms = fs::metadata(&path).unwrap().permissions();
    perms.set_readonly(false);
    fs::set_permissions(&path, perms).unwrap();
}

#[cfg(unix)]
fn unsafe_is_root() -> bool {
    use std::os::unix::fs::MetadataExt;
    fs::metadata("/proc/self")
        .map(|m| m.uid() == 0)
        .unwrap_or(false)
}

#[test]
fn errors_are_collected_and_reported_by_run() {
    let dir = temp_dir();
    let bp = dir.path().join("BP");
    fs::create_dir(&bp).unwrap();
    create(&bp.join("ok.json"), b"{}// c");
    let ro = bp.join("ro.json");
    create(&ro, b"{}// c");
    let mut perms = fs::metadata(&ro).unwrap().permissions();
    perms.set_readonly(true);
    fs::set_permissions(&ro, perms).unwrap();
    #[cfg(unix)]
    if unsafe_is_root() {
        return;
    }

    for threads in [1, 4] {
        let summary = run(&RunConfig {
            opts: opts(false, false),
            threads,
            roots: vec![bp.clone()],
        });
        assert_eq!(summary.files, 2);
        assert_eq!(summary.errors.len(), 1, "{:?}", summary.errors);
        assert!(summary.errors[0].contains("ro.json"));
        assert!(summary.errors[0].contains("open"));
    }
    assert_eq!(fs::read(bp.join("ok.json")).unwrap(), b"{}");
    let mut perms = fs::metadata(&ro).unwrap().permissions();
    perms.set_readonly(false);
    fs::set_permissions(&ro, perms).unwrap();
}

#[test]
fn walk_selects_json_files_recursively_and_skips_missing_roots() {
    let dir = temp_dir();
    let bp = dir.path().join("BP");
    fs::create_dir_all(bp.join("entities/deep")).unwrap();
    create(&bp.join("a.json"), b"1// c");
    create(&bp.join("entities/b.json"), b"2// c");
    create(&bp.join("entities/deep/c.JSON"), b"3// c");
    create(&bp.join("entities/deep/d.jsonc"), b"4// c");
    create(&bp.join("entities/notes.txt"), b"5// c");
    create(&bp.join("entities/json"), b"6// c");
    // A directory whose name ends with .json is not a file.
    fs::create_dir(bp.join("dir.json")).unwrap();
    // RP does not exist; data is not scanned at all.
    let data = dir.path().join("data");
    fs::create_dir(&data).unwrap();
    create(&data.join("e.json"), b"7// c");

    for threads in [1, 3] {
        let summary = run(&RunConfig {
            opts: opts(false, false),
            threads,
            roots: vec![bp.clone(), dir.path().join("RP")],
        });
        assert!(summary.errors.is_empty(), "{:?}", summary.errors);
        assert_eq!(summary.files, 3);
    }
    assert_eq!(fs::read(bp.join("a.json")).unwrap(), b"1");
    assert_eq!(fs::read(bp.join("entities/b.json")).unwrap(), b"2");
    assert_eq!(fs::read(bp.join("entities/deep/c.JSON")).unwrap(), b"3");
    assert_eq!(
        fs::read(bp.join("entities/deep/d.jsonc")).unwrap(),
        b"4// c"
    );
    assert_eq!(fs::read(bp.join("entities/notes.txt")).unwrap(), b"5// c");
    assert_eq!(fs::read(bp.join("entities/json")).unwrap(), b"6// c");
    assert_eq!(fs::read(data.join("e.json")).unwrap(), b"7// c");
}

#[test]
fn root_that_is_a_file_is_skipped() {
    let dir = temp_dir();
    let bp = dir.path().join("BP");
    create(&bp, b"{}// c");
    let summary = run(&RunConfig {
        opts: opts(false, false),
        threads: 2,
        roots: vec![bp.clone()],
    });
    assert!(summary.errors.is_empty());
    assert_eq!(summary.files, 0);
    assert_eq!(fs::read(&bp).unwrap(), b"{}// c");
}

fn try_symlink_dir(target: &Path, link: &Path) -> bool {
    #[cfg(unix)]
    {
        std::os::unix::fs::symlink(target, link).is_ok()
    }
    #[cfg(windows)]
    {
        std::os::windows::fs::symlink_dir(target, link).is_ok()
    }
}

fn try_symlink_file(target: &Path, link: &Path) -> bool {
    #[cfg(unix)]
    {
        std::os::unix::fs::symlink(target, link).is_ok()
    }
    #[cfg(windows)]
    {
        std::os::windows::fs::symlink_file(target, link).is_ok()
    }
}

#[test]
fn symlinks_are_not_followed() {
    let dir = temp_dir();
    let real = dir.path().join("real");
    fs::create_dir_all(real.join("sub")).unwrap();
    create(&real.join("sub/x.json"), b"1// c");
    create(&real.join("y.json"), b"2// c");
    let bp = dir.path().join("BP");
    fs::create_dir(&bp).unwrap();
    create(&bp.join("z.json"), b"3// c");
    if !try_symlink_dir(&real.join("sub"), &bp.join("linked_dir"))
        || !try_symlink_file(&real.join("y.json"), &bp.join("linked.json"))
        || !try_symlink_dir(&real, &dir.path().join("RP"))
    {
        eprintln!("skipping: cannot create symlinks here");
        return;
    }
    let summary = run(&RunConfig {
        opts: opts(false, false),
        threads: 2,
        roots: vec![bp.clone(), dir.path().join("RP")],
    });
    assert!(summary.errors.is_empty(), "{:?}", summary.errors);
    assert_eq!(summary.files, 1);
    assert_eq!(fs::read(bp.join("z.json")).unwrap(), b"3");
    assert_eq!(fs::read(real.join("sub/x.json")).unwrap(), b"1// c");
    assert_eq!(fs::read(real.join("y.json")).unwrap(), b"2// c");
}

#[test]
fn many_files_in_parallel_match_sequential() {
    // Same corpus processed with 1 and 8 threads must end up identical, with
    // timestamps preserved everywhere.
    let make = |root: &Path| -> Vec<(PathBuf, SystemTime)> {
        let mut files = Vec::new();
        for i in 0..300 {
            let sub = root.join(format!("d{}", i % 7));
            fs::create_dir_all(&sub).unwrap();
            let path = sub.join(format!("f{i}.json"));
            let content = format!(
                "{{\n  // file {i}\n  \"$schema\": \"s\",\n  \"i\": {i}, /* x */ \"s\": \"a//b\"\n}}\n"
            );
            let (mtime, _) = create(&path, content.as_bytes());
            files.push((path, mtime));
        }
        files
    };
    let dir = temp_dir();
    let a = dir.path().join("A");
    let b = dir.path().join("B");
    let fa = make(&a);
    let fb = make(&b);
    for (root, threads) in [(&a, 1), (&b, 8)] {
        let summary = run(&RunConfig {
            opts: opts(true, true),
            threads,
            roots: vec![root.clone()],
        });
        assert!(summary.errors.is_empty());
        assert_eq!(summary.files, 300);
        assert_eq!(summary.rewritten, 300);
    }
    for ((pa, ta), (pb, tb)) in fa.iter().zip(&fb) {
        let ca = fs::read(pa).unwrap();
        assert_eq!(ca, fs::read(pb).unwrap());
        assert!(ca.starts_with(b"{\"i\":"));
        assert_eq!(fs::metadata(pa).unwrap().modified().unwrap(), *ta);
        assert_eq!(fs::metadata(pb).unwrap().modified().unwrap(), *tb);
    }
}
