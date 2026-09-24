import requests
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from datetime import datetime
import schedule
import time
import os
import sys
from dotenv import load_dotenv

#  資料庫連線（從 pwd.env 讀取）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, "pwd.env"))
DB_URL = URL.create(
    "mysql+pymysql",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", 3306)),
    database=os.getenv("DB_NAME"),
    query={"charset": "utf8mb4"},
)
engine = create_engine(DB_URL, pool_pre_ping=True)

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
VS_CURRENCY = "usd"


#  從 coin_list 讀取要追蹤的幣種：coin_name 為 CoinGecko ID，coin_id 為代號
#  管理員在後台新增的幣種，下一次排程就會自動開始抓價
def load_coin_symbol_map(conn):
    rows = conn.execute(text("SELECT coin_id, coin_name FROM coin_list")).fetchall()
    return {coin_name: coin_id for coin_id, coin_name in rows if coin_name}


#  幣價抓取與寫入
def fetch_and_save():
    now = datetime.now().replace(second=0, microsecond=0)

    try:
        with engine.connect() as conn:
            coin_symbol_map = load_coin_symbol_map(conn)
    except Exception as e:
        print(f"[{now}]  讀取幣種清單失敗：{e}", flush=True)
        return

    if not coin_symbol_map:
        print(f"[{now}]  coin_list 沒有任何幣種，略過", flush=True)
        return

    params = {
        'ids': ','.join(coin_symbol_map.keys()),
        'vs_currencies': VS_CURRENCY,
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; BiliBiliCoin/1.0)'
    }

    try:
        response = requests.get(COINGECKO_URL, params=params, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f" API 錯誤 {response.status_code}：{response.text}", flush=True)
            return
        data = response.json()
    except Exception as e:
        print(f" 發生 API 錯誤：{e}", flush=True)
        return

    try:
        with engine.begin() as conn:  #  使用單一交易連線
            for coin, symbol in coin_symbol_map.items():
                if coin not in data or VS_CURRENCY not in data[coin]:
                    print(f"[{now}]  API 未回傳 {coin}，略過", flush=True)
                    continue
                price = data[coin][VS_CURRENCY]

                #  更新或插入 price 資料
                conn.execute(text("""
                    INSERT INTO price (coin_id, price, update_time)
                    VALUES (:coin_id, :price, :update_time)
                    ON DUPLICATE KEY UPDATE
                        price = VALUES(price),
                        update_time = VALUES(update_time)
                """), {'coin_id': symbol, 'price': price, 'update_time': now})

                # 新增一筆至 price_history（同一分鐘重複執行時忽略）
                conn.execute(text("""
                    INSERT IGNORE INTO price_history (coin_id, price, receiving_time)
                    VALUES (:coin_id, :price, :receiving_time)
                """), {'coin_id': symbol, 'price': price, 'receiving_time': now})

                print(f"[{now}]  Inserted/Updated: {symbol}, Price: {price}", flush=True)
    except Exception as e:
        print(f"[{now}]  寫入失敗：{e}", flush=True)
        with open(os.path.join(BASE_DIR, "error_log.txt"), "a", encoding="utf-8") as f:
            f.write(f"[{now}] Global insert error: {e}\n")


if __name__ == "__main__":
    #  測試資料庫連線
    try:
        with engine.connect():
            print(" 成功連接到資料庫！", flush=True)
    except Exception as e:
        print(f" 資料庫連線失敗：{e}", flush=True)
        sys.exit(1)

    #  立即執行一次
    fetch_and_save()

    #  每 5 分鐘排程
    schedule.every(5).minutes.do(fetch_and_save)

    print(" 開始監控中，每 5 分鐘更新幣價...", flush=True)

    while True:
        schedule.run_pending()
        time.sleep(1)
