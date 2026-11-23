#!/usr/bin/env node
// Joins a program with the SDK into one executable file.
//
//   node bundle.cjs MAIN.js OUTPUT
//
// OUTPUT is: a `#!/usr/bin/env node` line, the bytes of rcy-sdk.js between two
// marker lines, then the bytes of MAIN.js. MAIN.js is CommonJS source that
// uses the constant `rcySdk` and must not start with a `#!` line.
"use strict";
const fs = require("node:fs");
const path = require("node:path");

const BEGIN = "// ---- rcy-sdk begin ----\n";
const END = "// ---- rcy-sdk end ----\n";
const [main, output] = process.argv.slice(2);
if (!main || !output || process.argv.length !== 4) {
  process.stderr.write("usage: node bundle.cjs MAIN.js OUTPUT\n");
  process.exit(2);
}
const sdk = fs.readFileSync(path.join(__dirname, "rcy-sdk.js"), "utf8");
const program = fs.readFileSync(main, "utf8");
if (program.startsWith("#!")) {
  process.stderr.write(`bundle: ${main} must not start with a #! line\n`);
  process.exit(2);
}
if (sdk.includes(BEGIN) || sdk.includes(END) || program.includes(BEGIN) || program.includes(END)) {
  process.stderr.write("bundle: a marker line appears inside an input\n");
  process.exit(2);
}
fs.writeFileSync(output, "#!/usr/bin/env node\n" + BEGIN + sdk + END + program, { mode: 0o755 });
fs.chmodSync(output, 0o755);
