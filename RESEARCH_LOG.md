# RESEARCH_LOG

## 2026-11-27 — Repository setup

- Firmware analyzed: none (setup).
- Files examined: fork at C:\Users\Administrator\Music\git\s5e8835-sboot-probe;
  upstream yuki493/s5e8835-sboot-probe (remote configured).
- Findings: fork already present under origin IamSlom; upstream remote present.
  Created branch `research/exynos1380`.
- Changes: none yet.
- Tests: n/a.
- Remaining: begin firmware analysis.

## 2026-11-27 — November firmware (A356EXXUBEZJ2) inspection

- Firmware analyzed: C:\Users\Administrator\Downloads\sboot.bin
  (also work\sboot_a35bl.bin), sha256 `5a84f29aff7b03dfcc46793417c0d107aa71656d6e119fe482a2ea09aa02fe3c`,
  size 0x800000. Build A356EXXUBEZJ2 (target firmware).
- Files examined: tools/firmware_inspect.py (new), tools/find_lk.py, tools/input_diag.py,
  original SVE resolve.py (EZJ2-adapted) at Documents\...\SVE-2026-3546-master.
- Findings: LK slice 0xf1000, base 0xf4800000, end 0xf6000000, BSS 0xf4c44000..0xf5087270.
  Markers 0x5e43, 0x27700e, 0x4f125f. 2 embedded ELF64. Buffers match family.
- Changes: added firmware_inspect.py, firmware_compare.py, resolver_analysis.py.
- Tests: tests/test_firmware_inspect.py, tests/test_firmware_compare.py (11 passed).
- Remaining: October binary unavailable; PAC matcher open.

## 2026-11-27 — Resolver analysis (November)

- Firmware analyzed: same November build.
- Files examined: tools/resolver_analysis.py, resolve.py (via SVE_REPO).
- Findings: 9/9 rows PASS under EZJ2-adapted resolver; confidence split
  (5 high, 3 medium, 2 low). Fallbacks noted. blk_bread 0xf4864c60,
  blk_bwrite 0xf4864d5c, sha256 0xf4865a4c.
- Changes: fixed tools/find_lk.py named_fn call signatures; added resolver_analysis.py.
- Tests: unittest suite green.
- Remaining: validate fallback constants via disassembly.

## 2026-11-27 — Disassembly validation of fallback addresses (November)

- Firmware analyzed: same November build (A356EXXUBEZJ2).
- Files examined: work/disasm.py (original), tools/prologue_scan.py (new).
- Findings:
  - screen_printf @ 0xf484c998 is a real PAC-built function (prologue pacibsp).
  - fallback cursor 0xf48168e8 disassembles to `mov w0, wzr; ret` (stub) — NOT usable.
  - fallback display-update 0xf4801e54 is an empty PAC function — NOT usable.
  - sha256 wrapper 0xf4865a4c and default send 0xf480f30c are real PAC functions.
  - LK prologue census: 4047 PAC vs 166 non-PAC.
- Changes: tools/prologue_scan.py, tests/test_prologue_scan.py;
  updated unresolved-issues.md, compatibility-matrix.md, final-technical-report.md.
- Tests: 12 passed.
- Remaining: re-derive cursor/display-update from screen_printf callers.

## 2026-11-27 — Documentation

- Firmware analyzed: n/a (docs).
- Files examined: all docs/.
- Findings: compatibility matrix, A35 comparison, unresolved issues, final report.
- Changes: docs/compatibility-matrix.md, docs/a35-firmware-comparison.md,
  docs/unresolved-issues.md, docs/final-technical-report.md, RESEARCH_LOG.md.
- Tests: n/a.
- Remaining: push fork? (no gh CLI; git push available via credentials).
