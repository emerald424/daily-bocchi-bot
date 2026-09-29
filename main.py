import requests
import os
import random

  # 1. 从 GitHub Secrets 获取配置
  PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")

  def get_random_bocchi_image():
      """
      去 Safebooru 抓取一张后藤一里的图片
      """
      url = "https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&tags=gotou_hitori&limit=100"

      try:
          response = requests.get(url)
          if response.status_code == 200:
              data = response.json()
              if data:
                  image_data = random.choice(data)
                  image_url = f"https://safebooru.org/images/{image_data['directory']}/{image_data['image']}"
                  return image_url
      except Exception as e:
          print(f"找图失败: {e}")

      return "https://media1.tenor.com/m/oxsD2MwZD8IAAAAd/bocchi-the-rock-hitori-gotou.gif"

  def send_to_pushplus(image_url):
      """
      通过 PushPlus 把图片推送到你的微信
      """
      send_url = "https://www.pushplus.plus/send"
      content = f"🎸 早上好！今天的波奇酱请查收~\n\n![波奇酱]({image_url})"
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
      except Exception as e:
          print(f"发送失败: {e}")

  if __name__ == "__main__":
      if not PUSHPLUS_TOKEN:
          print("错误：未检测到 PUSHPLUS_TOKEN 配置，请在 GitHub 设置中添加。")
      else:
          print("正在寻找波奇酱...")
          pic = get_random_bocchi_image()
          print(f"找到图片: {pic}")
          send_to_pushplus(pic)
