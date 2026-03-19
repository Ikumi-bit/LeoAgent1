import os
import traceback
from flask import Flask, request, abort
import requests
from datetime import datetime, timedelta

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import openai

app = Flask(__name__)

# ========= 環境変数 =========
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

openai.api_key = OPENAI_API_KEY

# ========= LINE送信 =========
def send_line_message(reply_token, text):
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text}]
    }
    requests.post(url, headers=headers, json=data)

# ========= エラー通知 =========
def send_error(reply_token, error):
    message = f"""申し訳ございません。
処理中にエラーが発生いたしました。

【内容】
{error}
"""
    send_line_message(reply_token, message)

# ========= Googleカレンダー取得 =========
def get_today_events():
    creds = Credentials(
        None,
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET
    )

    service = build("calendar", "v3", credentials=creds)

    now = datetime.utcnow().isoformat() + "Z"
    end = (datetime.utcnow() + timedelta(days=1)).isoformat() + "Z"

    events_result = service.events().list(
        calendarId="primary",
        timeMin=now,
        timeMax=end,
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    return events_result.get("items", [])

# ========= Webhook =========
@app.route("/callback", methods=["POST"])
def callback():
    try:
        body = request.json
        event = body["events"][0]
        reply_token = event["replyToken"]
        user_message = event["message"]["text"].strip()

        # --- 休日 ---
        if user_message == "休日":
            send_line_message(
                reply_token,
                "本日はお休みでございますね。\n今日の休み方はいかがなさいますか？"
            )
            return "OK"

        # --- 平日 ---
        if user_message == "平日":
            events = get_today_events()

            if events:
                summary = "おはようございます。\n本日のご予定でございます。\n"
                for e in events:
                    start = e["start"].get("dateTime", e["start"].get("date"))
                    summary += f"・{start} {e.get('summary','')}\n"

                send_line_message(reply_token, summary)
            else:
                send_line_message(
                    reply_token,
                    "今日は特段タスクはないようです。\nリラックスしてお仕事いってらっしゃいませ。"
                )
            return "OK"

        # --- その他 ---
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "あなたは丁寧で控えめな執事です。"},
                {"role": "user", "content": user_message}
            ]
        )

        send_line_message(reply_token, response.choices[0].message.content)
        return "OK"

    except Exception as e:
        send_error(
            body["events"][0]["replyToken"],
            traceback.format_exc()
        )
        return abort(500)

@app.route("/")
def health_check():
    return "Leo is awake."
