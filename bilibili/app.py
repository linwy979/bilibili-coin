from flask import Flask, request, redirect, jsonify, send_from_directory, session
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from flask_session import Session
from linebot.models import FollowEvent, MessageEvent, TextSendMessage
from contextlib import contextmanager
import pymysql
import os
from dotenv import load_dotenv
from threading import Timer
from datetime import datetime
from flask_cors import CORS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 載入 .env 檔（以本檔所在目錄為準，不受啟動位置影響）
load_dotenv(dotenv_path=os.path.join(BASE_DIR, "pwd.env"))

INITIAL_BALANCE = 5000000  # 初始模擬資金
FEE_RATE = 0.001           # 手續費 0.1%
ALERT_THRESHOLD = 0.05     # 漲跌幅通知門檻 5%

DIST_DIR = os.path.join(BASE_DIR, "dist")  # React 建置產物

# 初始化 Flask app（靜態檔由最下方的 serve_react 統一處理）
bilibili = Flask(__name__, static_folder=None)
CORS(bilibili, supports_credentials=True)


# ✅ 開啟 session 支援
bilibili.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")
bilibili.config["SESSION_TYPE"] = "filesystem"
bilibili.config["SESSION_FILE_DIR"] = os.path.join(BASE_DIR, "flask_session")
Session(bilibili)
# LINE BOT 初始化
line_bot_api = LineBotApi(os.getenv("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("CHANNEL_SECRET"))


# 資料庫連線
def get_conn():
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

# 取得 cursor，離開 with 區塊時自動關閉連線；發生例外時自動 rollback
@contextmanager
def db_cursor():
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            yield conn, cursor
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def get_rich_menu_id_by_name(target_name):
    menus = line_bot_api.get_rich_menu_list()
    for menu in menus:
        if menu.name == target_name:
            return menu.rich_menu_id
    return None

# ✅ 輔助函式：從網址補 session 中的 uid
def get_user_id():
    user_id = session.get("uid")
    if not user_id:
        user_id = request.args.get("user_id", "").strip()
        if user_id:
            session["uid"] = user_id
            print(" 從網址取得 user_id 並寫入 session：", user_id)
    return user_id

# 輔助函式：把輸入轉成正數，無效時回傳 None
def parse_positive(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


@bilibili.route("/set_uid", methods=["POST"])
def set_uid():
    data = request.get_json(silent=True)
    if not data or not str(data.get("uid", "")).strip():
        print(" 錯誤：set_uid 接收到空資料或缺少 uid")
        return jsonify({"error": "missing uid"}), 400

    uid = str(data["uid"]).strip()
    session["uid"] = uid
    print(" 設定 session 中的 UID：", uid)
    return jsonify({"msg": "success"})

# 接收 LINE Webhook 的主路由
# ✅ LINE Webhook：處理事件，包括 FollowEvent
@bilibili.route("/webhook", methods=["POST"])
def callback():
    body = request.get_data(as_text=True)
    signature = request.headers.get("X-Line-Signature", "")
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print(" Webhook 簽章驗證失敗")
        return "Invalid signature", 400
    except Exception as e:
        print(" Webhook 處理失敗：", e)
    return "OK"

@handler.add(FollowEvent)
def handle_follow(event):
    user_id = event.source.user_id
    print(" 新使用者加入：", user_id)

    with db_cursor() as (conn, cursor):
        cursor.execute(
            "INSERT IGNORE INTO user_list (user_id, balance) VALUES (%s, %s)",
            (user_id, INITIAL_BALANCE)
        )
        conn.commit()

    rich_menu_id = get_rich_menu_id_by_name("default")
    if rich_menu_id:
        line_bot_api.link_rich_menu_to_user(user_id, rich_menu_id)
        print(" Rich Menu 綁定成功")

    entry_url = f"{os.getenv('PUBLIC_URL')}/#/?user_id={user_id}"
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=f"歡迎加入幣哩幣哩 \n請點選以下網址或下方按鈕開啟功能選單：\n{entry_url}")
    )


# 使用者傳訊息事件
@handler.add(MessageEvent)
def handle_text(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="請點選以下按鈕選擇要使用的功能")
    )


