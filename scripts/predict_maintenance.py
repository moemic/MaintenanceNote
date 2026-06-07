#!/usr/bin/env python3
import os
import glob
import re
import json
import subprocess
from datetime import datetime

# --- 設定値 ---
BASE_DIR = "/Users/takahiro/Library/Mobile Documents/iCloud~md~obsidian/Documents/moemic"
GP5_DIR = os.path.join(BASE_DIR, "01_プロジェクト/MaintenanceNote/MaintenanceNote/GP5フィット")

# 送り1回あたりの予測走行距離 (過去データに基づく)
KM_PER_SOKURI = 150

# 通知する残り距離のしきい値
WARNING_THRESHOLD = 1000

def get_latest_oil_change():
    """最新のオイル交換記録を取得し、日付と走行距離を返す"""
    search_pattern = os.path.join(GP5_DIR, "*_オイル交換*.md")
    files = glob.glob(search_pattern)
    
    latest_date = None
    latest_km = 0
    latest_file = ""

    for filepath in files:
        filename = os.path.basename(filepath)
        # ファイル名フォーマット例: 2026-03-04_141558km_オイル交換.md
        match = re.match(r"(\d{4}-\d{2}-\d{2})_(\d+)km_.*", filename)
        if match:
            date_str = match.group(1)
            km_val = int(match.group(2))
            
            if latest_date is None or date_str > latest_date:
                latest_date = date_str
                latest_km = km_val
                latest_file = filename
                
    return latest_date, latest_km, latest_file

def count_sokuri_events(start_date_str):
    """指定した日付から現在までにカレンダーに登録された「送り」イベントの数を取得する"""
    start_time = f"{start_date_str}T00:00:00Z"
    end_time = datetime.now().strftime("%Y-%m-%dT23:59:59Z")
    
    cmd_str = f"gws calendar events list --params '{{\"calendarId\": \"primary\", \"q\": \"送り\", \"timeMin\": \"{start_time}\", \"timeMax\": \"{end_time}\", \"singleEvents\": true, \"maxResults\": 2500}}' --format json"
    cmd = ["zsh", "-l", "-c", cmd_str]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        items = data.get("items", [])
        return len(items)
    except subprocess.CalledProcessError as e:
        print(f"カレンダー情報の取得に失敗しました: {e.stderr}")
        return 0
    except json.JSONDecodeError:
        print("カレンダー情報のパースに失敗しました")
        return 0

def send_discord_webhook(message, webhook_url):
    """DiscordへWebhookで通知を送信する"""
    if not webhook_url:
        return
        
    payload = {
        "content": message,
        "username": "メンテナンス予測AI",
    }
    
    cmd = [
        "curl", "-H", "Content-Type: application/json",
        "-d", json.dumps(payload),
        webhook_url
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True)
    except Exception as e:
        print(f"Discordへの通知送信に失敗しました: {e}")

