// Tests for JSON comment handling (the `allowJsonComments` setting).
// Run with `node test/run.js` from the filter directory.
const fs = require("fs");
const os = require("os");
const path = require("path");
const assert = require("assert");

const { stripJsonComments, createJsonLoader } = require("../json_comments.js");

const loadStrict = createJsonLoader(false);
const loadLenient = createJsonLoader(true);

let failures = 0;
function test(name, fn) {
  try {
    fn();
    console.log(`ok   ${name}`);
  } catch (err) {
    failures++;
    console.error(`FAIL ${name}`);
    console.error("  " + String(err.stack || err).split("\n").join("\n  "));
  }
}

const dir = fs.mkdtempSync(path.join(os.tmpdir(), "type_gen-test-"));
let counter = 0;
function fixture(contents) {
  const file = path.join(dir, `f${counter++}.json`);
  fs.writeFileSync(file, contents);
  return file;
}

// [name, source, expected object, is the source commented?]
const CASES = [
  ["plain json", '{"a": 1}', { a: 1 }, false],
  ["trailing line comment", '{"a": 1} // note', { a: 1 }, true],
  ["leading line comment", '// note\n{"a": 1}', { a: 1 }, true],
  ["interleaved line comments", '{\n// x\n"a": 1,\n// y\n"b": 2\n}', { a: 1, b: 2 }, true],
  ["block comment", '{/* note */"a": 1}', { a: 1 }, true],
  ["multiline block comment", '{"a": /* one\ntwo */ 1}', { a: 1 }, true],
  ["crlf line endings", '{\r\n// note\r\n"a": 1\r\n}', { a: 1 }, true],
  // A "//" or "/*" inside a string is data, not a comment.
  ["url in string", '{"u": "https://x.com/y"}', { u: "https://x.com/y" }, false],
  ["comment-like string", '{"a": "not /* a */ comment"}', { a: "not /* a */ comment" }, false],
  ["slashes in string", '{"a": "//"}', { a: "//" }, false],
  ["escaped quote then slashes", '{"a": "q \\" // z"}', { a: 'q " // z' }, false],
  ["trailing backslash in string", '{"a": "back\\\\"} // c', { a: "back\\" }, true],
];

for (const [name, source, expected, commented] of CASES) {
  test(`lenient: ${name}`, () =>
    assert.deepStrictEqual(loadLenient(fixture(source)), expected));

  // Uncommented sources must behave identically with the setting off; commented
  // ones must still be rejected, since the setting is opt-in.
  test(`strict: ${name}`, () => {
    const file = fixture(source);
    if (commented) assert.throws(() => loadStrict(file), SyntaxError);
    else assert.deepStrictEqual(loadStrict(file), expected);
  });
}

test("newlines in comments are preserved for line numbers", () => {
  const stripped = stripJsonComments('{\n/* a\nb\nc */\n"x": 1}');
  assert.strictEqual((stripped.match(/\n/g) || []).length, 4);
});

test("stripping leaves comment-free input byte-identical", () => {
  const src = '{"a": [1, 2], "b": {"c": "d"}}';
  assert.strictEqual(stripJsonComments(src), src);
});

test("genuine syntax errors still throw when lenient", () => {
  assert.throws(() => loadLenient(fixture('{"a": }')), SyntaxError);
});

test("unterminated block comment throws rather than truncating", () => {
  assert.throws(() => loadLenient(fixture('{"a": 1} /* oops')), SyntaxError);
});

fs.rmSync(dir, { recursive: true, force: true });

if (failures) {
  console.error(`\n${failures} test(s) failed`);
  process.exit(1);
}
console.log("\nall tests passed");
