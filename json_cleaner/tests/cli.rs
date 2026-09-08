// Tests restore permissions they changed; the lint suggests a different API.
#![allow(clippy::permissions_set_readonly_false)]

//! End-to-end tests of the binary as Regolith runs it: working directory with
//! `BP/` and `RP/`, settings as a single JSON argument, exit codes.

use std::fs;
use std::path::Path;
use std::process::Command;

fn bin() -> Command {
    let mut cmd = Command::new(env!("CARGO_BIN_EXE_json_cleaner"));
    cmd.env_remove("JSON_CLEANER_THREADS")
        .env_remove("JSON_CLEANER_BACKEND")
        .env_remove("JSON_CLEANER_VERBOSE");
    cmd
}

fn project(dir: &Path) {
    fs::create_dir_all(dir.join("BP/entities")).unwrap();
    fs::create_dir_all(dir.join("RP")).unwrap();
    fs::create_dir_all(dir.join("data")).unwrap();
    fs::write(
        dir.join("BP/entities/a.json"),
        b"{\n  \"$schema\": \"x\", // c\n  \"a\": 1.0\n}\n",
    )
    .unwrap();
    fs::write(dir.join("RP/b.json"), b"[1, /* c */ 2]").unwrap();
    fs::write(dir.join("data/c.json"), b"[1, /* c */ 2]").unwrap();
}

#[test]
fn runs_without_settings_argument() {
    let dir = tempfile::tempdir().unwrap();
    project(dir.path());
    let out = bin().current_dir(dir.path()).output().unwrap();
    assert!(
        out.status.success(),
        "{}",
        String::from_utf8_lossy(&out.stderr)
    );
    assert!(out.stdout.is_empty(), "no per-file logging expected");
    assert_eq!(
        fs::read(dir.path().join("BP/entities/a.json")).unwrap(),
        b"{\n  \"$schema\": \"x\", \n  \"a\": 1.0\n}\n"
    );
    assert_eq!(fs::read(dir.path().join("RP/b.json")).unwrap(), b"[1,  2]");
    assert_eq!(
        fs::read(dir.path().join("data/c.json")).unwrap(),
        b"[1, /* c */ 2]"
    );
}