def main():
    print("🚗 メンテナンス予測システムを起動しています...")
    
    latest_date, latest_km, latest_file = get_latest_oil_change()
    if not latest_date:
        print("オイル交換の記録が見つかりませんでした。")
        return
        
    print(f"📌 最新記録: {latest_file} ({latest_date} 時点で {latest_km:,} km)")
    
    print(f"📅 {latest_date} から現在までの「送り」件数を計算中...")
    event_count = count_sokuri_events(latest_date)
    
    estimated_added_km = event_count * KM_PER_SOKURI
    current_estimated_km = latest_km + estimated_added_km
    target_km = latest_km + 5000
    remaining_km = target_km - current_estimated_km
    
    print("-" * 40)
    print(f"🚙 「送り」回数        : {event_count} 回")
    print(f"🛣️ 追加推計距離      : {estimated_added_km:,} km (1回{KM_PER_SOKURI}km換算)")
    print(f"📍 現在の推計走行距離: {current_estimated_km:,} km")
    print(f"🎯 目標 ({target_km:,} km) まで")
    print(f"⬇️ 残り              : {remaining_km:,} km")
    print("-" * 40)
    
    message = (
        f"🚗 **メンテナンス時期のお知らせ** 🚗\n"
        f"現在の推計走行距離が **{current_estimated_km:,} km** になりました。\n"
        f"次回の目標（{target_km:,} km）まで残り **{remaining_km:,} km** です！\n"
        f"そろそろ整備の準備をお願いします。（※最終オイル交換日: {latest_date}）"
    )
    
    # 残りがしきい値を下回ったか判定
    if remaining_km <= WARNING_THRESHOLD:
        print(f"\n⚠️ 警告: 目安となる {target_km:,} km まで残り {remaining_km:,} km を切りました！")
        
        # Webhook URLが環境変数にある場合のみ送信（Discord通知を使いたい場合は環境変数を設定するだけでOK）
        webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
        if webhook_url:
            print("📤 Discordへ通知を送信します...")
            send_discord_webhook(message, webhook_url)
        else:
            print("\n💡 ［ヒント］\n通知をDiscordに送る場合は、Discordサーバーの設定から「連携サービス」>「Webhook」を作成し、")
            print("発行されたURLをターミナル環境変数の DISCORD_WEBHOOK_URL に設定してください。")
            print("（よくわからない場合は、このスクリプトを moemic control center などで実行し出力を見る形でも十分運用できます！）")
            
    # デイリーノートのタスク欄への追記
    today_str = datetime.now().strftime("%Y-%m-%d")
    daily_note_path = os.path.join(BASE_DIR, "05_日誌", f"{today_str}.md")
    if os.path.exists(daily_note_path):
        try:
            with open(daily_note_path, "r", encoding="utf-8") as f:
                content = f.read()

            insert_marker = "## 🎯 翌日以降にやろうと思っているタスク"
            if insert_marker in content:
                alert_text = " - ⚠️ **1,000kmを切りました！そろそろ準備をしてください**" if remaining_km <= WARNING_THRESHOLD else ""
                new_task = f"- [ ] 🚗 **オイル交換準備** (推計走行距離: {current_estimated_km:,}km / 目標まで残り: {remaining_km:,}km){alert_text}"
                
                # 既存の「オイル交換準備」に関連するタスク行（完了/未完了問わず）を削除
                # 前後の改行を含めてマッチさせ、重複を防ぐ
                pattern = r'\n\s*- \[[^\]]*\].*🚗.*オイル交換準備.*'
                content = re.sub(pattern, '', content)
                
                # 挿入位置を特定。見出しの直後に新しいタスクを挿入
                # replaceだと複数回マッチする可能性があるため、最初の一つに限定
                if insert_marker in content:
                    content = content.replace(insert_marker, f"{insert_marker}\n{new_task}")
                
                with open(daily_note_path, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"📝 デイリーノート ({today_str}.md) の「翌日以降にやろうと思っているタスク」を更新しました。")
            else:
                # 万が一見出しが見つからない場合は末尾に追記 (重複防止チェック付き)
                if "🚗 メンテナンス予測" not in content and "オイル交換準備" not in content:
                    with open(daily_note_path, "a", encoding="utf-8") as f:
                        f.write(f"\n## 🚗 メンテナンス予測 ({datetime.now().strftime('%H:%M')})\n")
                        f.write(f"- 現在の推計走行距離: **{current_estimated_km:,} km**\n")
                        f.write(f"- 次回目標 ({target_km:,} km) まで残り: **{remaining_km:,} km**\n")
                        if remaining_km <= WARNING_THRESHOLD:
                            f.write("- ⚠️ **警告:** 1,000kmを切りました。そろそろオイル交換の準備をしてください！\n")
                    print(f"📝 デイリーノート ({today_str}.md) に記録を末尾に追記しました。")
                else:
                    # 既に記載がある場合は何もしない（古い情報の可能性があるが、構造が不明なため安全策をとる）
                    print(f"📝 デイリーノート ({today_str}.md) には既に記載があるためスキップしました。")
        except Exception as e:
            print(f"デイリーノートの追記に失敗しました: {e}")
            
    # Moemic Control Centerの通知用JSON出力（最終行）
    status_label = "⚠️ 交換準備" if remaining_km <= WARNING_THRESHOLD else "✅ 正常"
    print(json.dumps({"status": f"{status_label} / 残り{remaining_km:,}km"}, ensure_ascii=False))

if __name__ == "__main__":
    main()
