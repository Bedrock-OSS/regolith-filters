//! Removal of `$schema` members from the root object.
//!
//! This pass runs after comment removal, so the buffer contains no comments
//! (but may still contain whitespace and trailing commas). It is a small
//! structural scanner, not a validating parser: it only needs to find member
//! boundaries at depth 0. Nested values are skipped by bracket counting with
//! proper string handling, without recursion.
//!
//! If the scanner cannot establish the structure of the root object with
//! confidence (unexpected byte, missing value, unbalanced brackets, EOF), the
//! whole document is left untouched.

use crate::transform::is_json_ws;

const TARGET: &[u8] = b"$schema";

/// Removes every member of the root object whose decoded name is exactly
/// `$schema`. Returns the new length of the buffer (`buf.len()` when nothing
/// was removed).
pub fn strip_root_schema(buf: &mut [u8]) -> usize {
    let n = buf.len();
    let ranges = match collect_ranges(buf) {
        Some(r) if !r.is_empty() => r,
        _ => return n,
    };
    apply_removals(buf, ranges)
}

/// Scans the root object and returns the byte ranges to remove, or `None`
/// when the structure could not be determined safely.
fn collect_ranges(buf: &[u8]) -> Option<Vec<(usize, usize)>> {
    let n = buf.len();
    let mut i = skip_ws(buf, 0);
    if i >= n || buf[i] != b'{' {
        return Some(Vec::new());
    }
    i += 1;
    let mut ranges: Vec<(usize, usize)> = Vec::new();
    // Position of the comma that follows the last member that is kept.
    let mut last_kept_comma: Option<usize> = None;
    loop {
        i = skip_ws(buf, i);
        if i >= n {
            return None;
        }
        if buf[i] == b'}' {
            break;
        }
        if buf[i] != b'"' {
            return None;
        }
        let key_start = i;
        let (after_key, is_schema) = scan_key(buf, i)?;
        i = skip_ws(buf, after_key);
        if i >= n || buf[i] != b':' {
            return None;
        }
        i = skip_ws(buf, i + 1);
        if i >= n {
            return None;
        }
        let value_end = skip_value(buf, i)?;
        i = skip_ws(buf, value_end);
        if i >= n {
            return None;
        }
        let comma = match buf[i] {
            b',' => Some(i),
            b'}' => None,
            _ => return None,
        };
        if is_schema {
            match comma {
                // Remove the member, its comma and the whitespace up to the
                // next token, so that pretty-printed files lose the whole line.
                Some(c) => ranges.push((key_start, skip_ws(buf, c + 1))),
                // Last member without a trailing comma: the separator that
                // has to go is the one after the previous kept member.
                None => match last_kept_comma {
                    Some(c) => ranges.push((c, value_end)),
                    None => ranges.push((key_start, value_end)),
                },
            }
        } else {
            last_kept_comma = comma;
        }
        match comma {
            Some(c) => i = c + 1,
            None => break,
        }
    }
    Some(ranges)
}

/// Compacts `buf` by removing the given ranges. Ranges may overlap and may be
/// out of order.
fn apply_removals(buf: &mut [u8], mut ranges: Vec<(usize, usize)>) -> usize {
    let n = buf.len();
    ranges.sort_unstable();
    let mut w = 0usize;
    let mut r = 0usize;
    let mut cur: Option<(usize, usize)> = None;
    for (s, e) in ranges {
        match cur {
            Some((cs, ce)) if s <= ce => cur = Some((cs, ce.max(e))),
            Some((cs, ce)) => {
                compact(buf, &mut r, &mut w, cs, ce);
                cur = Some((s, e));
            }
            None => cur = Some((s, e)),
        }
    }
    if let Some((cs, ce)) = cur {
        compact(buf, &mut r, &mut w, cs, ce);
    }
    if w != r {
        buf.copy_within(r..n, w);
    }
    w + (n - r)
}

/// Moves the kept span `[r, s)` to `w` and skips the removed span `[s, e)`.
#[inline]
fn compact(buf: &mut [u8], r: &mut usize, w: &mut usize, s: usize, e: usize) {
    if *w != *r {
        buf.copy_within(*r..s, *w);
    }
    *w += s - *r;
    *r = e;
}

#[inline]
fn skip_ws(buf: &[u8], mut i: usize) -> usize {
    while i < buf.len() && is_json_ws(buf[i]) {
        i += 1;
    }
    i
}