#[test]
fn applies_settings_from_the_json_argument() {
    let dir = tempfile::tempdir().unwrap();
    project(dir.path());
    let out = bin()
        .arg(r#"{"stripSchemas":true,"minify":true}"#)
        .current_dir(dir.path())
        .output()
        .unwrap();
    assert!(
        out.status.success(),
        "{}",
        String::from_utf8_lossy(&out.stderr)
    );
    assert_eq!(
        fs::read(dir.path().join("BP/entities/a.json")).unwrap(),
        b"{\"a\":1.0}"
    );
    assert_eq!(fs::read(dir.path().join("RP/b.json")).unwrap(), b"[1,2]");
}

#[test]
fn works_with_only_one_pack_and_with_no_packs() {
    let dir = tempfile::tempdir().unwrap();
    fs::create_dir_all(dir.path().join("RP")).unwrap();
    fs::write(dir.path().join("RP/b.json"), b"1//c").unwrap();
    let out = bin().current_dir(dir.path()).output().unwrap();
    assert!(
        out.status.success(),
        "{}",
        String::from_utf8_lossy(&out.stderr)
    );
    assert_eq!(fs::read(dir.path().join("RP/b.json")).unwrap(), b"1");

    let empty = tempfile::tempdir().unwrap();
    let out = bin().current_dir(empty.path()).output().unwrap();
    assert!(
        out.status.success(),
        "{}",
        String::from_utf8_lossy(&out.stderr)
    );
}

#[test]
fn invalid_settings_fail_before_touching_files() {
    let bad = [
        "{",
        "null",
        "[]",
        "42",
        r#"{"minify":"true"}"#,
        r#"{"stripSchemas":1}"#,
        r#"{"minify":null}"#,
    ];
    for arg in bad {
        let dir = tempfile::tempdir().unwrap();
        project(dir.path());
        let out = bin().arg(arg).current_dir(dir.path()).output().unwrap();
        assert_eq!(out.status.code(), Some(2), "{arg}");
        let stderr = String::from_utf8_lossy(&out.stderr);
        assert!(stderr.contains("settings"), "{arg}: {stderr}");
        assert_eq!(
            fs::read(dir.path().join("RP/b.json")).unwrap(),
            b"[1, /* c */ 2]",
            "{arg}: file was modified"
        );
    }
}

#[test]
fn unknown_settings_are_ignored_and_extra_arguments_do_not_matter() {
    let dir = tempfile::tempdir().unwrap();
    project(dir.path());
    let out = bin()
        .arg(r#"{"minify":true,"unknownOption":[1,2]}"#)
        .arg("extra")
        .current_dir(dir.path())
        .output()
        .unwrap();
    assert!(
        out.status.success(),
        "{}",
        String::from_utf8_lossy(&out.stderr)
    );
    assert_eq!(fs::read(dir.path().join("RP/b.json")).unwrap(), b"[1,2]");
}

#[test]
fn developer_overrides() {
    for (backend, threads) in [("scalar", "1"), ("memchr", "3"), ("scalar", "0")] {
        let dir = tempfile::tempdir().unwrap();
        project(dir.path());
        let out = bin()
            .env("JSON_CLEANER_BACKEND", backend)
            .env("JSON_CLEANER_THREADS", threads)
            .env("JSON_CLEANER_VERBOSE", "1")
            .current_dir(dir.path())
            .output()
            .unwrap();
        assert!(
            out.status.success(),
            "{}",
            String::from_utf8_lossy(&out.stderr)
        );
        let stdout = String::from_utf8_lossy(&out.stdout);
        assert!(
            stdout.contains("2 file(s) scanned, 2 rewritten"),
            "{stdout}"
        );
        assert_eq!(fs::read(dir.path().join("RP/b.json")).unwrap(), b"[1,  2]");
    }
    let dir = tempfile::tempdir().unwrap();
    project(dir.path());
    let out = bin()
        .env("JSON_CLEANER_BACKEND", "avx512")
        .current_dir(dir.path())
        .output()
        .unwrap();
    assert_eq!(out.status.code(), Some(2));
    let out = bin()
        .env("JSON_CLEANER_THREADS", "many")
        .current_dir(dir.path())
        .output()
        .unwrap();
    assert_eq!(out.status.code(), Some(2));
    assert_eq!(
        fs::read(dir.path().join("RP/b.json")).unwrap(),
        b"[1, /* c */ 2]"
    );
}

#[test]
fn file_errors_give_nonzero_exit_and_name_the_file() {
    let dir = tempfile::tempdir().unwrap();
    project(dir.path());
    let ro = dir.path().join("RP/b.json");
    let mut perms = fs::metadata(&ro).unwrap().permissions();
    perms.set_readonly(true);
    fs::set_permissions(&ro, perms).unwrap();
    let out = bin().current_dir(dir.path()).output().unwrap();
    let stderr = String::from_utf8_lossy(&out.stderr);
    let mut perms = fs::metadata(&ro).unwrap().permissions();
    perms.set_readonly(false);
    fs::set_permissions(&ro, perms).unwrap();
    if cfg!(unix) && out.status.success() {
        // Running as root: permission bits are not enforced.
        return;
    }
    assert_eq!(out.status.code(), Some(1), "{stderr}");
    assert!(
        stderr.contains("b.json") && stderr.contains("open"),
        "{stderr}"
    );
    // The other file is still processed.
    assert_eq!(
        fs::read(dir.path().join("BP/entities/a.json")).unwrap(),
        b"{\n  \"$schema\": \"x\", \n  \"a\": 1.0\n}\n"
    );
}