# 主路由：追蹤清單頁（顯示 + 新增 + 移除）
@bilibili.route("/follow_list", methods=["GET", "POST"])
def follow_list():
    user_id = get_user_id()
    if not user_id:
        return jsonify({"error": "請提供 user_id"}), 400

    if request.method == "POST":
        action = request.form.get("action")
        coin_id = request.form.get("coin_id")
        if action not in ("add", "remove") or not coin_id:
            return jsonify({"error": "參數錯誤"}), 400

        try:
            with db_cursor() as (conn, cursor):
                if action == "add":
                    cursor.execute(
                        "INSERT IGNORE INTO follow_list (user_id, coin_id) VALUES (%s, %s)",
                        (user_id, coin_id)
                    )
                else:
                    cursor.execute(
                        "DELETE FROM follow_list WHERE user_id = %s AND coin_id = %s",
                        (user_id, coin_id)
                    )
                conn.commit()
            return redirect(f"/follow_list?user_id={user_id}")
        except Exception as e:
            print("POST 操作失敗：", e)
            return jsonify({"error": "資料庫錯誤"}), 500

    # GET 方法：查詢追蹤清單
    try:
        with db_cursor() as (conn, cursor):
            cursor.execute("""
                SELECT c.coin_id, c.coin_name, p.price
                FROM follow_list f
                JOIN coin_list c ON f.coin_id = c.coin_id
                LEFT JOIN price p ON c.coin_id = p.coin_id
                WHERE f.user_id = %s
            """, (user_id,))
            tracked = cursor.fetchall()

            cursor.execute("""
                SELECT coin_id, coin_name
                FROM coin_list
                WHERE coin_id NOT IN (
                    SELECT coin_id FROM follow_list WHERE user_id = %s
                )
            """, (user_id,))
            untracked = cursor.fetchall()

        return jsonify({
            "tracked": tracked,
            "untracked": untracked,
            "user_id": user_id
        })
    except Exception as e:
        print(" 查詢失敗：", e)
        return jsonify({"error": "伺服器錯誤"}), 500


#漲跌幅通知設定
def check_price_fluctuations():
    with db_cursor() as (conn, cursor):
        cursor.execute("""
            SELECT f.user_id, f.coin_id,
                   p_now.price AS current_price,
                   p_prev.price AS previous_price
            FROM follow_list f
            JOIN price p_now ON f.coin_id = p_now.coin_id
            JOIN price_history p_prev ON f.coin_id = p_prev.coin_id
            WHERE p_prev.receiving_time = (
                SELECT MAX(receiving_time)
                FROM price_history
                WHERE coin_id = f.coin_id AND receiving_time <= NOW() - INTERVAL 5 MINUTE
            )
        """)
        results = cursor.fetchall()

    for row in results:
        now = row["current_price"]
        before = row["previous_price"]
        if not before: continue  # 避免除以 0

        change = (now - before) / before
        if abs(change) >= ALERT_THRESHOLD:
            percent = round(change * 100, 2)
            msg = f"{row['coin_id']} 在 5 分鐘內漲跌 {percent}%（由 {before} → {now}）"
            line_bot_api.push_message(row["user_id"], TextSendMessage(text=msg))

#將用不到的資料刪除
def clean_old_history():
    with db_cursor() as (conn, cursor):
        cursor.execute("""
            DELETE FROM price_history
            WHERE receiving_time < NOW() - INTERVAL 8 DAY
        """)
        conn.commit()

# 價格歷史由 coinapi.py 寫入，這裡只負責通知與清理
def schedule_price_check():
    try:
        check_price_fluctuations()
        clean_old_history()
    except Exception as e:
        print(" 排程執行失敗：", e)
    finally:
        timer = Timer(300, schedule_price_check)  # 每 5 分鐘執行一次
        timer.daemon = True
        timer.start()

#獲取及時幣價
@bilibili.route("/api/current_prices", methods=["GET"])
def current_prices():
    with db_cursor() as (conn, cursor):
        cursor.execute("SELECT coin_id, price FROM price")
        return jsonify(cursor.fetchall())

#趨勢圖
@bilibili.route("/api/price_history/<coin_id>")
def get_price_history(coin_id):
    chart_type = request.args.get("type", "1d")  # 預設為 1 天
    day_map = {"1d": 1, "3d": 3, "7d": 7}
    days = day_map.get(chart_type)

    if not days:
        return jsonify({"error": "圖表類型不支援"}), 400

    try:
        with db_cursor() as (conn, cursor):
            cursor.execute("""
                SELECT receiving_time AS label, price
                FROM price_history
                WHERE coin_id = %s AND receiving_time >= NOW() - INTERVAL %s DAY
                ORDER BY receiving_time ASC
            """, (coin_id, days))
            return jsonify(cursor.fetchall())
    except Exception as e:
        print(" price_history 查詢失敗：", e)
        return jsonify({"error": "查詢失敗"}), 500


