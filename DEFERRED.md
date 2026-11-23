# Decisions for the interactive application's specification

These decisions concern interactive editing, which `rcy-export` doesn't have.
Each becomes a requirement with a scenario when the standalone application is
specified.

| Subject | Decision |
|---|---|
| Slicing a region into `n` parts | `n` equal parts by the boundary formula of SPEC.md R08, applied to the region. |
| Nudging a boundary | The coarse step is 10 times the fine step, in both directions. |
| Export format option | None. An export always writes the whole kit of SPEC.md. |
| Manifest after cutting the source to a region | The manifest's `source` must name audio that the manifest's frame positions index correctly; it must not name the uncut file with positions measured in the cut one. |
| Logging | A log record at error level is written and nothing else happens; it never raises an exception. |
| Tail fade | Not applied on export, and there is no configuration key for it. |
| SFZ key numbering | One writer, with `FIRST_KEY` 60. |
