You are generating one program from a specification. Work only in the current
directory.

Read, in this order:

1. `SPEC.md`, the complete behaviour of the program. Every sentence with
   "must", every table row and every formula is binding.
2. `INVARIANTS.md`, constraints on the shape of the program that hold in
   addition to SPEC.md.

3. `rcy-sdk/README.md`, the functions that produce every file format. Don't
   read `rcy-sdk/dist/rcy-sdk.js` to learn a format; the README is the
   interface.

Write the program to `output/main.js`, then build `output/rcy-export` from it:

```
node rcy-sdk/dist/bundle.cjs output/main.js output/rcy-export
```

- `output/main.js` wraps its body in one function whose first statement is
  `"use strict";`, because a directive at the top of the file has no effect
  after the SDK;
- `output/main.js` is CommonJS source with no `#!` line. It uses the SDK
  through the constant `rcySdk`, which the bundle defines above it, and loads
  only Node's built-in modules;
- `output/rcy-export` is only ever written by that command. Run it again
  after every edit to `output/main.js`, and test `output/rcy-export`, not
  `output/main.js`;
- runs on Node.js 22 and every later version. Test with the `node` on your
  PATH;
- every constant in SPEC.md's Constants table defined once in
  `output/main.js`, by the name the table gives it, with a comment stating
  its unit and reason, except a constant the table gives as an `rcySdk`
  member, which is used from there.

You may write tests and scratch files under `output/` while you work, and you
should run the program against WAV files you synthesise yourself to check
each numbered requirement. You have no access to the
acceptance scenarios; SPEC.md is the only statement of what they check. Don't
read any file outside the current directory.

Don't modify any file outside `output/`.

Where SPEC.md is silent or contradicts itself, don't guess silently: choose
the reading closest to the surrounding text and record it as a comment line
starting `// SPEC-GAP:` at the point in the code where the choice is made.

When the program is finished, write `output/build-manifest.json`:

```json
{
  "contract": "rcy-export/spec-v1",
  "spec_sha256": "<SHA-256 of SPEC.md, lowercase hex>",
  "artifact_sha256": "<SHA-256 of output/rcy-export, lowercase hex>"
}
```

Compute both digests from the files' bytes after the last bundle run. Then stop.