# 顯示所有幣種清單（供交易用的下拉選單使用）
@bilibili.route("/api/coin_list", methods=["GET"])
def coin_list():
    with db_cursor() as (conn, cursor):
        cursor.execute("SELECT coin_id, coin_name FROM coin_list")
        return jsonify(cursor.fetchall())


# 查詢目前持有數量（買入總量 − 賣出總量）
def get_holding(cursor, user_id, coin_id):
    cursor.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN action = 'buy' THEN quantity ELSE 0 END), 0) -
            COALESCE(SUM(CASE WHEN action = 'sell' THEN quantity ELSE 0 END), 0) AS quantity
        FROM history_trade
        WHERE user_id = %s AND coin_id = %s
    """, (user_id, coin_id))
    return float(cursor.fetchone()["quantity"])


# 查詢目前餘額 + 幣價（GET）執行交易時要確認目前餘額以及獲取即時幣價
@bilibili.route("/api/trade_info", methods=["GET"])
def get_trade_info():
    user_id = get_user_id()
    coin_id = request.args.get("coin_id")

    with db_cursor() as (conn, cursor):
        # 查餘額
        cursor.execute("SELECT balance FROM user_list WHERE user_id = %s", (user_id,))
        balance_data = cursor.fetchone()
        balance = balance_data["balance"] if balance_data else 0

        # 查幣價
        price = None
        if coin_id:
            cursor.execute("SELECT price FROM price WHERE coin_id = %s", (coin_id,))
            price_data = cursor.fetchone()
            price = price_data["price"] if price_data else None

    return jsonify({
        "balance": round(balance, 2),
        # 低價幣（如 DOGE）需要保留更多小數位
        "coin_price": round(price, 6) if price else None
    })


# 執行交易（POST）
@bilibili.route("/api/trade", methods=["POST"])
def trade():
    data = request.get_json(silent=True) or {}
    user_id = get_user_id()
    coin_id = data.get("coin_id")
    action = data.get("action")  # 'buy' 或 'sell'

    if not user_id:
        return jsonify({"status": "fail", "reason": "請提供 user_id"}), 400
    if action not in ("buy", "sell"):
        return jsonify({"status": "fail", "reason": "操作無效"}), 400

    # 優先使用數量；未填數量時才用金額換算
    quantity = parse_positive(data.get("quantity"))
    total = parse_positive(data.get("total"))
    if quantity is None and total is None:
        return jsonify({"status": "fail", "reason": "請輸入大於 0 的數量或金額"}), 400

    try:
        with db_cursor() as (conn, cursor):
            # 查價格
            cursor.execute("SELECT price FROM price WHERE coin_id = %s", (coin_id,))
            price_data = cursor.fetchone()
            if not price_data or not price_data["price"]:
                return jsonify({"status": "fail", "reason": "幣種不存在"}), 400
            price = price_data["price"]

            if quantity is None:
                quantity = total / price

            # 查使用者餘額，鎖定該列避免同時交易造成餘額錯誤
            cursor.execute("SELECT balance FROM user_list WHERE user_id = %s FOR UPDATE", (user_id,))
            user_data = cursor.fetchone()
            if not user_data:
                return jsonify({"status": "fail", "reason": "使用者不存在"}), 400
            balance = user_data["balance"]

            if action == "buy":
                real_total = quantity * price * (1 + FEE_RATE)
                if real_total > balance:
                    return jsonify({"status": "fail", "reason": "餘額不足"}), 400
                new_balance = balance - real_total
            else:
                holding = get_holding(cursor, user_id, coin_id)
                # 容許浮點誤差，避免「全部賣出」時因小數位差異被拒絕
                if quantity > holding + 1e-9:
                    return jsonify({"status": "fail", "reason": "持有數量不足"}), 400
                quantity = min(quantity, holding)
                real_total = quantity * price * (1 - FEE_RATE)
                new_balance = balance + real_total

            # 更新餘額與記錄交易
            cursor.execute("UPDATE user_list SET balance = %s WHERE user_id = %s", (new_balance, user_id))
            cursor.execute("""
                INSERT INTO history_trade (user_id, coin_id, action, quantity, price, trade_time)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (user_id, coin_id, action, quantity, price, datetime.now()))
            conn.commit()
    except pymysql.err.IntegrityError:
        # history_trade 以 (user_id, coin_id, trade_time) 為主鍵，同一秒重複下單會衝突
        return jsonify({"status": "fail", "reason": "交易過於頻繁，請稍後再試"}), 429

    return jsonify({
        "status": "success",
        "action": action,
        "quantity": round(quantity, 6),
        "total": round(real_total, 2),
        "new_balance": round(new_balance, 2)
    })

