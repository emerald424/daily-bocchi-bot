import requests
import os
import random
import time
from datetime import datetime, timezone, timedelta

# 从 GitHub Secrets 获取配置
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")

HISTORY_FILE = "sent.txt"        # 已发图片去重（发过不再发）
WINDOW_FILE = "sent_windows.txt"  # 已发时段去重（防止延迟重跑重复推）

SEND_HOURS = (10, 14, 22)  # 北京时间推送时段

# 图床：用本仓库 images/ 目录 + jsDelivr CDN 加速（免费，无需第三方账号）
IMAGE_DIR = "images"
CDN_BASE = "https://fastly.jsdelivr.net/gh/emerald424/daily-bocchi-bot@main"
KEEP_DAYS = 30  # images/ 只保留最近 30 天，避免仓库无限膨胀


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
    # Safebooru 偶发 503/限流，重试 3 次、随机翻页换一批图
    base = "https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&tags=gotou_hitori&limit=1000"
    for attempt in range(3):
        try:
            url = f"{base}&pid={random.randint(0, 5)}"
            response = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            print(f"Safebooru 第 {attempt + 1} 次请求，HTTP {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                if data:
                    fresh = [d for d in data if d.get("image") not in sent]
                    pool = fresh if fresh else data
                    image_data = random.choice(pool)
                    image_url = f"https://safebooru.org/images/{image_data['directory']}/{image_data['image']}"
                    return image_url, image_data["image"]
                print("Safebooru 返回空数据")
            else:
                print(f"Safebooru 返回非 200：{response.text[:100]}")
        except Exception as e:
            print(f"找图失败: {e}")
        time.sleep(5)
    # 三次都失败：返回 None，由调用方跳过本次，靠下次 run 补发
    return None, None


def download_and_store(image_url):
    """下载原图存到本仓库 images/ 目录，返回 jsDelivr CDN 链接；失败返回 None。"""
    try:
        dl = requests.get(image_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        dl.raise_for_status()
        ext = os.path.splitext(image_url.split("?")[0])[1] or ".jpg"
        os.makedirs(IMAGE_DIR, exist_ok=True)
        # 文件名带 UTC 时间戳 + 随机数，避免同名覆盖和 CDN 缓存旧图
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"bocchi_{stamp}_{random.randint(1000, 9999)}{ext}"
        with open(os.path.join(IMAGE_DIR, filename), "wb") as f:
            f.write(dl.content)
        return f"{CDN_BASE}/{IMAGE_DIR}/{filename}"
    except Exception as e:
        print(f"下载转存失败: {e}")
        return None


def cleanup_old_images(days=KEEP_DAYS):
    """按文件名日期清理 images/ 下超过 days 天的旧图，避免仓库膨胀。"""
    try:
        cutoff = datetime.now(timezone.utc).date() - timedelta(days=days)
        for name in os.listdir(IMAGE_DIR):
            parts = name.split("_")
            if len(parts) < 2:
                continue
            date_part = parts[1]
            if len(date_part) == 8 and date_part.isdigit():
                try:
                    d = datetime.strptime(date_part, "%Y%m%d").date()
                except ValueError:
                    continue
                if d < cutoff:
                    os.remove(os.path.join(IMAGE_DIR, name))
                    print(f"清理旧图: {name}")
    except FileNotFoundError:
        pass


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
    cleanup_old_images()

    for h in pending:
        window_key = f"{today}-{h}"
        print(f"正在补发 {h} 点的波奇酱...")
        pic, image_key = get_random_bocchi_image(sent)
        if pic is None:
            print(f"{h} 点 Safebooru 拉图失败，本次跳过，稍后由下次 run 重试（不记录去重）。")
            continue
        print(f"找到原图: {pic}")

        # 下载转存到本仓库 + jsDelivr CDN；失败则回退用原图链接
        cdn_url = download_and_store(pic)
        if cdn_url:
            pic = cdn_url
            print(f"已转存 CDN: {pic}")
        else:
            print("下载转存失败，回退使用原图链接")

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
