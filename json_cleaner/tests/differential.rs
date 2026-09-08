//! Differential tests: every backend must produce exactly the same bytes as
//! the scalar reference for the same input and settings, for arbitrary bytes
//! (not only valid JSON), and the result must never be longer than the input.

use json_cleaner::process::{transform, Options};
use json_cleaner::settings::Settings;
use json_cleaner::transform::{clean, Backend};
use proptest::prelude::*;

/// Runs the full transformation with every backend and checks that they agree.
fn check_all_backends(input: &[u8], minify: bool, strip_schemas: bool) -> Vec<u8> {
    let mut reference: Option<Vec<u8>> = None;
    for backend in Backend::ALL {
        let mut buf = input.to_vec();
        let opts = Options {
            settings: Settings {
                strip_schemas,
                minify,
            },
            backend,
        };
        let changed = transform(&mut buf, &opts);
        assert!(buf.len() <= input.len());
        assert_eq!(changed, buf.as_slice() != input);
        match &reference {
            None => reference = Some(buf),
            Some(r) => assert!(
                *r == buf,
                "{backend:?} differs from scalar for input {:?} (minify={minify}, strip={strip_schemas}):\n scalar {:?}\n other  {:?}",
                String::from_utf8_lossy(input),
                String::from_utf8_lossy(r),
                String::from_utf8_lossy(&buf)
            ),
        }
    }
    reference.unwrap()
}

/// JSONC-like token soup: exercises every state transition far more often
/// than uniformly random bytes would.
fn jsonc_like() -> impl Strategy<Value = Vec<u8>> {
    let token = prop_oneof![
        Just(&b"\""[..]),
        Just(&b"\\"[..]),
        Just(&b"/"[..]),
        Just(&b"*"[..]),
        Just(&b"//"[..]),
        Just(&b"/*"[..]),
        Just(&b"*/"[..]),
        Just(&b"\n"[..]),
        Just(&b"\r"[..]),
        Just(&b"\r\n"[..]),
        Just(&b" "[..]),
        Just(&b"\t"[..]),
        Just(&b"{"[..]),
        Just(&b"}"[..]),
        Just(&b"["[..]),
        Just(&b"]"[..]),
        Just(&b","[..]),
        Just(&b":"[..]),
        Just(&b"\"$schema\""[..]),
        Just(&b"\"\\u0024schema\""[..]),
        Just(&b"$schema"[..]),
        Just(&b"\\u00"[..]),
        Just(&b"\"a\""[..]),
        Just(&b"1.5e-3"[..]),
        Just(&b"true"[..]),
        Just(&b"\xff"[..]),
        Just(&b"\xc3\xa9"[..]),
    ];
    proptest::collection::vec(token, 0..80).prop_map(|tokens| tokens.concat())
}

proptest! {
    #![proptest_config(ProptestConfig::with_cases(3000))]

    #[test]
    fn random_bytes_agree(input in proptest::collection::vec(any::<u8>(), 0..300), minify: bool, strip: bool) {
        check_all_backends(&input, minify, strip);
    }

    #[test]
    fn jsonc_like_agree(input in jsonc_like(), minify: bool, strip: bool) {
        check_all_backends(&input, minify, strip);
    }

    #[test]
    fn output_is_a_subsequence(input in jsonc_like(), minify: bool, strip: bool) {
        // Everything that is kept must appear in the input in the same order.
        let out = check_all_backends(&input, minify, strip);
        let mut i = 0;
        for &b in &out {
            while i < input.len() && input[i] != b {
                i += 1;
            }
            prop_assert!(i < input.len(), "output is not a subsequence of the input");
            i += 1;
        }
    }
}

/// Lengths around SIMD block boundaries and every alignment of the buffer
/// start, with a deterministic pseudo-random JSONC-ish alphabet.
#[test]
fn boundary_lengths_and_alignments() {
    const ALPHABET: &[u8] = b"\"\\/*\n\r \t{}[]:,ab1$schema\xff";
    let lengths = [
        0usize, 1, 2, 3, 7, 8, 9, 15, 16, 17, 31, 32, 33, 47, 48, 49, 63, 64, 65, 127, 128, 129,
        255, 256, 257, 511, 512, 513, 1023, 1024, 1025,
    ];
    let mut seed = 0x1234_5678_u32;
    let mut next = || {
        seed = seed.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
        ALPHABET[(seed >> 24) as usize % ALPHABET.len()]
    };
    for len in lengths {
        for round in 0..8 {
            let content: Vec<u8> = (0..len).map(|_| next()).collect();
            for offset in 0..8 {
                for minify in [false, true] {
                    // Place the content at a controlled offset inside a larger
                    // allocation so that the slice start alignment varies.
                    let mut expected: Option<Vec<u8>> = None;
                    for backend in Backend::ALL {
                        let mut storage = vec![b'#'; offset + len + 8];
                        storage[offset..offset + len].copy_from_slice(&content);
                        let n = clean(&mut storage[offset..offset + len], minify, backend);
                        assert!(n <= len);
                        let out = storage[offset..offset + n].to_vec();
                        // Bytes outside the slice must be untouched.
                        assert!(storage[..offset].iter().all(|&b| b == b'#'));
                        assert!(storage[offset + len..].iter().all(|&b| b == b'#'));
                        match &expected {
                            None => expected = Some(out),
                            Some(e) => assert_eq!(
                                *e, out,
                                "len={len} round={round} offset={offset} minify={minify} backend={backend:?}"
                            ),
                        }
                    }
                }
            }
        }
    }
}
