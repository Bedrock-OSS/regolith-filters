//! Lexical JSONC transformation: comment removal and optional minification.
//!
//! The transformation works in place on a byte buffer and only ever removes
//! bytes, so the result is never longer than the input. Nothing is decoded:
//! strings, numbers and escape sequences keep their exact byte representation.
//!
//! Two backends implement the same state machine:
//! * [`Backend::Scalar`] is the byte-at-a-time reference implementation.
//! * [`Backend::Memchr`] skips over long runs with `memchr` and moves kept
//!   spans with `copy_within`.
//!
//! Both must produce identical output for identical input (see the
//! differential tests in `tests/`).

/// Selects the implementation of the comment/whitespace scanner.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Backend {
    /// Simple byte-at-a-time reference implementation.
    Scalar,
    /// `memchr`-accelerated implementation.
    Memchr,
}

impl Backend {
    /// All backends available in this build.
    pub const ALL: [Backend; 2] = [Backend::Scalar, Backend::Memchr];

    /// The backend used when nothing else is requested.
    pub const DEFAULT: Backend = Backend::Memchr;

    /// Parses a backend name (as used by the `JSON_CLEANER_BACKEND` variable).
    pub fn parse(name: &str) -> Option<Backend> {
        match name {
            "scalar" => Some(Backend::Scalar),
            "memchr" => Some(Backend::Memchr),
            _ => None,
        }
    }
}

/// Returns `true` for the four JSON whitespace bytes.
#[inline]
pub fn is_json_ws(b: u8) -> bool {
    matches!(b, b' ' | b'\t' | b'\n' | b'\r')
}

