#!/usr/bin/env python3
"""各車両の schedule.yml を読み込み、最新の整備記録から次回予定の下書きファイルを生成する。

下書きファイルの命名規則: `_走行距離km_内容.md`
  例: _142341km_オイル交換.md

完了時はファイル名を `YYYY-MM-DD_走行距離km_内容.md` にリネームして使用する。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("pyyaml が必要です: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

ARTICLE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_(\d+)km_(.+)\.md$")
DRAFT_RE = re.compile(r"^_(\d+)km_(.+)\.md$")

DRAFT_TEMPLATE = """\
# {title}（次回予定）

- 実施日: （未定）
- 予定走行距離: {next_km_fmt}km
- 作業内容: {title}
- 実施場所:
- 費用:

## 作業詳細
-

## 使用部品・油脂
- 品名:
- 品番:
- 数量:

## メモ
- 前回: {last_km_fmt}km（{interval_km_fmt}km間隔）

## 画像
- `assets/` に画像を保存し、必要なら以下のように貼り付け
- `![説明](assets/画像ファイル名.jpg)`

---

完了時はファイル名を `YYYY-MM-DD_{next_km}km_{title}.md` にリネームしてください。
"""


def resolve_content_root(explicit_root: str | None) -> Path:
    if explicit_root:
        return Path(explicit_root).resolve()
    maintenance = Path("MaintenanceNote")
    if maintenance.exists() and maintenance.is_dir():
        return maintenance.resolve()
    return Path(".").resolve()


def discover_vehicles(content_root: Path) -> list[Path]:
    vehicles: list[Path] = []
    for child in sorted(content_root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if (child / "index.md").exists() and (child / "assets").is_dir():
            vehicles.append(child)
    return vehicles


def load_schedule(vehicle_path: Path) -> dict:
    schedule_file = vehicle_path / "schedule.yml"
    if not schedule_file.exists():
        return {}
    with schedule_file.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def collect_articles(vehicle_path: Path) -> list[tuple[int, str]]:
    """完了済み整備記録の (走行距離km, タイトル) リストを返す。"""
    articles: list[tuple[int, str]] = []
    for p in vehicle_path.glob("*.md"):
        m = ARTICLE_RE.match(p.name)
        if m:
            km = int(m.group(2))
            title = m.group(3)
            articles.append((km, title))
    return articles


def process_vehicle(vehicle_path: Path, dry_run: bool = False) -> None:
    schedule = load_schedule(vehicle_path)
    intervals: dict[str, int] = schedule.get("intervals", {})
    if not intervals:
        print("  schedule.yml なし、またはintervals未定義 → スキップ")
        return

    articles = collect_articles(vehicle_path)

    for item_name, interval_km in intervals.items():
        # 該当する最新記録を探す（タイトルに item_name が含まれるもの）
        matching_kms = [km for km, title in articles if item_name in title]
        if not matching_kms:
            print(f"  [{item_name}] 基準となる完了記録なし → スキップ")
            continue

        latest_km = max(matching_kms)
        next_km = latest_km + interval_km
        draft_name = f"_{next_km}km_{item_name}.md"
        draft_path = vehicle_path / draft_name

        # 古い下書きを削除（km が変わっている場合）
        for old in vehicle_path.glob(f"_*km_{item_name}.md"):
            if old.name != draft_name:
                print(f"  [{item_name}] 古い下書きを削除: {old.name}")
                if not dry_run:
                    old.unlink()

        # 新しい下書きを作成
        if draft_path.exists():
            print(f"  [{item_name}] 下書き済み: {draft_name}")
        else:
            content = DRAFT_TEMPLATE.format(
                title=item_name,
                next_km=next_km,
                next_km_fmt=f"{next_km:,}",
                last_km_fmt=f"{latest_km:,}",
                interval_km_fmt=f"{interval_km:,}",
            )
            print(f"  [{item_name}] 下書き作成: {draft_name}")
            if not dry_run:
                draft_path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="schedule.yml に基づいて次回メンテ予定の下書きファイルを生成する"
    )
    parser.add_argument("--root", default=None, help="コンテンツルート。省略時は MaintenanceNote/ または カレントディレクトリ")
    parser.add_argument("--dry-run", action="store_true", help="ファイルを実際に作成・削除しない")
    args = parser.parse_args()

    content_root = resolve_content_root(args.root)
    vehicles = discover_vehicles(content_root)

    if not vehicles:
        print("車両ディレクトリが見つかりませんでした")
        return 1

    for vehicle_path in vehicles:
        print(f"\n{vehicle_path.name}:")
        process_vehicle(vehicle_path, dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
