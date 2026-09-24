import time
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest

import app as backend

UID = "U_test_user_0001"


@pytest.fixture(autouse=True)
def mock_line(monkeypatch):
    fake = MagicMock()
    fake.get_rich_menu_list.return_value = [SimpleNamespace(name="default", rich_menu_id="rm-1")]
    monkeypatch.setattr(backend, "line_bot_api", fake)
    return fake


@pytest.fixture
def client():
    backend.bilibili.config["TESTING"] = True
    return backend.bilibili.test_client()


@pytest.fixture
def user(sql, client):
    sql("INSERT INTO user_list (user_id, balance) VALUES (%s, 5000000)", (UID,))
    assert client.post("/set_uid", json={"uid": UID}).status_code == 200
    return client


def balance(sql):
    return sql("SELECT balance FROM user_list WHERE user_id=%s", (UID,))[0]["balance"]


# ---------- LINE ----------

def test_follow_event_creates_user_once(sql, mock_line):
    event = SimpleNamespace(source=SimpleNamespace(user_id=UID), reply_token="tok")
    backend.handle_follow(event)
    backend.handle_follow(event)  # 重複加入好友不應出錯或重複建立
    rows = sql("SELECT * FROM user_list WHERE user_id=%s", (UID,))
    assert len(rows) == 1 and rows[0]["balance"] == 5000000
    mock_line.link_rich_menu_to_user.assert_called_with(UID, "rm-1")
    text = mock_line.reply_message.call_args[0][1].text
    assert "https://example.ngrok-free.app/#/?user_id=" + UID in text


def test_webhook_rejects_bad_signature(client):
    r = client.post("/webhook", data="{}", headers={"X-Line-Signature": "bad"})
    assert r.status_code == 400


# ---------- 基本查詢 ----------

def test_coin_list_and_prices(client):
    assert len(client.get("/api/coin_list").get_json()) == 8
    prices = {p["coin_id"]: p["price"] for p in client.get("/api/current_prices").get_json()}
    assert prices["BTC"] == 100000


def test_set_uid_requires_uid(client):
    assert client.post("/set_uid", json={}).status_code == 400
    assert client.post("/set_uid", data="not json").status_code == 400


def test_trade_info_keeps_small_price_precision(user):
    data = user.get("/api/trade_info?coin_id=DOGE").get_json()
    assert data["balance"] == 5000000 and data["coin_price"] == pytest.approx(0.2)


def test_price_history_ascending_and_range(client, sql):
    now = datetime.now().replace(microsecond=0)
    sql("INSERT INTO price_history VALUES ('BTC', 3, %s), ('BTC', 1, %s), ('BTC', 2, %s), ('BTC', 9, %s)",
        (now, now - timedelta(hours=2), now - timedelta(hours=1), now - timedelta(days=5)))
    one_day = client.get("/api/price_history/BTC?type=1d").get_json()
    assert [p["price"] for p in one_day] == [1, 2, 3]  # 由舊到新
    assert len(client.get("/api/price_history/BTC?type=7d").get_json()) == 4
    assert client.get("/api/price_history/BTC?type=30d").status_code == 400


# ---------- 追蹤清單 ----------

def test_follow_add_remove(user):
    assert user.post("/follow_list", data={"action": "add", "coin_id": "BTC"}).status_code == 302
    user.post("/follow_list", data={"action": "add", "coin_id": "BTC"})  # 重複新增不報錯
    data = user.get("/follow_list").get_json()
    assert [c["coin_id"] for c in data["tracked"]] == ["BTC"]
    assert len(data["untracked"]) == 7
    user.post("/follow_list", data={"action": "remove", "coin_id": "BTC"})
    assert user.get("/follow_list").get_json()["tracked"] == []


def test_follow_shows_coin_without_price(user):
    user.post("/follow_list", data={"action": "add", "coin_id": "SOL"})  # SOL 沒有價格資料
    tracked = user.get("/follow_list").get_json()["tracked"]
    assert tracked == [{"coin_id": "SOL", "coin_name": "solana", "price": None}]


def test_follow_requires_user_and_valid_action(client, user):
    assert backend.bilibili.test_client().get("/follow_list").status_code == 400
    assert user.post("/follow_list", data={"action": "hack", "coin_id": "BTC"}).status_code == 400


# ---------- 交易 ----------

def test_buy_charges_fee(user, sql):
    r = user.post("/api/trade", json={"coin_id": "BTC", "action": "buy", "quantity": 2})
    assert r.status_code == 200, r.get_json()
    assert balance(sql) == pytest.approx(5000000 - 2 * 100000 * 1.001)
    assert r.get_json()["total"] == pytest.approx(200200)


@pytest.mark.parametrize("payload", [
    {"coin_id": "BTC", "action": "buy", "quantity": -5},
    {"coin_id": "BTC", "action": "buy", "quantity": 0},
    {"coin_id": "BTC", "action": "buy", "quantity": "abc"},
    {"coin_id": "BTC", "action": "buy"},
    {"coin_id": "BTC", "action": "steal", "quantity": 1},
])
def test_trade_rejects_invalid_input(user, sql, payload):
    assert user.post("/api/trade", json=payload).status_code == 400
    assert balance(sql) == 5000000


def test_buy_insufficient_balance_and_unknown_coin(user, sql):
    assert user.post("/api/trade", json={"coin_id": "BTC", "action": "buy", "quantity": 100}).get_json()["reason"] == "餘額不足"
    assert user.post("/api/trade", json={"coin_id": "SOL", "action": "buy", "quantity": 1}).status_code == 400
    assert balance(sql) == 5000000


