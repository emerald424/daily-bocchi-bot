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

def resolve_send_hour(now):
    """把执行时刻归入最近的推送时段，容忍 GitHub 调度延迟最多约 2 小时。
    返回所属时段小时（10/14/22），不在任何时段则返回 None。"""
    for h in SEND_HOURS:
        if h <= now.hour < h + 2:
            return h
    return None


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


def send_to_pushplus(image_url):
    send_url = "https://www.pushplus.plus/send"
    content = f"🎸 波奇酱来啦~\n\n![波奇酱]({image_url})"
    payload = {
        "token": PUSHPLUS_TOKEN,
        "title": "🎸 每日波奇酱",
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
    send_hour = resolve_send_hour(now)

    if send_hour is None:
        print(f"当前北京时间 {now.strftime('%H:%M')}，不在推送时段，跳过。")
        raise SystemExit(0)

    window_key = now.strftime("%Y-%m-%d") + f"-{send_hour}"
    if window_key in load_windows():
        print(f"时段 {window_key} 已推送过，跳过。")
        raise SystemExit(0)

    print("正在寻找波奇酱...")
    sent = load_sent()
    pic, image_key = get_random_bocchi_image(sent)
    print(f"找到图片: {pic}")

    ok = send_to_pushplus(pic)

    if ok:
        with open(WINDOW_FILE, "a") as f:
            f.write(window_key + "\n")
        print(f"已记录时段去重: {window_key}")
        if image_key:
            with open(HISTORY_FILE, "a") as f:
                f.write(image_key + "\n")
            print(f"已记录图片去重: {image_key}")
    else:
        print("推送失败，本次不记录去重，下次会重试。")
        raise SystemExit(1)
