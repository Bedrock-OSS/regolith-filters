//! Per-file processing: read, transform in memory, and rewrite in place only
//! when something was removed.
//!
//! The file is opened once for reading and writing. Timestamps are read from
//! the open handle before the content is read. When the content changes, the
//! new (shorter) content is written from the start, the file is truncated to
//! the new length and the original modification time (and, when available,
//! access time) is restored on the same handle.
//!
//! Consequences of this design, documented for users:
//! * Unchanged files are never written, truncated or re-timestamped.
//! * The file identity is preserved (no temp file + rename), so a failure in
//!   the middle of the write can leave a partially updated file.
//! * Opening read/write fails on read-only files even when they would not
//!   need any change.
//! * Nothing is fsynced; durability across power loss is not promised.

use std::fmt;
use std::fs::{File, FileTimes, OpenOptions};
use std::io::{self, Read, Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};

use crate::schema::strip_root_schema;
use crate::settings::Settings;
use crate::transform::{clean, Backend};

/// Everything needed to transform one buffer.
#[derive(Clone, Copy, Debug)]
pub struct Options {
    pub settings: Settings,
    pub backend: Backend,
}

/// Applies the configured transformations to `buf` in place and truncates it.
/// Returns `true` when bytes were removed, i.e. when the content changed.
///
/// Every transformation only removes bytes, so a length change is exactly
/// equivalent to a content change.
pub fn transform(buf: &mut Vec<u8>, opts: &Options) -> bool {
    let original_len = buf.len();
    let mut len = clean(buf, opts.settings.minify, opts.backend);
    if opts.settings.strip_schemas {
        len = strip_root_schema(&mut buf[..len]);
    }
    buf.truncate(len);
    buf.len() != original_len
}

/// What happened to a file.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Outcome {
    /// Content was already clean; nothing was written.
    Unchanged,
    /// Content was rewritten; `removed` bytes were dropped.
    Rewritten { removed: usize },
}

/// A failed file operation, with the path and the operation for the message.
#[derive(Debug)]
pub struct FileError {
    pub path: PathBuf,
    pub op: &'static str,
    pub source: io::Error,
}

impl fmt::Display for FileError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "{}: {} failed: {}",
            self.path.display(),
            self.op,
            self.source
        )
    }
}

impl std::error::Error for FileError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        Some(&self.source)
    }
}

/// Cleans a single file. `buf` is a reusable scratch buffer; its previous
/// content is discarded.
pub fn process_file(path: &Path, opts: &Options, buf: &mut Vec<u8>) -> Result<Outcome, FileError> {
    let err = |op: &'static str, source: io::Error| FileError {
        path: path.to_path_buf(),
        op,
        source,
    };
    let mut file = OpenOptions::new()
        .read(true)
        .write(true)
        .open(path)
        .map_err(|e| err("open", e))?;
    let meta = file.metadata().map_err(|e| err("metadata", e))?;
    let mtime = meta
        .modified()
        .map_err(|e| err("read modification time", e))?;
    // The access time is optional: not every platform/filesystem reports it.
    let atime = meta.accessed().ok();

    buf.clear();
    buf.reserve(meta.len() as usize);
    file.read_to_end(buf).map_err(|e| err("read", e))?;

    let original_len = buf.len();
    if !transform(buf, opts) {
        return Ok(Outcome::Unchanged);
    }
    rewrite(&mut file, buf, mtime, atime).map_err(|(op, e)| err(op, e))?;
    Ok(Outcome::Rewritten {
        removed: original_len - buf.len(),
    })
}

/// Overwrites the open file with `content`, truncates it and restores the
/// timestamps. `content` must not be longer than the current file.
fn rewrite(
    file: &mut File,
    content: &[u8],
    mtime: std::time::SystemTime,
    atime: Option<std::time::SystemTime>,
) -> Result<(), (&'static str, io::Error)> {
    file.seek(SeekFrom::Start(0)).map_err(|e| ("seek", e))?;
    file.write_all(content).map_err(|e| ("write", e))?;
    file.set_len(content.len() as u64)
        .map_err(|e| ("truncate", e))?;
    let mut times = FileTimes::new().set_modified(mtime);
    if let Some(atime) = atime {
        times = times.set_accessed(atime);
    }
    file.set_times(times)
        .map_err(|e| ("restore timestamps", e))?;
    Ok(())
}
