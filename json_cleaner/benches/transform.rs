//! Micro-benchmarks of the in-memory transformation.
//!
//! Method: the transformation is in place and destructive, so every iteration
//! starts from a fresh copy of the input. The copy is made in Criterion's
//! `iter_batched` setup closure, which is excluded from the measured time.
//! Throughput is reported relative to the *input* size.
//!
//! Run with `cargo bench --bench transform` (optionally `-- <filter>`).

use criterion::{criterion_group, criterion_main, BatchSize, BenchmarkId, Criterion, Throughput};
use json_cleaner::schema::strip_root_schema;
use json_cleaner::transform::{clean, Backend};

const SIZES: [usize; 4] = [1 << 10, 8 << 10, 64 << 10, 1 << 20];

/// Repeats a generator until the buffer reaches `size`, then truncates. The
/// closure receives the entry index so that content can vary.
fn build(
    size: usize,
    head: &[u8],
    mut entry: impl FnMut(usize) -> Vec<u8>,
    tail: &[u8],
) -> Vec<u8> {
    let mut out = head.to_vec();
    let mut i = 0;
    while out.len() < size {
        out.extend_from_slice(&entry(i));
        i += 1;
    }
    out.truncate(size.saturating_sub(tail.len()));
    out.extend_from_slice(tail);
    out
}

/// Pretty-printed JSON without comments (typical Bedrock file).
fn pretty(size: usize) -> Vec<u8> {
    build(
        size,
        b"{\n    \"format_version\": \"1.20.80\",\n    \"minecraft:entity\": {\n",
        |i| {
            format!(
                "        \"minecraft:component_{i}\": {{\n            \"value\": {}.5,\n            \"identifier\": \"namespace:thing_{i}\",\n            \"list\": [1, 2, 3, 4],\n            \"enabled\": true\n        }},\n",
                i % 100
            )
            .into_bytes()
        },
        b"\n    }\n}\n",
    )
}

/// Pretty JSON with a comment on almost every line.
fn commented(size: usize) -> Vec<u8> {
    build(
        size,
        b"// header comment\n/* block\n   comment */\n{\n",
        |i| {
            format!(
                "    // entry {i}\n    \"key_{i}\": {i}, // trailing comment with text\n    /* inline */ \"other_{i}\": \"value\", /* another\n       multi-line block */\n"
            )
            .into_bytes()
        },
        b"}\n",
    )
}

/// Many strings with escape sequences.
fn stringy(size: usize) -> Vec<u8> {
    build(
        size,
        b"[\n",
        |i| {
            format!(
                "  \"text_{i}\": \"line one\\nline two \\\"quoted\\\" back\\\\slash \\u00e9\\u4e2d path C:\\\\Users\\\\x http://a.b/c//d\",\n"
            )
            .into_bytes()
        },
        b"]",
    )
}

/// Already minified JSON: nothing to remove in any mode.
fn minified(size: usize) -> Vec<u8> {
    build(
        size,
        b"{",
        |i| format!("\"k{i}\":{{\"a\":{i},\"b\":\"v{i}\",\"c\":[1,2,3],\"d\":true}},").into_bytes(),
        b"}",
    )
}

/// Single line, many very short tokens separated by spaces, no tabs or line
/// breaks: the adversarial case for the two-search minify finder.
fn short_tokens_single_line(size: usize) -> Vec<u8> {
    build(
        size,
        b"{ ",
        |i| format!("\"k{}\": {}, ", i % 1000, i % 10).into_bytes(),
        b"}",
    )
}

/// Few, very long strings.
fn long_strings(size: usize) -> Vec<u8> {
    build(
        size,
        b"[\n",
        |i| {
            let mut s = String::from("  \"");
            for j in 0..2000 {
                s.push_str(if (i + j) % 7 == 0 {
                    "lorem ipsum "
                } else {
                    "dolor sit "
                });
            }
            s.push_str("\",\n");
            s.into_bytes()
        },
        b"]",
    )
}

/// Unfavourable for the searches: slashes that do not start comments, tabs
/// as indentation (group two of the minify finder) and no spaces at all.
fn search_unfriendly(size: usize) -> Vec<u8> {
    build(
        size,
        b"{\n",
        |i| format!("\t\"a/b/c/{i}\":\t\"x/y/z\",\n\t\"n{i}\":\t1\n").into_bytes(),
        b"}",
    )
}

type Generator = fn(usize) -> Vec<u8>;

fn bench_clean(c: &mut Criterion) {
    let corpora: [(&str, Generator); 7] = [
        ("pretty", pretty),
        ("commented", commented),
        ("stringy", stringy),
        ("minified", minified),
        ("short_tokens", short_tokens_single_line),
        ("long_strings", long_strings),
        ("search_unfriendly", search_unfriendly),
    ];
    for (name, gen) in corpora {
        for minify in [false, true] {
            let mode = if minify { "minify" } else { "comments" };
            let mut group = c.benchmark_group(format!("clean/{name}/{mode}"));
            for size in SIZES {
                let input = gen(size);
                group.throughput(Throughput::Bytes(input.len() as u64));
                for backend in Backend::ALL {
                    let id = BenchmarkId::new(format!("{backend:?}").to_lowercase(), size);
                    group.bench_with_input(id, &input, |b, input| {
                        b.iter_batched(
                            || input.clone(),
                            |mut buf| clean(&mut buf, minify, backend),
                            BatchSize::LargeInput,
                        )
                    });
                }
            }
            group.finish();
        }
    }
}

fn bench_schema(c: &mut Criterion) {
    let mut group = c.benchmark_group("schema/strip_root");
    for size in SIZES {
        // Root object with $schema first, then many members; comment-free.
        let mut input = pretty(size);
        input.splice(
            2..2,
            b"    \"$schema\": \"https://example.com/entity.json\",\n"
                .iter()
                .copied(),
        );
        group.throughput(Throughput::Bytes(input.len() as u64));
        group.bench_with_input(BenchmarkId::new("pretty", size), &input, |b, input| {
            b.iter_batched(
                || input.clone(),
                |mut buf| strip_root_schema(&mut buf),
                BatchSize::LargeInput,
            )
        });
        let mut m = minified(size);
        m.splice(1..1, b"\"$schema\":\"x\",".iter().copied());
        group.throughput(Throughput::Bytes(m.len() as u64));
        group.bench_with_input(BenchmarkId::new("minified", size), &m, |b, input| {
            b.iter_batched(
                || input.clone(),
                |mut buf| strip_root_schema(&mut buf),
                BatchSize::LargeInput,
            )
        });
    }
    group.finish();
}

criterion_group!(benches, bench_clean, bench_schema);
criterion_main!(benches);
