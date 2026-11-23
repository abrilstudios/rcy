#!/usr/bin/env node
// Writes dist/rcy-sdk.js: the SDK as one plain JavaScript file that defines a
// single global constant, `rcySdk`, and loads nothing. Each source module
// becomes a function scope; type annotations are removed by Node.
"use strict";
const fs = require("node:fs");
const path = require("node:path");
process.removeAllListeners("warning"); // type stripping is flagged experimental on every call
const { stripTypeScriptTypes } = require("node:module");

const root = path.resolve(__dirname, "..");
const version = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8")).version;
// Dependency order; index.ts re-exports every one of them.
const MODULES = ["numbers", "wav", "midi", "manifest", "exs"];
const parts = [`// rcy-sdk ${version}. Built from src/ by bin/build.cjs; don't edit.`, "const rcySdk = (() => {", '"use strict";'];
const all = [];
for (const name of MODULES) {
  const source = fs.readFileSync(path.join(root, "src", name + ".ts"), "utf8");
  const names = [];
  const body = stripTypeScriptTypes(source)
    .replace(/^import \{([^}]*)\} from "\.\/(\w+)\.ts";$/gm, (_, list, from) => `const {${list}} = m_${from};`)
    .replace(/^export (function|const|class) (\w+)/gm, (_, kind, id) => { names.push(id); return `${kind} ${id}`; });
  if (/^(import|export) /m.test(body)) throw new Error(`${name}.ts: an import or export form the build doesn't handle`);
  parts.push(`const m_${name} = (() => {`, body.trimEnd(), `return { ${names.join(", ")} };`, "})();");
  all.push(`...m_${name}`);
}
parts.push(`return Object.freeze({ VERSION: ${JSON.stringify(version)}, ${all.join(", ")} });`, "})();");
// An argument names another output file, which the tests use to check dist/ is current.
fs.writeFileSync(process.argv[2] ?? path.join(root, "dist", "rcy-sdk.js"), parts.join("\n") + "\n");