#餘額損益表查詢
@bilibili.route("/api/profit", methods=["GET"])
def get_profit():
    user_id = get_user_id()

    with db_cursor() as (conn, cursor):
        # 1. 查餘額
        cursor.execute("SELECT balance FROM user_list WHERE user_id = %s", (user_id,))
        balance_data = cursor.fetchone()
        balance = balance_data["balance"] if balance_data else 0

        # 2. 查交易紀錄彙總與最新市價
        cursor.execute("""
            SELECT
                t.coin_id,
                p.price AS current_price,
                SUM(CASE WHEN t.action = 'buy' THEN t.quantity ELSE 0 END) AS total_buy_qty,
                SUM(CASE WHEN t.action = 'buy' THEN t.quantity * t.price * %s ELSE 0 END) AS total_buy_cost,
                SUM(CASE WHEN t.action = 'sell' THEN t.quantity ELSE 0 END) AS total_sell_qty,
                SUM(CASE WHEN t.action = 'sell' THEN t.quantity * t.price * %s ELSE 0 END) AS total_sell_income
            FROM history_trade t
            LEFT JOIN price p ON t.coin_id = p.coin_id
            WHERE t.user_id = %s
            GROUP BY t.coin_id, p.price
        """, (1 + FEE_RATE, 1 - FEE_RATE, user_id))
        trades = cursor.fetchall()

    portfolio = []

    total_market_value = 0
    total_buy_cost = 0
    total_sell_income = 0
    total_net_profit = 0

    for row in trades:
        total_buy_qty = row["total_buy_qty"] or 0
        total_sell_qty = row["total_sell_qty"] or 0
        quantity = total_buy_qty - total_sell_qty

        if quantity <= 1e-9:
            continue  #  不顯示已清空的幣

        buy_cost = row["total_buy_cost"] or 0
        sell_income = row["total_sell_income"] or 0
        average_cost = (buy_cost / total_buy_qty) if total_buy_qty > 0 else 0
        current_price = row["current_price"] or 0

        market_value = quantity * current_price
        net_profit = market_value + sell_income - buy_cost

        total_market_value += market_value
        total_buy_cost += buy_cost
        total_sell_income += sell_income
        total_net_profit += net_profit

        portfolio.append({
            "coin_id": row["coin_id"],
            "quantity": round(quantity, 6),
            "average_buy_cost": round(average_cost, 6),
            "current_price": round(current_price, 6),
            "net_profit": round(net_profit, 2)
        })

    total_return_rate = (total_net_profit / total_buy_cost) * 100 if total_buy_cost > 0 else 0

    return jsonify({
        "balance": round(balance, 2),
        "portfolio": portfolio,
        "summary": {
            "total_market_value": round(total_market_value, 2),
            "total_buy_cost": round(total_buy_cost, 2),
            "total_sell_income": round(total_sell_income, 2),
            "total_net_profit": round(total_net_profit, 2),
            "total_return_rate": round(total_return_rate, 2)  # %
        }
    })

#reset balance

@bilibili.route("/api/reset", methods=["POST"])
def reset_user():
    user_id = get_user_id()
    print("[後端] 收到重置請求，user_id：", user_id)

    if not user_id:
        return jsonify({"error": "請提供 user_id"}), 400

    try:
        with db_cursor() as (conn, cursor):
            # 刪除該使用者的所有交易紀錄
            cursor.execute("DELETE FROM history_trade WHERE user_id = %s", (user_id,))

            # 將使用者的餘額重設為初始資金
            cursor.execute("UPDATE user_list SET balance = %s WHERE user_id = %s", (INITIAL_BALANCE, user_id))

            conn.commit()
        return jsonify({"message": "已成功重置模擬投資帳號", "balance": INITIAL_BALANCE}), 200

    except Exception as e:
        print(" reset_user 錯誤：", e)
        return jsonify({"error": "重置失敗，請稍後再試"}), 500

@bilibili.route("/", defaults={"path": ""})
@bilibili.route("/<path:path>")
def serve_react(path):
    # 如果是靜態資源（js, css, png...）就直接回傳
    if path != "" and os.path.isfile(os.path.join(DIST_DIR, path)):
        return send_from_directory(DIST_DIR, path)
    # 否則一律送出 index.html（給 React 前端路由用）
    return send_from_directory(DIST_DIR, "index.html")

# 執行 Flask
if __name__ == "__main__":
    schedule_price_check()
    bilibili.run(host="0.0.0.0", port=5000)
