//! Native replacement for the `json_cleaner` Regolith filter.
//!
//! The library exposes the pieces that the binary, the tests and the
//! benchmarks share: the lexical transformation ([`transform`]), the root
//! `$schema` remover ([`schema`]), per-file I/O ([`process`]), settings parsing
//! ([`settings`]) and the directory walk with the worker pool ([`run`]).

#![forbid(unsafe_code)]

pub mod process;
pub mod run;
pub mod schema;
pub mod settings;
pub mod transform;
