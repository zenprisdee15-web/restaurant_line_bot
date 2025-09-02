import os, json
from datetime import datetime
from flask import Flask, request, jsonify
from dotenv import load_dotenv

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)

load_dotenv()

CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
PORT = int(os.getenv("PORT", "8000"))

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# โหลด config
with open("config.json", "r", encoding="utf-8") as f:
    CFG = json.load(f)

app = Flask(__name__)

# เก็บสถานะการจองโต๊ะ (ชั่วคราว)
RESV_STATE = {}

def quick_menu():
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="เมนู", text="เมนู")),
        QuickReplyButton(action=MessageAction(label="จองโต๊ะ", text="จองโต๊ะ")),
        QuickReplyButton(action=MessageAction(label="โปรโมชั่น", text="โปร")),
        QuickReplyButton(action=MessageAction(label="เวลาเปิดร้าน", text="เปิด")),
        QuickReplyButton(action=MessageAction(label="ที่อยู่/แผนที่", text="ที่อยู่")),
        QuickReplyButton(action=MessageAction(label="สั่งเดลิเวอรี", text="สั่ง")),
        QuickReplyButton(action=MessageAction(label="โทรหาเรา", text="เบอร์โทร"))
    ])

@app.route("/", methods=["GET"])
def health():
    return jsonify({"ok": True, "name": CFG["restaurant_name"]})

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return "Invalid signature", 400
    return "OK", 200

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    if user_id in RESV_STATE:
        step = RESV_STATE[user_id]["step"]
        data = RESV_STATE[user_id]["data"]
        if step == "ask_name":
            data["name"] = text
            RESV_STATE[user_id]["step"] = "ask_phone"
            reply = "ได้ครับ รบกวนขอเบอร์โทรด้วยครับ"
        elif step == "ask_phone":
            data["phone"] = text
            RESV_STATE[user_id]["step"] = "ask_people"
            reply = "ต้องการจองกี่ท่านครับ"
        elif step == "ask_people":
            data["people"] = text
            RESV_STATE[user_id]["step"] = "ask_datetime"
            reply = "วันและเวลาไหนครับ เช่น 5 ก.ย. 19:00"
        elif step == "ask_datetime":
            data["datetime"] = text
            summary = (
                f"✅ สรุปการจอง\n"
                f"ชื่อ: {data['name']}\n"
                f"โทร: {data['phone']}\n"
                f"จำนวน: {data['people']} คน\n"
                f"วันเวลา: {data['datetime']}\n"
                f"ทีมงานจะติดต่อยืนยันอีกครั้ง โทร {CFG['phone']}"
            )
            reply = summary
            RESV_STATE.pop(user_id)
        else:
            reply = "เกิดข้อผิดพลาด เริ่มใหม่พิมพ์ 'จองโต๊ะ'"

        line_bot_api.reply_message(event.reply_token,
            TextSendMessage(text=reply, quick_reply=quick_menu()))
        return

    if "เมนู" in text:
        reply = "\n".join([f"{m['emoji']} {m['name']} {m['price']} บาท" for m in CFG["top_menu"]])
    elif "โปร" in text:
        reply = CFG["promo_text"]
    elif "เปิด" in text:
        reply = CFG["hours"]
    elif "ที่อยู่" in text:
        reply = CFG["address"]
    elif "สั่ง" in text:
        reply = "\n".join([f"{k}: {v}" for k,v in CFG["order_links"].items()])
    elif "เบอร์" in text:
        reply = CFG["phone"]
    elif "จอง" in text:
        RESV_STATE[user_id] = {"step": "ask_name", "data": {}}
        reply = "ยินดีรับจองครับ กรุณาบอกชื่อผู้จอง"
    else:
        reply = "สวัสดีครับ พิมพ์: เมนู | จองโต๊ะ | โปร | เปิด | ที่อยู่ | สั่ง | เบอร์โทร"

    line_bot_api.reply_message(event.reply_token,
        TextSendMessage(text=reply, quick_reply=quick_menu()))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
