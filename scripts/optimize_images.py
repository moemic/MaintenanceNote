#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageOps
import pillow_heif

pillow_heif.register_heif_opener()


def resolve_content_root(explicit_root: str | None) -> Path:
    if explicit_root:
        return Path(explicit_root).resolve()

    maintenance = Path("MaintenanceNote")
    if maintenance.exists() and maintenance.is_dir():
        return maintenance.resolve()

    return Path(".").resolve()


def iter_asset_files(content_root: Path):
    for path in content_root.rglob("assets/*"):
        if path.is_file():
            yield path


def save_as_jpeg(src: Path, dst: Path, max_long_edge: int, quality: int):
    with Image.open(src) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        w, h = img.size
        long_edge = max(w, h)
        if long_edge > max_long_edge:
            scale = max_long_edge / float(long_edge)
            nw = max(1, int(round(w * scale)))
            nh = max(1, int(round(h * scale)))
            img = img.resize((nw, nh), Image.Resampling.LANCZOS)

        dst.parent.mkdir(parents=True, exist_ok=True)
        img.save(dst, format="JPEG", quality=quality, optimize=True, exif=b"")


def process_file(path: Path, max_long_edge: int, quality: int) -> tuple[bool, str]:
    ext = path.suffix.lower()

    if ext in {".heic", ".heif"}:
        out = path.with_suffix(".jpg")
        save_as_jpeg(path, out, max_long_edge=max_long_edge, quality=quality)
        path.unlink()
        return True, f"converted {path} -> {out}"

    if ext in {".jpg", ".jpeg"}:
        tmp = path.with_suffix(path.suffix + ".tmp")
        save_as_jpeg(path, tmp, max_long_edge=max_long_edge, quality=quality)
        tmp.replace(path)
        return True, f"optimized {path}"

    if ext == ".png":
        return False, f"skipped png {path}"

    return False, f"skipped {path}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Optimize images under */assets/*")
    parser.add_argument("--root", default=None, help="Content root. Defaults to MaintenanceNote/ if present, else current dir")
    parser.add_argument("--max-long-edge", type=int, default=2000)
    parser.add_argument("--quality", type=int, default=75)
    args = parser.parse_args()

    content_root = resolve_content_root(args.root)
    changed = 0
    errors = 0

    for file_path in iter_asset_files(content_root):
        try:
            did_change, msg = process_file(file_path, max_long_edge=args.max_long_edge, quality=args.quality)
            print(msg)
            if did_change:
                changed += 1
        except Exception as exc:  # pragma: no cover
            errors += 1
            print(f"error {file_path}: {exc}", file=sys.stderr)

    print(f"done changed={changed} errors={errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