/// Removes comments from `buf` in place and, when `minify` is set, also
/// removes JSON whitespace outside of strings. Returns the new length; the
/// bytes past it are unspecified and should be truncated by the caller.
pub fn clean(buf: &mut [u8], minify: bool, backend: Backend) -> usize {
    match backend {
        Backend::Scalar => clean_scalar(buf, minify),
        Backend::Memchr => clean_memchr(buf, minify),
    }
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum State {
    Normal,
    Str,
    Escape,
    LineComment,
    BlockComment,
}

/// Reference implementation: one byte at a time.
pub fn clean_scalar(buf: &mut [u8], minify: bool) -> usize {
    let n = buf.len();
    let mut r = 0usize;
    let mut w = 0usize;
    let mut state = State::Normal;
    while r < n {
        let b = buf[r];
        match state {
            State::Normal => {
                if b == b'/' && r + 1 < n {
                    match buf[r + 1] {
                        b'/' => {
                            state = State::LineComment;
                            r += 2;
                            continue;
                        }
                        b'*' => {
                            state = State::BlockComment;
                            r += 2;
                            continue;
                        }
                        _ => {}
                    }
                }
                if minify && is_json_ws(b) {
                    r += 1;
                    continue;
                }
                if b == b'"' {
                    state = State::Str;
                }
            }
            State::Str => {
                if b == b'"' {
                    state = State::Normal;
                } else if b == b'\\' {
                    state = State::Escape;
                }
            }
            State::Escape => state = State::Str,
            State::LineComment => {
                // The line terminator itself is not part of the comment; it is
                // handled by the normal state (kept, or dropped when minifying).
                if b == b'\n' || b == b'\r' {
                    state = State::Normal;
                } else {
                    r += 1;
                }
                continue;
            }
            State::BlockComment => {
                if b == b'*' && r + 1 < n && buf[r + 1] == b'/' {
                    state = State::Normal;
                    r += 2;
                } else {
                    r += 1;
                }
                continue;
            }
        }
        // Keep the byte. Skip the copy while nothing has been removed yet.
        if w != r {
            buf[w] = b;
        }
        w += 1;
        r += 1;
    }
    w
}

/// Byte classes for the normal state when minifying: `"`, `/` and the four
/// JSON whitespace bytes need attention, everything else is kept as is.
///
/// `memchr` supports at most three needles per search. The first version of
/// this backend combined two `memchr3` searches per token; measured on
/// pretty-printed JSON, where such a byte occurs every few bytes, the call
/// overhead made it slower than the scalar loop (see `benchmarks.md`). A
/// plain table lookup is faster there and trivially linear; strings and
/// comments, where the long runs are, still use `memchr`.
static MINIFY_STOP: [bool; 256] = {
    let mut t = [false; 256];
    t[b'"' as usize] = true;
    t[b'/' as usize] = true;
    t[b' ' as usize] = true;
    t[b'\t' as usize] = true;
    t[b'\n' as usize] = true;
    t[b'\r' as usize] = true;
    t
};

#[inline]
fn find_minify_stop(buf: &[u8], mut r: usize) -> Option<usize> {
    while r < buf.len() {
        if MINIFY_STOP[buf[r] as usize] {
            return Some(r);
        }
        r += 1;
    }
    None
}

/// `memchr`-accelerated implementation with span copying.
pub fn clean_memchr(buf: &mut [u8], minify: bool) -> usize {
    let n = buf.len();
    // `keep` is the start of the pending kept span `[keep, r)`. `w` is where
    // that span will be written to. Copies happen only when bytes are removed.
    let mut keep = 0usize;
    let mut r = 0usize;
    let mut w = 0usize;
    let block_end = memchr::memmem::Finder::new(b"*/");

    // Moves the pending kept span `[keep, end)` to `w`.
    // The new `keep` is set by the caller after skipping the removed bytes.
    #[inline(always)]
    fn flush(buf: &mut [u8], keep: usize, end: usize, w: &mut usize) {
        if *w != keep {
            buf.copy_within(keep..end, *w);
        }
        *w += end - keep;
    }

    loop {
        let found = if minify {
            find_minify_stop(buf, r)
        } else {
            memchr::memchr2(b'"', b'/', &buf[r..]).map(|p| r + p)
        };
        let Some(p) = found else {
            break;
        };
        match buf[p] {
            b'"' => {
                // Skip over the string; it is kept verbatim.
                r = p + 1;
                loop {
                    match memchr::memchr2(b'"', b'\\', &buf[r..]) {
                        None => {
                            r = n;
                            break;
                        }
                        Some(q) => {
                            let q = r + q;
                            if buf[q] == b'"' {
                                r = q + 1;
                                break;
                            }
                            // Backslash: the next byte cannot end the string.
                            r = (q + 2).min(n);
                        }
                    }
                }
            }
            b'/' => {
                let next = buf.get(p + 1).copied();
                match next {
                    Some(b'/') => {
                        flush(buf, keep, p, &mut w);
                        r = memchr::memchr2(b'\n', b'\r', &buf[p + 2..]).map_or(n, |q| p + 2 + q);
                        keep = r;
                    }
                    Some(b'*') => {
                        flush(buf, keep, p, &mut w);
                        r = block_end.find(&buf[p + 2..]).map_or(n, |q| p + 2 + q + 2);
                        keep = r;
                    }
                    _ => r = p + 1,
                }
            }
            _ => {
                // Whitespace while minifying: drop the whole run.
                flush(buf, keep, p, &mut w);
                r = p + 1;
                while r < n && is_json_ws(buf[r]) {
                    r += 1;
                }
                keep = r;
            }
        }
    }
    flush(buf, keep, n, &mut w);
    w
}

#[cfg(test)]
mod tests {
    use super::*;

    fn run(input: &[u8], minify: bool) -> Vec<u8> {
        let mut outs = Vec::new();
        for backend in Backend::ALL {
            let mut buf = input.to_vec();
            let len = clean(&mut buf, minify, backend);
            buf.truncate(len);
            outs.push(buf);
        }
        assert_eq!(outs[0], outs[1], "backends differ for {:?}", input);
        outs.pop().unwrap()
    }

    #[test]
    fn required_example() {
        let input = b"{\n    // comment\n    \"number\": 1.00,\n    \"url\": \"https://example.com/a//b\",\n    \"escaped\": \"\\u0061\"\n}";
        assert_eq!(
            run(input, false),
            b"{\n    \n    \"number\": 1.00,\n    \"url\": \"https://example.com/a//b\",\n    \"escaped\": \"\\u0061\"\n}"
        );
        assert_eq!(
            run(input, true),
            b"{\"number\":1.00,\"url\":\"https://example.com/a//b\",\"escaped\":\"\\u0061\"}"
        );
    }

    #[test]
    fn comments_at_edges() {
        assert_eq!(run(b"// a\n{}", false), b"\n{}");
        assert_eq!(run(b"{}// a", false), b"{}");
        assert_eq!(run(b"{}/* a", false), b"{}");
        assert_eq!(run(b"/**/{}", false), b"{}");
        assert_eq!(run(b"//", false), b"");
        assert_eq!(run(b"/", false), b"/");
        assert_eq!(run(b"/*", false), b"");
        assert_eq!(run(b"*/", false), b"*/");
        assert_eq!(run(b"/*/", false), b"");
        assert_eq!(run(b"/**/", false), b"");
    }

    #[test]
    fn line_endings() {
        assert_eq!(run(b"1// a\r\n2", false), b"1\r\n2");
        assert_eq!(run(b"1// a\r2", false), b"1\r2");
        assert_eq!(run(b"1// a\n2", false), b"1\n2");
        assert_eq!(run(b"1// a\r\n2", true), b"12");
        assert_eq!(run(b"1/* a\r\n b */2", false), b"12");
    }

    #[test]
    fn strings_are_opaque() {
        assert_eq!(run(b"\"//\"", false), b"\"//\"");
        assert_eq!(run(b"\"/*\"", true), b"\"/*\"");
        assert_eq!(run(b"\"a \\\" // b\"", true), b"\"a \\\" // b\"");
        assert_eq!(run(b"\"\\\\\"//x", false), b"\"\\\\\"");
        assert_eq!(run(b"\" \t\n\"", true), b"\" \t\n\"");
        // Unterminated string keeps everything up to EOF.
        assert_eq!(run(b"\"abc // x", true), b"\"abc // x");
        assert_eq!(run(b"\"abc\\", true), b"\"abc\\");
    }

    #[test]
    fn minify_whitespace() {
        assert_eq!(run(b" \t\r\n{ \"a\" : 1 } \n", true), b"{\"a\":1}");
        assert_eq!(run(b"", true), b"");
        assert_eq!(run(b" ", true), b"");
        assert_eq!(run(b"1/*x*/2", true), b"12");
    }

    #[test]
    fn non_utf8_bytes_kept() {
        assert_eq!(run(b"\xff\xfe//c\n\x80", false), b"\xff\xfe\n\x80");
        assert_eq!(run(b"\"\xff\"//c", true), b"\"\xff\"");
    }
}
