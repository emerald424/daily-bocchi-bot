import requests
import os
import random
from datetime import datetime, timezone, timedelta

# 从 GitHub Secrets 获取配置
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")

HISTORY_FILE = "sent.txt"        # 已发图片去重（发过不再发）
WINDOW_FILE = "sent_windows.txt"  # 已发时段去重（防止延迟重跑重复推）

SEND_HOURS = (10, 14, 22)  # 北京时间推送时段


def beijing_now():
    return datetime.now(timezone.utc) + timedelta(hours=8)


def load_sent():
    try:
        with open(HISTORY_FILE, "r") as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        return set()


def load_windows():
    try:
        with open(WINDOW_FILE, "r") as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        return set()


def get_random_bocchi_image(sent):
    url = "https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&tags=gotou_hitori&limit=1000"
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data:
                fresh = [d for d in data if d.get("image") not in sent]
                pool = fresh if fresh else data
                image_data = random.choice(pool)
                image_url = f"https://safebooru.org/images/{image_data['directory']}/{image_data['image']}"
                return image_url, image_data["image"]
    except Exception as e:
        print(f"找图失败: {e}")

    return "https://media1.tenor.com/m/oxsD2MwZD8IAAAAd/bocchi-the-rock-hitori-gotou.gif", None


def send_to_pushplus(image_url, title="🎸 每日波奇酱"):
    send_url = "https://www.pushplus.plus/send"
    content = f"🎸 波奇酱来啦~\n\n![波奇酱]({image_url})"
    payload = {
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": content,
        "template": "markdown",
    }
    try:
        res = requests.post(send_url, json=payload, timeout=30)
        print(f"HTTP 状态: {res.status_code}")
        print(res.text)
        if res.status_code == 200:
            body = res.json()
            if body.get("code") == 200:
                return True
            print(f"PushPlus 返回错误 code={body.get('code')}: {body.get('msg')}")
        return False
    except Exception as e:
        print(f"发送失败: {e}")
        return False


if __name__ == "__main__":
    if not PUSHPLUS_TOKEN:
        print("错误：未检测到 PUSHPLUS_TOKEN 配置，请在 GitHub Secrets 中添加。")
        raise SystemExit(1)

    now = beijing_now()
    today = now.strftime("%Y-%m-%d")
    sent_windows = load_windows()

    # 当天还没发过、且已经过了该时段的推送，按 10→14→22 顺序补发
    pending = [h for h in SEND_HOURS if now.hour >= h and f"{today}-{h}" not in sent_windows]

    if not pending:
        print(f"当前北京时间 {now.strftime('%H:%M')}，今天没有待补发的推送，跳过。")
        raise SystemExit(0)

    sent = load_sent()
    for h in pending:
        window_key = f"{today}-{h}"
        print(f"正在补发 {h} 点的波奇酱...")
        pic, image_key = get_random_bocchi_image(sent)
        print(f"找到图片: {pic}")

        ok = send_to_pushplus(pic, title=f"🎸 每日波奇酱（{h}点）")

        if ok:
            with open(WINDOW_FILE, "a") as f:
                f.write(window_key + "\n")
            print(f"已记录时段去重: {window_key}")
            if image_key:
                sent.add(image_key)
                with open(HISTORY_FILE, "a") as f:
                    f.write(image_key + "\n")
                print(f"已记录图片去重: {image_key}")
        else:
            print(f"{h} 点推送失败，本次不记录去重，下次会重试。")
            raise SystemExit(1)
