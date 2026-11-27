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

## 2026-11-27 — PAC-aware screen resolver

- Firmware analyzed: October and November A35 builds.
- Files examined: tools/screen_scan.py (new).
- Findings:
  - screen_printf PAC starts: Oct 0xf484c7a4, Nov 0xf484c994 (155-156 callers).
  - cursor getter: Oct 0xf484bdec, Nov 0xf484bfdc (freq 142-143).
  - display update: 0xf4807c70 on both builds (freq 26).
  - The old resolver fallbacks (0xf48168e8, 0xf4801e54) are stubs and must not
    be used.
- Changes: tools/screen_scan.py; updated docs/unresolved-issues.md,
  compatibility-matrix.md, a35-firmware-comparison.md, final-technical-report.md.
- Tests: 12 passed.
- Remaining: port PAC-aware logic into resolve.py.

## 2026-11-27 — October firmware obtained and direct comparison

- Firmware analyzed: C:\Users\Administrator\Downloads\sboot_oct.bin
  (A356EXXSBDZH1), sha256 `797fcba92b90e6ceadd55ffa6adaea64793c4a378c0dca26efc8ce9f89e37484`,
  extracted from SAMFW.COM_SM-A356E_KSA_A356EXXSBDZH1_fac.zip via
  tools/extract_sboot.py; hash verified.
- Files examined: tools/firmware_compare.py, tools/resolver_analysis.py,
  tools/prologue_scan.py, tools/blk_wrapper_scan.py (new).
- Findings:
  - Direct October vs November comparison completed (see a35-firmware-comparison.md).
  - blk_bread/bwrite real (PAC) starts: Oct 0xf48479ac/0xf4847ba8,
    Nov 0xf4847b9c/0xf4847d98.
  - Upstream named_fn() heuristic is unreliable on PAC builds (off by 4 and
    may match PAC functions); added PAC-aware blk_wrapper_scan.py.
  - sha256 wrappers: Oct 0xf48657cc, Nov 0xf4865a4c.
  - screen_printf identical on both (0xf484c998); cursor/display-update
    fallbacks are stubs on both.
- Changes: tools/blk_wrapper_scan.py; updated docs.
- Tests: 12 passed.
- Remaining: PAC-aware named_fn in resolver; re-derive cursor/display-update.

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
