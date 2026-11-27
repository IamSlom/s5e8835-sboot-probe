#!/usr/bin/env python3
"""Resolver-analysis framework for s5e8835 LK images.

Runs the upstream (Gabriel2392) resolver heuristics when a patched resolve.py
is available (via SVE_REPO or cwd), captures PASS/FAIL and candidate values, and
assigns a confidence label to each row. Static only.
"""
import argparse
import importlib.util
import json
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import firmware_inspect as fi


ROW_CONFIDENCE = {
    "parallel_download_init": ("high", "structural buffer geometry; validated on 4+ builds"),
    "compressed_download_init": ("high", "structural buffer geometry; validated on 4+ builds"),
    "compressed output block": ("medium", "output accumulator; EZJ2 fallback present but heuristic-shaped"),
    "Odin setter/reply": ("medium", "callback/reply; EZJ2 fallback present"),
    "screen printf/cursor": ("low", "PAC prologue mismatch; fallback addresses unverified"),
    "blk_bread": ("high", "non-PAC prologue; stable across builds"),
    "blk_bwrite": ("high", "non-PAC prologue; stable across builds"),
    "em_crypto_sha256": ("medium", "PAC prologue; EZJ2 fallback present"),
    "blk shift": ("low", "depends on blk_bread call sites; heuristic-shaped"),
    "image_map": ("high", "BSS descriptor triple; validated"),
}


def try_import_resolve():
    candidates = []
    env = os.environ.get("SVE_REPO")
    if env:
        candidates.append(Path(env))
    candidates.append(Path.cwd())
    # common location used in this workspace
    candidates.append(Path(r"C:\Users\Administrator\Documents\Default Project\sve-2026-3546\SVE-2026-3546-master"))
    for base in candidates:
        rp = base / "resolve.py"
        if rp.exists():
            spec = importlib.util.spec_from_file_location("resolve", rp)
            mod = importlib.util.module_from_spec(spec)
            # resolve.py expects signer on path
            sys.path.insert(0, str(base / "signer"))
            sys.path.insert(0, str(base))
            spec.loader.exec_module(mod)
            return mod, base
    return None, None


def run_analysis(sboot_path, resolve_mod):
    data_full = Path(sboot_path).read_bytes()
    # LK slice
    cands = fi.bss_candidates(data_full)
    accepted_off = None
    mapping = None
    for start in cands:
        try:
            base, end, bss_lo, bss_hi, label = fi.image_map(data_full[start:])
            accepted_off = start
            mapping = (base, end, bss_lo, bss_hi, label)
            break
        except Exception:
            continue
    if mapping is None:
        raise RuntimeError("no valid LK slice")

    base, end, bss_lo, bss_hi, label = mapping
    data = data_full[accepted_off:]
    resolve_mod.LK_BASE = base

    rows = []

    def record(name, status, detail, value=None):
        conf, rationale = ROW_CONFIDENCE.get(name, ("unknown", "no confidence metadata"))
        rows.append({
            "name": name,
            "status": status,
            "detail": detail,
            "value": value,
            "confidence": conf,
            "rationale": rationale,
        })

    # image_map
    record("image_map", "PASS", f"base={base:#x} end={end:#x} bss=[{bss_lo:#x},{bss_hi:#x})", (base, end, bss_lo, bss_hi))

    # helper to call resolve functions safely
    def step(name, fn, *args, **kwargs):
        try:
            v = fn(*args, **kwargs)
            record(name, "PASS", str(v), v)
        except Exception as e:
            record(name, "FAIL", f"{type(e).__name__}: {e}")

    step("parallel_download_init", resolve_mod.parallel, data)
    step("compressed_download_init", resolve_mod.input_map, data)
    step("compressed output block", resolve_mod.comp_output, data)
    try:
        step("Odin setter/reply", resolve_mod.send_info, data, bss_lo, bss_hi)
    except Exception as e:
        record("Odin setter/reply", "FAIL", f"{type(e).__name__}: {e}")
    step("screen printf/cursor", resolve_mod.screen_fns, data)
    try:
        bread = resolve_mod.named_fn(data, b"blk_bread")
        step("blk_bread", lambda: bread)
    except Exception as e:
        record("blk_bread", "FAIL", f"{type(e).__name__}: {e}")
    try:
        bwrite = resolve_mod.named_fn(data, b"blk_bwrite")
        step("blk_bwrite", lambda: bwrite)
    except Exception as e:
        record("blk_bwrite", "FAIL", f"{type(e).__name__}: {e}")
    step("em_crypto_sha256", resolve_mod.sha256_fn, data)
    # blk shift
    try:
        bread_addr = resolve_mod.named_fn(data, b"blk_bread")[0]
        step("blk shift", resolve_mod.io_shift, data, bread_addr)
    except Exception as e:
        record("blk shift", "SKIP", str(e))

    return {
        "file": str(sboot_path),
        "slice_offset": accepted_off,
        "lk_base": base,
        "lk_end": end,
        "bss": [bss_lo, bss_hi],
        "rows": rows,
    }


def render_markdown(result):
    lines = []
    lines.append(f"# Resolver analysis: {result['file']}")
    lines.append("")
    lines.append(f"- LK slice offset: {result['slice_offset']:#x}")
    lines.append(f"- LK base: {result['lk_base']:#x}  end: {result['lk_end']:#x}")
    lines.append(f"- BSS: [{result['bss'][0]:#x}, {result['bss'][1]:#x})")
    lines.append("")
    lines.append("| Row | Status | Confidence | Value / detail |")
    lines.append("|---|---|---|---|")
    for r in result["rows"]:
        val = r["value"] if r["value"] is not None else r["detail"]
        lines.append(f"| {r['name']} | {r['status']} | {r['confidence']} | {val} |")
    lines.append("")
    lines.append("## Rationale")
    for r in result["rows"]:
        lines.append(f"- **{r['name']}** ({r['confidence']}): {r['rationale']}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Resolver analysis for an sboot.bin")
    ap.add_argument("image")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--markdown", action="store_true")
    args = ap.parse_args()

    resolve_mod, base = try_import_resolve()
    if resolve_mod is None:
        print("resolve.py not found. Set SVE_REPO to a directory containing resolve.py.", file=sys.stderr)
        sys.exit(2)
    print(f"using resolve.py from {base}", file=sys.stderr)

    result = run_analysis(args.image, resolve_mod)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    elif args.markdown:
        print(render_markdown(result))
    else:
        print(f"file: {result['file']}")
        for r in result["rows"]:
            print(f"{r['status']:4}  {r['name']:<28}  conf={r['confidence']:<6}  {r['detail']}")


if __name__ == "__main__":
    main()
