# Final technical report — Exynos 1380 (s5e8835) SVE-2026-3546 research

## 1. What has actually been confirmed on the Exynos 1380?

Confirmed on the November 2026 build (A356EXXUBEZJ2, sha256
`5a84f29aff7b03dfcc46793417c0d107aa71656d6e119fe482a2ea09aa02fe3c`):

- LK sub-image at file offset `0xf1000`, mapped `0xf4800000..0xf6000000`.
- BSS range `0xf4c44000..0xf5087270`, derived from the descriptor at `0xf1030`.
- Download buffers identical to s5e8825:
  PAR `0xce800000/0x7e00000/0x1e00000`, IN `0x890010000/0x8000000/0x2000000`.
- Slot size lives in `w10` (not `w9`); `w9` carries `0x40`.
- Block wrappers (PAC-aware): `blk_bread` @ `0xf4847b9c` (Nov) / `0xf48479ac` (Oct),
  `blk_bwrite` @ `0xf4847d98` (Nov) / `0xf4847ba8` (Oct). Both are PAC-built;
  the upstream `named_fn()` non-PAC heuristic is unreliable on these builds.
- SHA-256 wrapper @ `0xf4865a4c`.
- LK is PAC-built.
- Embedded ELF64 (AArch64) objects at `0x2a8928` and `0x2af008`.

Cross-build (documentary): October build A356EXXSBDZH1 shares slice/base/end/buffers;
BSS and middle marker differ. Consistent with linker variation, not protocol change.

## 2. Which parts of Yuki's implementation work?

- LK slice discovery (`bss_candidates` + `image_map`): works on November.
- `parallel()` and `input_map()` with the w9/w10 patch: work on November.
- Block-wrapper resolution (`named_fn` non-PAC prologue): works.
- A53 regression guard (`slot[2] == 9`): preserved in the patch; not re-run here
  (no s5e8825 firmware).

## 3. Which parts remain incomplete?

- PAC-tolerant prologue matcher for `screen_fns` and `sha256_fn` (fallbacks only).
- Independent validation of `comp_output` and `send_info` fallback constants.
- `io_shift` (returns 12 fallback).
- `screen` cursor/display-update addresses: the current fallbacks disassemble to
  stubs (`mov w0, wzr; ret` and an empty PAC function) and are not usable.
- Direct October-vs-November diff (October binary unavailable).

## 4. What changed between October and November firmware?

- BSS range: `0xf4c3c000..0xf5079908` -> `0xf4c44000..0xf5087270`.
- Middle `s5e8835` marker: `0x26ee28` -> `0x27700e` (+0x81e6).
- Wrapper addresses shifted by +0x1f0 (blk_bread/bwrite) and +0x280 (sha256)
  between October and November; screen_printf, reply, default send, and
  download buffers are unchanged.
- November resolves more rows under the EZJ2-adapted resolver, but several are
  fallbacks, not newly confirmed heuristic matches. See compatibility matrix.

## 5. Which conclusions are specific to SM-A356E?

- All measured addresses (blk wrappers, sha256, screen, reply/callback/send)
  are build-specific to A356EXXUBEZJ2 and must not be generalized to other
  builds/devices without re-running the resolver.
- BSS range and marker offsets are build-specific.
- The structural rows (slice/base/end/buffers/slot register) are family-wide
  (confirmed across X510, A26, A35, A54).

## 6. What is still required before a complete port is technically validated?

1. Independent (non-fallback) confirmation of comp_output, send_info, sha256,
   screen, blk shift on at least two builds.
2. PAC-aware prologue matcher validated against multiple builds.
3. s5e8825 regression re-run (no firmware available here).
4. PAC-aware re-implementation of named_fn() in the resolver (currently only
   available as the separate blk_wrapper_scan.py tool).
5. Hardware validation is explicitly excluded: the chain ends in an irreversible
   KEY2 fuse and there is no dry run. Static analysis cannot validate the fuse
   path, USB protocol, loader, or post-fuse boot.

## 7. Deliverables in this fork

- Improved docs: README, findings (preserved), compatibility-matrix.md,
  a35-firmware-comparison.md, unresolved-issues.md, final-technical-report.md.
- Tooling: tools/firmware_inspect.py, tools/firmware_compare.py,
  tools/resolver_analysis.py, plus fixed tools/find_lk.py, tools/input_diag.py.
- Tests: tests/test_firmware_inspect.py, tests/test_firmware_compare.py.
- RESEARCH_LOG.md.
- Git branch: research/exynos1380.
