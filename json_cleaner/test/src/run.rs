//! Directory walk and the worker pool.
//!
//! Files are processed in parallel, one file per task. The walk runs on the
//! calling thread and feeds a channel; a fixed number of worker threads pull
//! paths from it, each with its own reusable buffer. Errors are collected and
//! reported after all workers finished.

use std::io;
use std::path::{Path, PathBuf};
use std::sync::mpsc;
use std::sync::Mutex;
use std::thread;

use walkdir::WalkDir;

use crate::process::{process_file, Options, Outcome};

/// Configuration of one run.
#[derive(Clone, Debug)]
pub struct RunConfig {
    pub opts: Options,
    /// Number of worker threads. `1` processes everything on the calling
    /// thread without spawning.
    pub threads: usize,
    /// Directories to scan recursively. Missing ones are skipped.
    pub roots: Vec<PathBuf>,
}

/// Counters and error messages of one run.
#[derive(Debug, Default)]
pub struct Summary {
    pub files: usize,
    pub rewritten: usize,
    pub errors: Vec<String>,
}

impl Summary {
    fn absorb(&mut self, other: Summary) {
        self.files += other.files;
        self.rewritten += other.rewritten;
        self.errors.extend(other.errors);
    }

    fn record(&mut self, result: Result<Outcome, crate::process::FileError>) {
        self.files += 1;
        match result {
            Ok(Outcome::Rewritten { .. }) => self.rewritten += 1,
            Ok(Outcome::Unchanged) => {}
            Err(e) => self.errors.push(e.to_string()),
        }
    }
}

/// Picks the number of worker threads when the user did not choose one.
///
/// The measurements in `benchmarks.md` showed the gains flattening out well
/// before the core count on the tested machine, while more threads mostly add
/// contention on the filesystem. The cap is deliberately conservative.
pub fn default_threads() -> usize {
    thread::available_parallelism()
        .map_or(1, |n| n.get())
        .clamp(1, 8)
}

/// Returns `true` when `path` has a `.json` extension (ASCII case-insensitive,
/// matching what the previous implementation did on Windows and macOS).
pub fn is_json_file(path: &Path) -> bool {
    path.extension()
        .and_then(|e| e.to_str())
        .is_some_and(|e| e.eq_ignore_ascii_case("json"))
}

/// Walks the configured roots and cleans every regular `.json` file.
pub fn run(cfg: &RunConfig) -> Summary {
    let mut summary = Summary::default();
    if cfg.threads <= 1 {
        let mut buf = Vec::new();
        let walk_errors = walk(cfg, |path| {
            summary.record(process_file(&path, &cfg.opts, &mut buf))
        });
        summary.errors.extend(walk_errors);
        return summary;
    }

    let (tx, rx) = mpsc::channel::<PathBuf>();
    let rx = Mutex::new(rx);
    thread::scope(|scope| {
        let workers: Vec<_> = (0..cfg.threads)
            .map(|_| {
                let rx = &rx;
                let opts = &cfg.opts;
                scope.spawn(move || {
                    let mut local = Summary::default();
                    let mut buf = Vec::new();
                    loop {
                        // Hold the lock only while receiving, not while working.
                        let next = rx.lock().unwrap_or_else(|p| p.into_inner()).recv();
                        match next {
                            Ok(path) => local.record(process_file(&path, opts, &mut buf)),
                            Err(_) => break,
                        }
                    }
                    local
                })
            })
            .collect();
        let walk_errors = walk(cfg, |path| {
            // A send only fails when every worker is gone, which cannot
            // happen while the scope is alive.
            let _ = tx.send(path);
        });
        drop(tx);
        summary.errors.extend(walk_errors);
        for worker in workers {
            match worker.join() {
                Ok(local) => summary.absorb(local),
                Err(_) => summary.errors.push("a worker thread panicked".to_string()),
            }
        }
    });
    summary
}

/// Visits every regular `.json` file below the roots and returns the errors
/// met while walking. Symlinks (including a root that is itself a symlink)
/// are not followed. A missing root is not an error; any other failure to
/// access a root or an entry is reported.
fn walk(cfg: &RunConfig, mut visit: impl FnMut(PathBuf)) -> Vec<String> {
    let mut errors = Vec::new();
    for root in &cfg.roots {
        match std::fs::symlink_metadata(root) {
            Err(e) if e.kind() == io::ErrorKind::NotFound => continue,
            Err(e) => {
                errors.push(format!("{}: stat failed: {}", root.display(), e));
                continue;
            }
            Ok(meta) if !meta.is_dir() => continue,
            Ok(_) => {}
        }
        let walker = WalkDir::new(root)
            .follow_links(false)
            .follow_root_links(false);
        for entry in walker {
            match entry {
                Ok(entry) => {
                    if entry.file_type().is_file() && is_json_file(entry.path()) {
                        visit(entry.into_path());
                    }
                }
                Err(e) => {
                    let path = e.path().map_or_else(|| root.clone(), Path::to_path_buf);
                    errors.push(format!("{}: directory walk failed: {}", path.display(), e));
                }
            }
        }
    }
    errors
}