/// Scans the string starting at the opening quote `buf[i]`. Returns the index
/// after the closing quote and whether the decoded name equals `$schema`.
/// Returns `None` when the string is unterminated.
fn scan_key(buf: &[u8], i: usize) -> Option<(usize, bool)> {
    let n = buf.len();
    let mut i = i + 1;
    let mut matched = 0usize;
    let mut matches = true;
    loop {
        if i >= n {
            return None;
        }
        let b = buf[i];
        let (decoded, len) = if b == b'"' {
            return Some((i + 1, matches && matched == TARGET.len()));
        } else if b == b'\\' {
            decode_escape(buf, i)
        } else {
            (Some(b as u32), 1)
        };
        if matches {
            match decoded {
                Some(c) if matched < TARGET.len() && c == TARGET[matched] as u32 => matched += 1,
                _ => matches = false,
            }
        }
        i += len;
    }
}

/// Decodes the escape sequence starting at the backslash `buf[i]`. Returns the
/// code point (`None` for an invalid escape) and the number of bytes consumed.
/// Invalid escapes consume the backslash and the following byte, exactly like
/// the comment scanner does, so both passes agree on where strings end.
fn decode_escape(buf: &[u8], i: usize) -> (Option<u32>, usize) {
    let Some(&e) = buf.get(i + 1) else {
        return (None, 1);
    };
    let c = match e {
        b'"' => b'"',
        b'\\' => b'\\',
        b'/' => b'/',
        b'b' => 0x08,
        b'f' => 0x0c,
        b'n' => b'\n',
        b'r' => b'\r',
        b't' => b'\t',
        b'u' => {
            let hex = match buf.get(i + 2..i + 6) {
                Some(h) => h,
                None => return (None, 2),
            };
            let mut code = 0u32;
            for &h in hex {
                let Some(d) = (h as char).to_digit(16) else {
                    return (None, 2);
                };
                code = code * 16 + d;
            }
            return (Some(code), 6);
        }
        _ => return (None, 2),
    };
    (Some(c as u32), 2)
}

/// Skips a string starting at the opening quote `buf[i]`, returning the index
/// after the closing quote, or `None` when unterminated.
fn skip_string(buf: &[u8], i: usize) -> Option<usize> {
    let n = buf.len();
    let mut i = i + 1;
    while i < n {
        match buf[i] {
            b'"' => return Some(i + 1),
            b'\\' => i += 2,
            _ => i += 1,
        }
    }
    None
}

