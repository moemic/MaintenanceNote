#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ARTICLE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_(\d+)km_(.+)\.md$")


@dataclass
class Vehicle:
    name: str
    path: Path


@dataclass
class Article:
    date: datetime
    distance_km: int | None
    title: str
    path: Path
    vehicle: str


def resolve_content_root(explicit_root: str | None) -> Path:
    if explicit_root:
        return Path(explicit_root).resolve()

    maintenance = Path("MaintenanceNote")
    if maintenance.exists() and maintenance.is_dir():
        return maintenance.resolve()

    return Path(".").resolve()


def discover_vehicles(content_root: Path) -> list[Vehicle]:
    vehicles: list[Vehicle] = []
    for child in sorted(content_root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if (child / "index.md").exists() and (child / "assets").is_dir():
            vehicles.append(Vehicle(name=child.name, path=child))
    return vehicles


def parse_article(path: Path, vehicle: str) -> Article | None:
    if path.name in {"index.md", "_index.md"}:
        return None
    if path.suffix.lower() != ".md":
        return None

    m = ARTICLE_RE.match(path.name)
    if not m:
        return None

    dt = datetime.strptime(m.group(1), "%Y-%m-%d")
    dist = int(m.group(2))
    title = m.group(3).replace("_", " ")
    return Article(date=dt, distance_km=dist, title=title, path=path, vehicle=vehicle)


def collect_articles(vehicles: list[Vehicle]) -> list[Article]:
    items: list[Article] = []
    for vehicle in vehicles:
        for p in vehicle.path.glob("*.md"):
            article = parse_article(p, vehicle.name)
            if article:
                items.append(article)
    items.sort(key=lambda x: (x.date, x.path.name), reverse=True)
    return items


def find_cover_image(vehicle: Vehicle) -> str | None:
    """Find cover image in vehicle's assets directory."""
    assets = vehicle.path / "assets"
    if not assets.is_dir():
        return None
    for ext in ("jpg", "jpeg", "png", "svg", "webp"):
        candidate = assets / f"cover.{ext}"
        if candidate.exists():
            return f"assets/cover.{ext}"
    return None


def collect_extra_files(vehicle: Vehicle) -> list[Path]:
    """Collect non-article, non-system markdown files."""
    extras: list[Path] = []
    for p in sorted(vehicle.path.glob("*.md")):
        if p.name in {"index.md", "_index.md", "_template.md"}:
            continue
        if ARTICLE_RE.match(p.name):
            continue
        extras.append(p)
    return extras


def render_vehicle_index(vehicle: Vehicle, articles: list[Article]) -> str:
    vehicle_articles = [a for a in articles if a.vehicle == vehicle.name]
    cover = find_cover_image(vehicle)
    extras = collect_extra_files(vehicle)

    lines: list[str] = []
    lines.append(f"# {vehicle.name} メンテナンスノート")
    lines.append("")

    if cover:
        lines.append(f"![{vehicle.name}]({cover})")
        lines.append("")

    lines.append("## 記録ルール")
    lines.append("")
    lines.append("- 記事ファイル名: `YYYY-MM-DD_走行距離km_内容.md`")
    lines.append("- 画像保存先: `assets/`")
    lines.append("- テンプレート: [`_template.md`](_template.md)")
    lines.append("")

    count = len(vehicle_articles)
    lines.append(f"## メンテナンス履歴（全{count}件）")
    lines.append("")

    if vehicle_articles:
        lines.append("| 日付 | 走行距離 | 内容 |")
        lines.append("| --- | ---: | --- |")
        for a in vehicle_articles:
            date_str = a.date.strftime("%Y-%m-%d")
            dist = f"{a.distance_km}km" if a.distance_km is not None else "-"
            link = a.path.name
            lines.append(f"| {date_str} | {dist} | [{a.title}]({link}) |")
    else:
        lines.append("まだメンテナンス記録がありません。")

    if extras:
        lines.append("")
        lines.append("## その他")
        lines.append("")
        for p in extras:
            name = p.stem
            lines.append(f"- [{name}]({p.name})")

    lines.append("")
    return "\n".join(lines)


def relpath(path: Path, base: Path) -> str:
    return path.relative_to(base).as_posix()


def render(content_root: Path, vehicles: list[Vehicle], articles: list[Article], top_n: int) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []
    lines.append("# MaintenanceNote インデックス")
    lines.append("")
    lines.append(f"生成日時: {now}")
    lines.append("")
    lines.append("## 所有車両一覧")
    lines.append("")
    if vehicles:
        for v in vehicles:
            idx = v.path / "index.md"
            lines.append(f"- [{v.name}]({relpath(idx, content_root)})")
    else:
        lines.append("- （車両が見つかりません）")

    lines.append("")
    lines.append(f"## 最新メンテ上位{top_n}件")
    lines.append("")

    picked = articles[:top_n]
    if picked:
        lines.append("| 日付 | 車両 | 走行距離 | 内容 |")
        lines.append("| --- | --- | ---: | --- |")
        for a in picked:
            date_str = a.date.strftime("%Y-%m-%d")
            dist = f"{a.distance_km}km" if a.distance_km is not None else "-"
            link = relpath(a.path, content_root)
            lines.append(f"| {date_str} | {a.vehicle} | {dist} | [{a.title}]({link}) |")
    else:
        lines.append("- （メンテ記事が見つかりません）")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate MaintenanceNote/_index.md")
    parser.add_argument("--root", default=None, help="Content root. Defaults to MaintenanceNote/ if present, else current dir")
    parser.add_argument("--top-n", type=int, default=10)
    args = parser.parse_args()

    content_root = resolve_content_root(args.root)
    vehicles = discover_vehicles(content_root)
    articles = collect_articles(vehicles)

    output = render(content_root, vehicles, articles, top_n=args.top_n)
    out_path = content_root / "_index.md"
    out_path.write_text(output, encoding="utf-8")
    print(f"generated {out_path}")

    for vehicle in vehicles:
        vehicle_index = render_vehicle_index(vehicle, articles)
        idx_path = vehicle.path / "index.md"
        idx_path.write_text(vehicle_index, encoding="utf-8")
        print(f"generated {idx_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
