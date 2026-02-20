#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml as _yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

ARTICLE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_(\d+)km_(.+)\.md$")
DRAFT_RE = re.compile(r"^_(\d+)km_(.+)\.md$")


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


def load_schedule(vehicle_path: Path) -> dict:
    """schedule.yml を読み込む。pyyaml が無い場合や file が無い場合は空 dict を返す。"""
    if not HAS_YAML:
        return {}
    schedule_file = vehicle_path / "schedule.yml"
    if not schedule_file.exists():
        return {}
    with schedule_file.open(encoding="utf-8") as f:
        return _yaml.safe_load(f) or {}


def collect_draft_files(vehicle: Vehicle) -> list[tuple[int, str, Path]]:
    """次回予定の下書きファイル (_XXXXXkm_内容.md) を収集する。"""
    drafts: list[tuple[int, str, Path]] = []
    for p in sorted(vehicle.path.glob("_*km_*.md")):
        m = DRAFT_RE.match(p.name)
        if m:
            km = int(m.group(1))
            title = m.group(2)
            drafts.append((km, title, p))
    drafts.sort(key=lambda x: x[0])
    return drafts


def collect_extra_files(vehicle: Vehicle) -> list[Path]:
    """非記事・非システム・非下書きの Markdown ファイルを収集する。"""
    extras: list[Path] = []
    for p in sorted(vehicle.path.glob("*.md")):
        if p.name in {"index.md", "_index.md", "_template.md"}:
            continue
        if ARTICLE_RE.match(p.name):
            continue
        if DRAFT_RE.match(p.name):
            continue
        extras.append(p)
    return extras


def render_vehicle_index(vehicle: Vehicle, articles: list[Article]) -> str:
    vehicle_articles = [a for a in articles if a.vehicle == vehicle.name]
    cover = find_cover_image(vehicle)
    extras = collect_extra_files(vehicle)
    schedule = load_schedule(vehicle.path)
    service_data: dict = schedule.get("service_data", {})
    drafts = collect_draft_files(vehicle)

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

    # 次回メンテ予定（下書きファイルから）
    if drafts:
        lines.append("")
        lines.append("## 次回メンテ予定")
        lines.append("")
        lines.append("| 予定走行距離 | 内容 |")
        lines.append("| ---: | --- |")
        for km, title, p in drafts:
            lines.append(f"| {km:,}km | [{title}]({p.name}) |")

    # サービスデータ（schedule.yml から）
    if service_data:
        lines.append("")
        lines.append("## サービスデータ")
        lines.append("")
        for category, items in service_data.items():
            lines.append(f"### {category}")
            lines.append("")
            lines.append("| 区分 | 油量 |")
            lines.append("| --- | ---: |")
            for key, value in items.items():
                lines.append(f"| {key} | {value} |")
            lines.append("")

    # その他（下書き・記事以外の追加ファイル）
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
