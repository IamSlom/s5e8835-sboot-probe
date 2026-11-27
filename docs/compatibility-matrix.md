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
| `blk_bread` address | 0xf4864c60 | CONFIRMED (resolver, non-PAC prologue) |
| `blk_bwrite` address | 0xf4864d5c | CONFIRMED |
| vtable offsets | 168 / 176 | CONFIRMED |
| Prologue | non-PAC (fd7b bda9 ...) | CONFIRMED |

October A35 wrapper addresses were not captured in Yuki's docs (UNCONFIRMED for
October). X510/A26 October-era wrappers documented at 0xf4846b58/0xf4846d54 and
0xf4845fb8/0xf48461b4.

## 6. Resolver rows (November, EZJ2-adapted resolver)

| Row | Status | Confidence | Notes |
|---|---|---|---|
| image_map | PASS | high | BSS descriptor validated |
| parallel_download_init | PASS | high | structural |
| compressed_download_init | PASS | high | structural |
| compressed output block | PASS | medium | EZJ2 fallback returns constants; not independently heuristic-validated |
| Odin setter/reply | PASS | medium | EZJ2 fallback (call-count heuristic); not independently validated |
| screen printf/cursor | PARTIAL | low | printf 0xf484c998 is real PAC fn; cursor/display-update fallbacks are stubs (mov w0,wzr; ret / empty PAC) — not usable |
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
| LK is PAC-built | CONFIRMED (prologue mismatch; census: 4047 PAC vs 166 non-PAC prologues in November LK) |
| Block wrappers non-PAC | CONFIRMED |
| PAC-tolerant prologue matcher | NOT IMPLEMENTED (open work) |

## 8. Embedded objects

| Item | November | Status |
|---|---|---|
| Embedded ELF64 (AArch64) count | 2 (offsets 0x2a8928, 0x2af008) | CONFIRMED (measured) |
| October equivalent | not measured | UNCONFIRMED |

## 9. SoC-specific assumptions

- Slot register w10 and ordering guard are s5e8835-specific.
- Download buffers match s5e8825 exactly (family-wide).
- LK slice offset/base/end stable across 4+ devices and both October/November.
- BSS range varies per build; must be derived, never hardcoded.
- Block wrapper addresses vary per build.

## 10. What remains unknown

- Whether October A35 block-wrapper addresses match November (not captured).
- Whether PAC prologue matcher can be generalized.
- Whether comp_output/send_info fallback constants are correct on November
  (they pass structural validation in resolve.py main()).
- November-vs-October diff of comp_output/send_info internals.
- A53 regression was validated only for s5e8825; not re-run in this fork
  (no s5e8825 firmware available here).