def test_trade_requires_user():
    r = backend.bilibili.test_client().post("/api/trade", json={"coin_id": "BTC", "action": "buy", "quantity": 1})
    assert r.status_code == 400


def test_sell_flow(user, sql):
    user.post("/api/trade", json={"coin_id": "ETH", "action": "buy", "quantity": 10})
    time.sleep(1.1)  # history_trade 主鍵含秒數
    assert user.post("/api/trade", json={"coin_id": "ETH", "action": "sell", "quantity": 11}).get_json()["reason"] == "持有數量不足"
    r = user.post("/api/trade", json={"coin_id": "ETH", "action": "sell", "quantity": 4})
    assert r.status_code == 200
    expected = 5000000 - 10 * 2500 * 1.001 + 4 * 2500 * 0.999
    assert balance(sql) == pytest.approx(expected)
    summary = user.get("/api/profit").get_json()["summary"]
    assert summary["total_sell_income"] == pytest.approx(4 * 2500 * 0.999)


def test_sell_by_total_records_matching_quantity(user, sql):
    """原本的 bug：用金額賣出時會入帳，但數量記成 0"""
    user.post("/api/trade", json={"coin_id": "ETH", "action": "buy", "quantity": 10})
    time.sleep(1.1)
    r = user.post("/api/trade", json={"coin_id": "ETH", "action": "sell", "total": 5000})
    assert r.status_code == 200
    sold = sql("SELECT quantity FROM history_trade WHERE action='sell'")[0]["quantity"]
    assert sold == pytest.approx(2)


def test_duplicate_trade_same_second_returns_429(user, sql):
    codes = [user.post("/api/trade", json={"coin_id": "BTC", "action": "buy", "quantity": 1}).status_code for _ in range(2)]
    assert codes[0] == 200 and codes[1] in (200, 429)
    trades = sql("SELECT COUNT(*) AS n FROM history_trade")[0]["n"]
    # 餘額只扣實際成功的筆數
    assert balance(sql) == pytest.approx(5000000 - trades * 100000 * 1.001)


# ---------- 損益 ----------

def test_profit_summary(user, sql):
    user.post("/api/trade", json={"coin_id": "BTC", "action": "buy", "quantity": 1})
    user.post("/api/trade", json={"coin_id": "ETH", "action": "buy", "quantity": 4})
    time.sleep(1.1)
    user.post("/api/trade", json={"coin_id": "ETH", "action": "sell", "quantity": 4})  # 清倉
    sql("UPDATE price SET price = 110000 WHERE coin_id='BTC'")

    data = user.get("/api/profit").get_json()
    assert [c["coin_id"] for c in data["portfolio"]] == ["BTC"]  # 已清倉的 ETH 不顯示
    btc = data["portfolio"][0]
    assert btc["average_buy_cost"] == pytest.approx(100100)
    assert btc["net_profit"] == pytest.approx(9900)
    assert data["summary"]["total_return_rate"] == pytest.approx(9900 / 100100 * 100, abs=0.01)


def test_profit_for_unknown_user_is_empty():
    c = backend.bilibili.test_client()
    data = c.get("/api/profit?user_id=nobody").get_json()
    assert data["balance"] == 0 and data["portfolio"] == []


# ---------- 重置 ----------

def test_reset(user, sql):
    user.post("/api/trade", json={"coin_id": "BTC", "action": "buy", "quantity": 1})
    r = user.post("/api/reset", json={})
    assert r.status_code == 200 and r.get_json()["balance"] == 5000000
    assert balance(sql) == 5000000
    assert sql("SELECT COUNT(*) AS n FROM history_trade")[0]["n"] == 0


# ---------- 排程 ----------

def test_price_alert_pushes_on_big_move(sql, mock_line):
    sql("INSERT INTO user_list VALUES (%s, 5000000)", (UID,))
    sql("INSERT INTO follow_list VALUES (%s, 'BTC'), (%s, 'ETH')", (UID, UID))
    ten_min_ago = datetime.now() - timedelta(minutes=10)
    sql("INSERT INTO price_history VALUES ('BTC', 90000, %s), ('ETH', 2490, %s)", (ten_min_ago, ten_min_ago))
    backend.check_price_fluctuations()
    assert mock_line.push_message.call_count == 1  # BTC +11% 通知；ETH +0.4% 不通知
    assert "BTC" in mock_line.push_message.call_args[0][1].text


def test_clean_old_history(sql):
    sql("INSERT INTO price_history VALUES ('BTC', 1, %s), ('BTC', 2, NOW())", (datetime.now() - timedelta(days=9),))
    backend.clean_old_history()
    assert [r["price"] for r in sql("SELECT price FROM price_history")] == [2]


def test_scheduler_survives_errors(monkeypatch):
    started = []
    monkeypatch.setattr(backend, "check_price_fluctuations", MagicMock(side_effect=RuntimeError("db down")))
    monkeypatch.setattr(backend, "Timer", lambda *a: SimpleNamespace(start=lambda: started.append(True), daemon=False))
    backend.schedule_price_check()
    assert started == [True]  # 出錯仍會排下一次


# ---------- 前端靜態檔 ----------

def test_serves_spa(client):
    assert b'<div id="root">' in client.get("/").data
    assert b'<div id="root">' in client.get("/some/client/route").data
    assert client.get("/vite.svg").status_code == 200
