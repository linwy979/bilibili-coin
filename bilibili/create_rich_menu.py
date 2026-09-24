from linebot import LineBotApi
from linebot.models import (
    RichMenu, RichMenuArea, RichMenuBounds,
    RichMenuSize, URIAction
)
from linebot.exceptions import LineBotApiError
from dotenv import load_dotenv
import os

# 從 pwd.env 讀取 token 與對外網址
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, "pwd.env"))
CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)

# ✅ LINE Rich Menu 的每個按鈕都要用 https 開頭的完整 URL
base_url = f"{os.getenv('PUBLIC_URL')}/#"

areas = [
    RichMenuArea(
        bounds=RichMenuBounds(x=100, y=80, width=800, height=800),
        action=URIAction(label="查詢幣價", uri=f"{base_url}/?target=pricesearch")
    ),
    RichMenuArea(
        bounds=RichMenuBounds(x=1000, y=80, width=800, height=800),
        action=URIAction(label="交易", uri=f"{base_url}/?target=trade")
    ),
    RichMenuArea(
        bounds=RichMenuBounds(x=0, y=900, width=700, height=700),
        action=URIAction(label="追蹤清單", uri=f"{base_url}/?target=followlist")
    ),
    RichMenuArea(
        bounds=RichMenuBounds(x=900, y=900, width=700, height=700),
        action=URIAction(label="損益表", uri=f"{base_url}/?target=pnlbalance")
    ),
    RichMenuArea(
        bounds=RichMenuBounds(x=1700, y=900, width=700, height=700),
        action=URIAction(label="重置", uri=f"{base_url}/?target=reset")
    ),
]

rich_menu = RichMenu(
    size=RichMenuSize(width=2500, height=1686),
    selected=True,
    name="default",
    chat_bar_text="功能選單",
    areas=areas
)

try:
    print("🧹 清除舊 Rich Menu...")
    menus = line_bot_api.get_rich_menu_list()
    for m in menus:
        print("🗑️ 刪除 Rich Menu：", m.rich_menu_id)
        line_bot_api.delete_rich_menu(m.rich_menu_id)

    rich_menu_id = line_bot_api.create_rich_menu(rich_menu)
    print("✅ Rich Menu 建立成功：", rich_menu_id)

    with open(os.path.join(BASE_DIR, "richmenu.png"), "rb") as f:
        line_bot_api.set_rich_menu_image(rich_menu_id, "image/png", f)
    print("🖼️ 圖片上傳成功")

    line_bot_api.set_default_rich_menu(rich_menu_id)
    print("✅ 設為預設 Rich Menu")

except LineBotApiError as e:
    print("❌ 發生錯誤：", e)
