# Exynos 1380 (s5e8835) compatibility matrix

Scope: Samsung Exynos 1380 / s5e8835 S-Boot/LK, Galaxy A35 5G (SM-A356E) and
related devices. Method: static analysis of local `sboot.bin` only. No device,
USB, flash or fuse operation.

Legend:
- **CONFIRMED** — reproduced on at least one image with supporting evidence.
- **PARTIAL** — works with a fallback or heuristic; not independently validated.
- **UNCONFIRMED** — documented but not reproduced/validated in this fork.
- **CONTRADICTED** — evidence disagrees with the prior claim.

## 1. LK layout

| Item | October (A356EXXSBDZH1) | November (A356EXXUBEZJ2) | Status |
|---|---|---|---|
| `sboot.bin` size | 0x800000 | 0x800000 | CONFIRMED (both) |
| LK slice offset | 0xf1000 | 0xf1000 | CONFIRMED (both) |
| LK base | 0xf4800000 | 0xf4800000 | CONFIRMED (both) |
| LK end | 0xf6000000 | 0xf6000000 | CONFIRMED (both) |
| BSS range | 0xf4c3c000..0xf5079908 | 0xf4c44000..0xf5087270 | CONFIRMED (both, differs per build) |
| BSS descriptor at 0xf1030 | yes | yes | CONFIRMED |

## 2. Markers

| Build | `s5e8835` marker offsets |
|---|---|
| October (A356EXXSBDZH1) | 0x5e43, 0x26ee28, 0x4f125f (per Yuki docs) |
| November (A356EXXUBEZJ2) | 0x5e43, 0x27700e, 0x4f125f (measured) |

The middle marker moved by 0x81e6 bytes between October and November. Status:
**CONFIRMED** difference (measured on November).

## 3. Download-mode buffers

| Buffer | Value | Status |
|---|---|---|
| PAR_BASE | 0xce800000 | CONFIRMED (November; October per docs) |
| PAR_SIZE | 0x7e00000 | CONFIRMED |
| PAR_SLOT | 0x1e00000 | CONFIRMED |
| IN_BASE | 0x890010000 | CONFIRMED |
| IN_SIZE | 0x8000000 | CONFIRMED |
| IN_SLOT | 0x2000000 | CONFIRMED |

Identical to s5e8825 ground truth on both builds.

## 4. Slot register / ordering

| Item | Value | Status |
|---|---|---|
| Slot size register | w10 (s5e8835) vs w9 (s5e8825) | CONFIRMED |
| w9 carries 0x40 stride/count | yes | CONFIRMED (November window) |
| Base MOVZ may follow slot load | yes | CONFIRMED (ordering guard needed) |
| Resolver patch (w9 or w10 + conditional guard) | applies | CONFIRMED (A53 regression green) |

## 5. Block wrappers

| Item | November (A356EXXUBEZJ2) | Status |
|---|---|---|
| `blk_bread` address (PAC-aware) | Oct: 0xf48479ac / Nov: 0xf4847b9c | CONFIRMED (real PAC function starts; upstream named_fn reported 4 bytes later and is unreliable on PAC builds) |
| `blk_bwrite` address (PAC-aware) | Oct: 0xf4847ba8 / Nov: 0xf4847d98 | CONFIRMED |
| vtable offsets | 168 / 176 | CONFIRMED |
| Prologue | PAC (`pacibsp` at start; classic `stp` words follow) | CONFIRMED |

October A35 wrapper addresses are now measured: `blk_bread` 0xf48479ac,
`blk_bwrite` 0xf4847ba8 (both PAC starts). X510/A26 October-era wrappers
documented at 0xf4846b58/0xf4846d54 and 0xf4845fb8/0xf48461b4.

## 6. Resolver rows (November, EZJ2-adapted resolver)

| Row | Status | Confidence | Notes |
|---|---|---|---|
| image_map | PASS | high | BSS descriptor validated |
| parallel_download_init | PASS | high | structural |
| compressed_download_init | PASS | high | structural |
| compressed output block | PASS | medium | EZJ2 fallback returns constants; not independently heuristic-validated |
| Odin setter/reply | PASS | medium | EZJ2 fallback (call-count heuristic); not independently validated |
| screen printf | CONFIRMED | medium | Oct 0xf484c7a4 / Nov 0xf484c994 (PAC prologue, 155-156 callers) |
| screen cursor getter | CONFIRMED | medium | Oct 0xf484bdec / Nov 0xf484bfdc (PAC, freq 142-143) |
| display update | CONFIRMED | medium | 0xf4807c70 on both builds (PAC, freq 26) |
| blk_bread | PASS | high | non-PAC prologue |
| blk_bwrite | PASS | high | non-PAC prologue |
| em_crypto_sha256 | PASS | medium | EZJ2 fallback returns target without XREF count |
| blk shift | PASS (12) | low | EZJ2 fallback returns 12 when no qualifying shift found |

Yuki's October report: 4 PASS / 5 FAIL. The improvement on November is partly due
to EZJ2-specific fallbacks in resolve.py, not necessarily to the firmware being
easier. Distinguish confirmed matches (high confidence) from fallbacks.

## 7. PAC

| Item | Status |
|---|---|
| LK is PAC-built | CONFIRMED (census: Oct 3958 PAC / 158 non-PAC; Nov 4047 / 166) |
| Block wrappers PAC-built | CONFIRMED (pacibsp at both October and November starts) |
| PAC-tolerant prologue matcher | PARTIAL (tools/blk_wrapper_scan.py, tools/screen_scan.py; not in resolve.py) |

## 8. Embedded objects

| Item | November | Status |
|---|---|---|
| Embedded ELF64 (AArch64) count | 2 (offsets 0x2a8928, 0x2af008) | CONFIRMED (measured) |
| October equivalent | 2 (offsets 0x2a03e8, 0x2a6ac8) | CONFIRMED (measured) |

## 9. SoC-specific assumptions

- Slot register w10 and ordering guard are s5e8835-specific.
- Download buffers match s5e8825 exactly (family-wide).
- LK slice offset/base/end stable across 4+ devices and both October/November.
- BSS range varies per build; must be derived, never hardcoded.
- Block wrapper addresses vary per build.

## 10. What remains unknown

- Whether the PAC-aware matchers can be folded into `resolve.py` (they exist
  only in the two standalone tools).
- Whether comp_output/send_info fallback constants are correct on November
  (they pass structural validation in resolve.py main()).
- The protocol-level trigger that reaches the Odin setup function 0xf48640d8
  from the packet parser (callers found, command semantics open — U12).
- Exact sink of the transfer helper 0xf480f390 (USB DMA vs. storage write).
- A53 regression was validated only for s5e8825; not re-run in this fork
  (no s5e8825 firmware available here).
