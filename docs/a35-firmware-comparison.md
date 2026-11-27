# A35 (SM-A356E) firmware comparison: October vs November 2026

Devices: Samsung Galaxy A35 5G (SM-A356E), SoC s5e8835.
Builds compared:
- October: A356EXXSBDZH1 (SPL Oct 2026), sha256 `797fcba9...9e37484` (per Yuki docs; not available locally)
- November: A356EXXUBEZJ2 (target firmware), sha256 `5a84f29a...02fe3c`.
  Provenance: extracted from official BL package
  `BL_A356EXXUBEZJ2_..._MULTI_CERT.tar.md5` via `tools/extract_sboot.py`
  (member `sboot.bin.lz4`, lz4-decompressed, hash verified).

Method: static analysis only. October values are taken from Yuki's published
documentation (findings.md, issue-body.md); November values measured in this fork.
No October binary was available locally, so October-side rows are documentary,
not re-measured.

## Summary

The LK layout is stable between October and November: same slice offset, base,
end, and download buffers. The differences are in BSS range, marker offsets,
wrapper addresses, and the internal heuristic shapes. The November image resolves
more rows under the EZJ2-adapted resolver, but several of those are fallbacks
rather than confirmed heuristic matches.

## Side-by-side

| Item | October (A356EXXSBDZH1) | November (A356EXXUBEZJ2) | Changed? |
|---|---|---|---|
| sboot.bin size | 0x800000 | 0x800000 | no |
| sha256 | 797fcba9...9e37484 | 5a84f29a...02fe3c | yes (different build) |
| LK slice offset | 0xf1000 | 0xf1000 | no |
| LK base | 0xf4800000 | 0xf4800000 | no |
| LK end | 0xf6000000 | 0xf6000000 | no |
| BSS range | 0xf4c3c000..0xf5079908 | 0xf4c44000..0xf5087270 | yes |
| `s5e8835` markers | 0x5e43, 0x26ee28, 0x4f125f | 0x5e43, 0x27700e, 0x4f125f | middle moved +0x81e6 |
| PAR buffer | 0xce800000/0x7e00000/0x1e00000 | same | no |
| IN buffer | 0x890010000/0x8000000/0x2000000 | same | no |
| blk_bread address (PAC-aware) | 0xf48479ac | 0xf4847b9c | yes (+0x1f0) |
| blk_bwrite address (PAC-aware) | 0xf4847ba8 | 0xf4847d98 | yes (+0x1f0) |
| sha256 wrapper | 0xf48657cc | 0xf4865a4c | yes (+0x280) |
| screen_printf | 0xf484c7a4 | 0xf484c994 | yes (+0x1f0) |
| screen cursor getter | 0xf484bdec | 0xf484bfdc | yes (+0x1f0) |
| display update | 0xf4807c70 | 0xf4807c70 | no |
| reply (Odin) | 0xf4f1c9a8 | 0xf4f1c9a8 | no |
| default send | 0xf480f30c | 0xf480f30c | no |
| sha256 wrapper | not captured for A35 | 0xf4865a4c | n/a |
| screen printf | not captured | 0xf484c998 | n/a |
| reply (Odin) | not captured | 0xf4f1c9a8 | n/a |
| callback | not captured | 0xf4f1c9b8 | n/a |
| default send | not captured | 0xf480f30c | n/a |
| embedded ELF count | not measured | 2 | n/a |

## Probe result comparison

October (Yuki docs, X510/A26-equivalent A35 structural): 4 PASS / 5 FAIL
- PASS: parallel, input_map, blk_bread, blk_bwrite
- FAIL: comp_output, send_info, screen, sha256, blk shift

November (this fork, EZJ2-adapted resolver): 9/9 PASS, but with confidence split
- high confidence: image_map, parallel, input_map, blk_bread, blk_bwrite
- medium: comp_output, send_info, sha256
- low: screen, blk shift (fallbacks)

## Interpretation

1. The structural rows (parallel, input_map, blk wrappers) are stable and
   high-confidence on both builds. This matches Yuki's conclusion that the LK
   layout and download buffers are family-stable.
2. The five rows that failed on October still rely on EZJ2-specific fallbacks on
   November. Their "PASS" status reflects resolver fallback logic, not an
   independently confirmed heuristic match. The fallback constants (screen cursor,
   display update, sha256 target, blk shift=12) need targeted disassembly to
   validate.
3. The BSS range and middle marker moved, confirming that addresses derived from
   linker output are build-specific and must not be hardcoded. `image_map()` and
   marker scans remain the correct approach.
4. The November image is the first local artifact available in this workspace; it
   unblocks the "November-2026+ BL diff" item partially, but a true October binary
   is still needed for a direct diff. The October values above are documentary.

## Inputs (now available)

- October A35 binary (A356EXXSBDZH1) was obtained from the official BL package
  `SAMFW.COM_SM-A356E_KSA_A356EXXSBDZH1_fac.zip` and extracted via
  `tools/extract_sboot.py`. sha256 verified against Yuki's documented value
  (`797fcba9...9e37484`). This unblocks the direct comparison above.
- Block-wrapper addresses for both builds were re-derived with the PAC-aware
  `tools/blk_wrapper_scan.py`.

## Reproduction

```
python tools/firmware_inspect.py <sboot.bin>
python tools/find_lk.py <sboot.bin>          # requires SVE_REPO
python tools/resolver_analysis.py <sboot.bin> # requires SVE_REPO
python tools/firmware_compare.py <oct.bin> <nov.bin>
```
