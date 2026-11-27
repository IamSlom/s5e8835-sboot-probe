# Unresolved issues (Exynos 1380 / s5e8835)

Each item: location, what is missing, available evidence, status, next step.
Confidence labels: high / medium / low.

## U1. PAC-tolerant prologue matcher (screen, sha256)

- Location: `resolve.py` `screen_fns()`, `sha256_fn()`.
- Missing: matcher that accepts `pacibsp`/`autibsp`-style prologues instead of
  fixed non-PAC sequences. Current code falls back to hardcoded addresses.
- Evidence: X510 wrapper reported at 0xf48645ec calling 0xf48bea04; November
  sha256 resolved to 0xf4865a4c via fallback. Block wrappers (non-PAC) pass,
  consistent with PAC explanation.
- Status: PARTIAL (fallbacks present, not validated).
- Next: implement PAC-aware prologue detection; validate against November image
  and any additional build.

## U2. comp_output (compressed output block)

- Location: `resolve.py` `comp_output()`.
- OUT_BASE=0xc5000000: SUPPORTED — the `mov w8, #-0x3b000000` encoding
  (0x52b8a008) occurs 3 times in the November LK (and October). The upstream
  10-instruction pattern is absent on PAC builds, but the constant is present.
- BLOCK=0x100000: FALLBACK — `mov w23, #0x100000` (0x52a002f7) occurs 0
  times on November; the block size is not independently evidenced. It is
  assumed from PIT geometry (0x100000) and structural validation passes.
- Status: PARTIAL (out_base supported; block size assumed).
- Next: locate the CD worker's block-size check on November to confirm 0x100000.

## U3. send_info (Odin setter/reply)

- Location: `resolve.py` `send_info()`.
- Missing: confirm reply/callback/default-send on November. Fallback uses
  call-count heuristic (default send 0xf480f30c with 11+ callers) and a
  calibrated reply (0xf4f1c9a8).
- Evidence: November returns reply=0xf4f1c9a8, callback=0xf4f1c9b8,
  send=0xf480f30c; structural checks pass (callback in BSS, cb_off=0x10).
  Upstream Odin setter pattern (6-word ADRP/STR sequence) has 0 hits on
  November (PAC build), so the fallback (call-count heuristic) is the only
  path; reply/callback are plausible but not independently validated.
- Status: PARTIAL.
- Next: map the Odin callback setter layout on November; verify reply buffer
  derivation (currently issue-#13 calibration).

## U4. blk shift

- Location: `resolve.py` `io_shift()`.
- Missing: qualifying `lsr`/shift pattern at blk_bread call sites. Fallback
  returns 12 (per PIT geometry).
- Evidence: November returns 12 (fallback path; no qualifying shift found).
- Status: LOW confidence.
- Next: inspect blk_bread call sites; determine whether shift is genuinely 12
  on November or whether the pattern is obfuscated.

## U5. screen cursor / display update

- Status: RESOLVED via `tools/screen_scan.py`.
- screen_printf (PAC start): Oct 0xf484c7a4 / Nov 0xf484c994 (155-156 callers).
- cursor getter: Oct 0xf484bdec / Nov 0xf484bfdc (PAC, freq 142-143).
- display update: 0xf4807c70 on both builds (PAC, freq 26).
- The old resolver fallbacks (0xf48168e8, 0xf4801e54) are stubs and must not
  be used; the PAC-aware scan replaces them.
- Remaining: port the PAC-aware logic into the resolver itself.

## U6. October vs November direct diff

- Status: RESOLVED (input now available).
- October binary obtained from official BL package and hash-verified
  (797fcba9...9e37484). Direct comparison performed; see
  docs/a35-firmware-comparison.md. Remaining: byte-level diff of non-LK
  sections and deeper function-level diff.

## U7. A53 regression (s5e8825)

- Location: resolve.py patch (slot[2] == 9 guard).
- Missing: re-run on an s5e8825 image to confirm the guard still preserves
  `base=0xf8800000 in=0x890010000 ...`. No s5e8825 firmware in this workspace.
- Evidence: Yuki docs report it green.
- Status: UNCONFIRMED in this fork (no input).
- Next: obtain an s5e8825 BL package; run resolve.py and compare to ground truth.

## U8. November-or-later diff for heuristics

- Location: README "Remaining work".
- Missing: any build newer than November 2026 to see which function the vendor
  changed. Only one November build is available.
- Status: OPEN.
- Next: collect additional builds; rerun resolver_analysis; diff slices.

## U9. BL signing profile for s5e8835

- Location: `s5e8835.json`, `android-resigner/config/s5e8835.json` (in original
  SVE project) — not in this fork.
- Missing: image offsets re-derived from A35 BL tar for real signing. Copied
  from s5e8825 template.
- Status: OUT OF SCOPE for this fork (no signing/redistribution here).
- Note: this fork does not contain signing code or firmware.

## U10. named_fn() blk wrapper resolution is unreliable on PAC builds

- Location: upstream `resolve.py` `named_fn()` (non-PAC prologue matcher).
- Missing: PAC-aware wrapper resolution. The classic prologue words
  (`fd7b bda9 f657 01a9 f44f 02a9 fd03 0091`) occur immediately after
  `pacibsp` on these builds, so the upstream scan returns an address 4 bytes
  past the real function start (and may match PAC functions, not true wrappers).
- Evidence: October/November blk_bread and blk_bwrite real starts are
  `0xf48479ac`/`0xf4847b9c` and `0xf4847ba8`/`0xf4847d98` (pacibsp),
  4 bytes before the upstream-reported values.
- Status: CONTRADICTED (upstream heuristic).
- Mitigation: `tools/blk_wrapper_scan.py` implements the PAC-aware scan.
- Next: port the PAC-aware logic into the resolver itself.

## U11. Synthetic coverage

- Location: tests/.
- Status: basic tests present; more fixtures needed for resolver heuristics.
- Next: add synthetic LK slices exercising image_map edge cases and
  bss_candidates false positives.
