//! Fixture-driven tests: every file in `tests/fixtures/input` is transformed
//! with all four settings combinations and every backend, and compared
//! byte-for-byte with `tests/fixtures/expected/<combo>/<name>`.
//!
//! The expected outputs for the comments-only combination were produced by the
//! previous Node.js implementation (tag `json_cleaner-2.0.2`) and are identical
//! to it for every fixture except `non_utf8.json`, which the old filter
//! corrupted by decoding the file as UTF-8. See `tools/compare_with_old.py`.

use std::fs;
use std::path::Path;

use json_cleaner::process::{transform, Options};
use json_cleaner::settings::Settings;
use json_cleaner::transform::Backend;

const COMBOS: [(&str, bool, bool); 4] = [
    ("comments", false, false),
    ("minify", false, true),
    ("schema", true, false),
    ("schema_minify", true, true),
];

#[test]
fn fixtures_match_expected_output() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures");
    let mut count = 0;
    for entry in fs::read_dir(root.join("input")).unwrap() {
        let entry = entry.unwrap();
        let name = entry.file_name();
        let input = fs::read(entry.path()).unwrap();
        for (combo, strip_schemas, minify) in COMBOS {
            let expected = fs::read(root.join("expected").join(combo).join(&name)).unwrap();
            for backend in Backend::ALL {
                let mut buf = input.clone();
                let opts = Options {
                    settings: Settings {
                        strip_schemas,
                        minify,
                    },
                    backend,
                };
                let changed = transform(&mut buf, &opts);
                assert!(
                    buf == expected,
                    "{}/{} with {:?}:\n  got      {:?}\n  expected {:?}",
                    combo,
                    name.to_string_lossy(),
                    backend,
                    String::from_utf8_lossy(&buf),
                    String::from_utf8_lossy(&expected)
                );
                assert_eq!(changed, input != expected);
                assert!(buf.len() <= input.len());
            }
        }
        count += 1;
    }
    assert!(count >= 50, "only {count} fixtures found");
}

/// Exact representations of numbers and strings must survive every mode.
#[test]
fn token_representations_are_preserved() {
    let tokens: &[&[u8]] = &[
        b"1.0",
        b"1.00",
        b"1e5",
        b"1e+5",
        b"1E-5",
        b"-0",
        b"0.00000000000000001",
        b"123456789012345678901234567890",
        b"\"\\u0061\"",
        b"\"\\/\\b\\f\\n\\r\\t\\\\\\\"\"",
        b"\"\xc5\xbc\xc3\xb3\xc5\x82w\"",
    ];
    for token in tokens {
        let mut input = Vec::new();
        input.extend_from_slice(b"{\n  \"k\": ");
        input.extend_from_slice(token);
        input.extend_from_slice(b" // c\n}");
        let mut expected = Vec::new();
        expected.extend_from_slice(b"{\"k\":");
        expected.extend_from_slice(token);
        expected.extend_from_slice(b"}");
        for backend in Backend::ALL {
            let mut buf = input.clone();
            transform(
                &mut buf,
                &Options {
                    settings: Settings {
                        strip_schemas: true,
                        minify: true,
                    },
                    backend,
                },
            );
            assert_eq!(buf, expected, "{:?}", String::from_utf8_lossy(token));
        }
    }
}
