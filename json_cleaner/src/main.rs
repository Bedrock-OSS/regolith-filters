//! Command line entry point used by Regolith (`runWith: "exe"`).
//!
//! Usage: `json_cleaner [settings-json]`
//!
//! Regolith passes the filter settings as a single JSON argument (omitted when
//! the settings are empty) and runs the process with the working directory
//! set to the temporary build folder that contains `BP/` and `RP/`.
//!
//! Developer / test overrides (environment variables, not part of the filter
//! settings contract):
//! * `JSON_CLEANER_THREADS=<n>`: number of worker threads (`0` = automatic).
//! * `JSON_CLEANER_BACKEND=scalar|memchr`: scanner implementation.
//! * `JSON_CLEANER_VERBOSE=1`: print a one-line summary on success.

use std::path::PathBuf;
use std::process::ExitCode;

use json_cleaner::process::Options;
use json_cleaner::run::{default_threads, run, RunConfig};
use json_cleaner::settings::Settings;
use json_cleaner::transform::Backend;

const USAGE_ERROR: u8 = 2;
const FILE_ERROR: u8 = 1;

fn main() -> ExitCode {
    let settings = match Settings::parse(std::env::args().nth(1).as_deref()) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("json_cleaner: {e}");
            return ExitCode::from(USAGE_ERROR);
        }
    };
    let backend = match std::env::var("JSON_CLEANER_BACKEND") {
        Ok(name) => match Backend::parse(&name) {
            Some(b) => b,
            None => {
                eprintln!("json_cleaner: unknown JSON_CLEANER_BACKEND {name:?} (expected scalar or memchr)");
                return ExitCode::from(USAGE_ERROR);
            }
        },
        Err(_) => Backend::DEFAULT,
    };
    let threads = match std::env::var("JSON_CLEANER_THREADS") {
        Ok(value) => match value.trim().parse::<usize>() {
            Ok(0) => default_threads(),
            Ok(n) => n,
            Err(_) => {
                eprintln!(
                    "json_cleaner: invalid JSON_CLEANER_THREADS {value:?} (expected a number)"
                );
                return ExitCode::from(USAGE_ERROR);
            }
        },
        Err(_) => default_threads(),
    };

    let cfg = RunConfig {
        opts: Options { settings, backend },
        threads,
        roots: vec![PathBuf::from("BP"), PathBuf::from("RP")],
    };
    let summary = run(&cfg);
    for error in &summary.errors {
        eprintln!("json_cleaner: {error}");
    }
    if !summary.errors.is_empty() {
        eprintln!(
            "json_cleaner: {} error(s), {} file(s) processed",
            summary.errors.len(),
            summary.files
        );
        return ExitCode::from(FILE_ERROR);
    }
    if std::env::var_os("JSON_CLEANER_VERBOSE").is_some() {
        println!(
            "json_cleaner: {} file(s) scanned, {} rewritten, {} thread(s), {:?} backend",
            summary.files, summary.rewritten, threads, backend
        );
    }
    ExitCode::SUCCESS
}