/// Skips one value starting at the non-whitespace byte `buf[i]`. Returns the
/// index just past the value, or `None` when there is no value or the value is
/// unterminated.
fn skip_value(buf: &[u8], i: usize) -> Option<usize> {
    let n = buf.len();
    match buf[i] {
        b'"' => skip_string(buf, i),
        b'{' | b'[' => {
            let mut depth = 0usize;
            let mut j = i;
            while j < n {
                match buf[j] {
                    b'"' => {
                        j = skip_string(buf, j)?;
                        continue;
                    }
                    b'{' | b'[' => depth += 1,
                    b'}' | b']' => {
                        depth -= 1;
                        if depth == 0 {
                            return Some(j + 1);
                        }
                    }
                    _ => {}
                }
                j += 1;
            }
            None
        }
        b'}' | b']' | b',' | b':' => None,
        _ => {
            let mut j = i;
            while j < n
                && !is_json_ws(buf[j])
                && !matches!(buf[j], b',' | b'}' | b']' | b'{' | b'[' | b'"' | b':')
            {
                j += 1;
            }
            Some(j)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn strip(input: &[u8]) -> Vec<u8> {
        let mut buf = input.to_vec();
        let len = strip_root_schema(&mut buf);
        buf.truncate(len);
        buf
    }

    #[test]
    fn required_examples() {
        assert_eq!(strip(b"{\"$schema\":\"x\"}"), b"{}");
        assert_eq!(strip(b"{\"$schema\":\"x\",}"), b"{}");
        assert_eq!(strip(b"{\"$schema\":\"x\",\"a\":1,}"), b"{\"a\":1,}");
        assert_eq!(strip(b"{\"a\":1,\"$schema\":\"x\"}"), b"{\"a\":1}");
        assert_eq!(strip(b"{\"$schema\":1,\"$schema\":2}"), b"{}");
    }

    #[test]
    fn positions_and_repeats() {
        assert_eq!(
            strip(b"{\"a\":1,\"$schema\":2,\"b\":3}"),
            b"{\"a\":1,\"b\":3}"
        );
        assert_eq!(
            strip(b"{\"$schema\":1,\"a\":1,\"$schema\":2,\"b\":2,\"$schema\":3}"),
            b"{\"a\":1,\"b\":2}"
        );
        assert_eq!(
            strip(b"{\"$schema\":1,\"$schema\":2,\"$schema\":3,}"),
            b"{}"
        );
        assert_eq!(
            strip(b"{\"a\":1,\"$schema\":1,\"$schema\":2}"),
            b"{\"a\":1}"
        );
        assert_eq!(
            strip(b"{\"a\":1,\"$schema\":1,\"$schema\":2,}"),
            b"{\"a\":1,}"
        );
    }

    #[test]
    fn whitespace_layout() {
        assert_eq!(
            strip(b"{\n  \"$schema\": \"x\",\n  \"a\": 1\n}\n"),
            b"{\n  \"a\": 1\n}\n"
        );
        assert_eq!(
            strip(b"{\n\t\"a\": 1,\n\t\"$schema\": \"x\"\n}\n"),
            b"{\n\t\"a\": 1\n}\n"
        );
        assert_eq!(
            strip(b"  {  \"$schema\"  :  \"x\"  ,  \"a\": 1 \n}"),
            b"  {  \"a\": 1 \n}"
        );
        assert_eq!(strip(b"{ \"$schema\" : \"x\" }"), b"{  }");
    }

    #[test]
    fn escaped_names() {
        assert_eq!(strip(b"{\"\\u0024schema\":1,\"a\":2}"), b"{\"a\":2}");
        assert_eq!(strip(b"{\"$schem\\u0061\":1,\"a\":2}"), b"{\"a\":2}");
        assert_eq!(strip(b"{\"\\u0024schem\\u0061\":1,\"a\":2}"), b"{\"a\":2}");
        // Invalid escapes never match.
        assert_eq!(strip(b"{\"$schem\\x61\":1}"), b"{\"$schem\\x61\":1}");
        assert_eq!(strip(b"{\"$schema\\u\":1}"), b"{\"$schema\\u\":1}");
        assert_eq!(strip(b"{\"\\u002schema\":1}"), b"{\"\\u002schema\":1}");
        // Similar but different names are kept.
        assert_eq!(
            strip(b"{\"$schemas\":1,\"schema\":2,\"$Schema\":3,\"$schema \":4,\"\":5}"),
            b"{\"$schemas\":1,\"schema\":2,\"$Schema\":3,\"$schema \":4,\"\":5}"
        );
        // The name is only compared, never rewritten.
        assert_eq!(strip(b"{\"\\u0061\":1,\"$schema\":2}"), b"{\"\\u0061\":1}");
    }

    #[test]
    fn only_root_object() {
        assert_eq!(strip(b"[{\"$schema\":1}]"), b"[{\"$schema\":1}]");
        assert_eq!(strip(b"\"$schema\""), b"\"$schema\"");
        assert_eq!(
            strip(b"{\"a\":{\"$schema\":1}}"),
            b"{\"a\":{\"$schema\":1}}"
        );
        assert_eq!(strip(b""), b"");
        assert_eq!(strip(b"{}"), b"{}");
        assert_eq!(strip(b"{ }"), b"{ }");
    }

    #[test]
    fn complex_values() {
        assert_eq!(
            strip(
                b"{\"$schema\":{\"a\":[1,\"}\",{\"b\":\"]\\\"}\"}],\"c\":\"x,y\"},\"keep\":true}"
            ),
            b"{\"keep\":true}"
        );
        assert_eq!(
            strip(b"{\"$schema\":\"a\\\"b,c}d\",\"k\":\"v\"}"),
            b"{\"k\":\"v\"}"
        );
        assert_eq!(
            strip(b"{\"$schema\":[[[]]],\"k\":-1.5e3}"),
            b"{\"k\":-1.5e3}"
        );
        assert_eq!(strip(b"{\"$schema\":null,\"k\":[1,2,]}"), b"{\"k\":[1,2,]}");
    }

    #[test]
    fn unsafe_structure_is_left_alone() {
        let cases: &[&[u8]] = &[
            b"{\"$schema\":[1,\"k\":2}",
            b"{\"$schema\":,\"k\":2}",
            b"{\"$schema\":1",
            b"{\"$schema\":1,",
            b"{\"$schema\"1}",
            b"{\"$schema\":1 \"k\":2}",
            b"{\"$schema\":\"unterminated}",
            b"{$schema:1}",
            b"{\"$schema\":1]}",
            b"{\"$schema\":1}}",
        ];
        for &c in cases {
            let out = strip(c);
            // Either untouched, or (trailing garbage after a complete root) cleaned.
            if c == b"{\"$schema\":1}}" {
                assert_eq!(out, b"{}}");
            } else {
                assert_eq!(out, c, "{:?}", String::from_utf8_lossy(c));
            }
        }
    }
}
