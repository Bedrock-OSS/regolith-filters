const fs = require("fs");

const QUOTE = 34; // "
const STAR = 42; // *
const SLASH = 47; // /
const BACKSLASH = 92; // \
const LF = 10; // \n

// Same single-pass, string-aware, slice-accumulating algorithm as
// https://github.com/sindresorhus/strip-json-comments, reimplemented with
// charCodeAt in place of its per-character string comparisons. Input with no
// comments is returned as-is, allocating nothing.
//
// Newlines inside a comment are preserved so JSON.parse reports real line
// numbers; an unterminated /* is left in place and reaches JSON.parse as the
// error it is.
function stripJsonComments(text) {
  const length = text.length;
  let result = "";
  let offset = 0;
  let i = 0;

  while (i < length) {
    const code = text.charCodeAt(i);

    if (code === QUOTE) {
      i++;
      while (i < length) {
        const inner = text.charCodeAt(i);
        if (inner === BACKSLASH) {
          i += 2;
          continue;
        }
        i++;
        if (inner === QUOTE) break;
      }
      continue;
    }

    if (code !== SLASH) {
      i++;
      continue;
    }

    const next = text.charCodeAt(i + 1);
    const commentStart = i;

    if (next === SLASH) {
      result += text.slice(offset, i);
      i += 2;
      while (i < length && text.charCodeAt(i) !== LF) i++;
      offset = i; // leaves the newline itself in the next slice
      continue;
    }

    if (next === STAR) {
      result += text.slice(offset, i);
      i += 2;
      let newlines = 0;
      while (i < length) {
        const inner = text.charCodeAt(i);
        if (inner === STAR && text.charCodeAt(i + 1) === SLASH) break;
        if (inner === LF) newlines++;
        i++;
      }
      if (i >= length) return result + text.slice(commentStart);
      i += 2;
      if (newlines > 0) result += "\n".repeat(newlines);
      offset = i;
      continue;
    }

    i++;
  }

  return offset === 0 ? text : result + text.slice(offset);
}

// With allowComments set, a file is retried with comments stripped only after
// a strict parse fails, so well-formed JSON never runs the stripper.
function createJsonLoader(allowComments) {
  return function loadJsonFile(filePath) {
    const text = fs.readFileSync(filePath, "utf8");
    if (!allowComments) {
      return JSON.parse(text);
    }
    try {
      return JSON.parse(text);
    } catch {
      return JSON.parse(stripJsonComments(text));
    }
  };
}

module.exports = { stripJsonComments, createJsonLoader };
