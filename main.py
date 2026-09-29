import requests
import os
import random

# 1. 从 GitHub Secrets 获取配置
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")

HISTORY_FILE = "sent.txt"


def load_sent():
    """读取已经发送过的图片记录（去重用）"""
    try:
        with open(HISTORY_FILE, "r") as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        return set()


def get_random_bocchi_image(sent):
    """
    去 Safebooru 抓取一张后藤一里的图片，跳过已经发过的
    返回 (图片URL, 图片唯一标识)；失败时返回 (保底图URL, None)
    """
    # tags=gotou_hitori 表示只搜波奇酱，limit 加大随机池以降低重复概率
    url = "https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&tags=gotou_hitori&limit=1000"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data:
                # 过滤掉已经发送过的图片
                fresh = [d for d in data if d.get("image") not in sent]
                pool = fresh if fresh else data
                image_data = random.choice(pool)
                image_url = f"https://safebooru.org/images/{image_data['directory']}/{image_data['image']}"
                return image_url, image_data["image"]
    except Exception as e:
        print(f"找图失败: {e}")

    # 失败时返回一张保底图（不参与去重记录）
    return "https://media1.tenor.com/m/oxsD2MwZD8IAAAAd/bocchi-the-rock-hitori-gotou.gif", None


def send_to_pushplus(image_url):
    """通过 PushPlus 把图片推送到微信，返回是否成功"""
    send_url = "https://www.pushplus.plus/send"
    content = f"🎸 波奇酱来啦~\n\n![波奇酱]({image_url})"
    payload = {
        "token": PUSHPLUS_TOKEN,
        "title": "🎸 每日波奇酱",
        "content": content,
        "template": "markdown",
    }

    try:
        res = requests.post(send_url, json=payload)
        print(f"发送状态: {res.status_code}")
        print(res.text)
        return res.status_code == 200
    except Exception as e:
        print(f"发送失败: {e}")
        return False


if __name__ == "__main__":
    if not PUSHPLUS_TOKEN:
        print("错误：未检测到 PUSHPLUS_TOKEN 配置，请在 GitHub 设置中添加。")
        raise SystemExit(1)

    print("正在寻找波奇酱...")
    sent = load_sent()
    pic, image_key = get_random_bocchi_image(sent)
    print(f"找到图片: {pic}")

    ok = send_to_pushplus(pic)

    # 只有「真实抓到的图」且「发送成功」才记录，避免漏发或重复发保底图
    if ok and image_key:
        with open(HISTORY_FILE, "a") as f:
            f.write(image_key + "\n")
        print(f"已记录去重: {image_key}")
