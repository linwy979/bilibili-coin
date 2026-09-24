from datetime import datetime
import pytest

import main as admin_main
from admin import db

UID = "U_admin_view_user"


@pytest.fixture
def client():
    admin_main.app.config["TESTING"] = True
    with admin_main.app.app_context():
        db.session.remove()
    admin_main.init_admin()
    return admin_main.app.test_client()


def login(c, account="admin", password="S3cure!pw"):
    return c.post("/admin/login", data={"account": account, "password": password}, follow_redirects=True)


def text(resp):
    return resp.get_data(as_text=True)


def test_default_admin_password_is_hashed(client, sql):
    stored = sql("SELECT password, level FROM ROOT WHERE account='admin'")[0]
    assert stored["password"].startswith(("pbkdf2:", "scrypt:")) and stored["level"] == 2


def test_login(client):
    assert "帳號或密碼錯誤" in text(login(client, password="wrong"))
    assert "帳號或密碼錯誤" in text(login(client, account="ghost"))
    r = login(client)
    assert "登入成功" in text(r) and "管理管理員" in text(r)


def test_legacy_plaintext_password_still_works(client, sql):
    sql("INSERT INTO ROOT VALUES ('old', 'plain123', 1)")
    assert "登入成功" in text(login(client, "old", "plain123"))


def test_pages_require_login(client):
    r = client.get("/admin/cryptos")
    assert r.status_code == 302 and "/admin/login" in r.headers["Location"]


def test_open_redirect_blocked(client):
    r = client.post("/admin/login", data={"account": "admin", "password": "S3cure!pw", "next": "//evil.com"})
    assert r.headers["Location"].endswith("/admin/dashboard")


def test_crypto_crud(client, sql):
    login(client)
    client.post("/admin/cryptos/add", data={"symbol": "ada", "name": "cardano"})
    assert sql("SELECT coin_name FROM coin_list WHERE coin_id='ADA'")[0]["coin_name"] == "cardano"

    page = text(client.get("/admin/cryptos/edit/ADA"))
    assert 'value="ADA"' in page and 'value="cardano"' in page  # 原本的 bug：欄位是空的

    client.post("/admin/cryptos/edit/ADA", data={"symbol": "ADA2", "name": "cardano"})
    assert sql("SELECT coin_id FROM coin_list WHERE coin_id='ADA2'")

    sql("INSERT INTO price VALUES ('ADA2', 0.7, NOW())")
    client.post("/admin/cryptos/delete/ADA2")
    assert not sql("SELECT * FROM coin_list WHERE coin_id='ADA2'")
    assert not sql("SELECT * FROM price WHERE coin_id='ADA2'")


def test_cannot_rename_or_delete_coin_in_use(client, sql):
    login(client)
    sql("INSERT INTO user_list VALUES (%s, 1)", (UID,))
    sql("INSERT INTO history_trade (user_id, coin_id, quantity, price, action, trade_time) VALUES (%s,'BTC',1,100000,'buy',NOW())", (UID,))
    r = client.post("/admin/cryptos/delete/BTC", follow_redirects=True)
    assert "無法刪除" in text(r) and sql("SELECT * FROM coin_list WHERE coin_id='BTC'")
    r = client.post("/admin/cryptos/edit/BTC", data={"symbol": "XBT", "name": "bitcoin"}, follow_redirects=True)
    assert "無法修改符號" in text(r)


def test_view_and_delete_user(client, sql):
    login(client)
    sql("INSERT INTO user_list VALUES (%s, 4899899.5)", (UID,))
    sql("INSERT INTO follow_list VALUES (%s, 'ETH')", (UID,))
    sql("INSERT INTO history_trade (user_id, coin_id, quantity, price, action, trade_time) VALUES (%s,'BTC',1,100000,'buy',%s)",
        (UID, datetime(2025, 6, 3, 12, 0, 0)))

    users_page = text(client.get("/admin/users"))
    assert UID in users_page and "4,899,899.50" in users_page

    r = client.get(f"/admin/users/view/{UID}")  # 原本的 bug：inv.amount 不存在
    assert r.status_code == 200
    page = text(r)
    assert "Bitcoin (BTC)" in page and "100,000.00" in page and "Ethereum (ETH)" in page

    client.post(f"/admin/users/delete/{UID}")  # 原本會因外鍵失敗
    assert not sql("SELECT * FROM user_list WHERE user_id=%s", (UID,))
    assert not sql("SELECT * FROM history_trade WHERE user_id=%s", (UID,))


def test_admin_management(client, sql):
    login(client)
    client.post("/admin/register", data={"account": "helper", "password": "pw1", "confirm_password": "pw1", "level": "1"})
    helper = sql("SELECT password, level FROM ROOT WHERE account='helper'")[0]
    assert helper["level"] == 1 and helper["password"].startswith(("pbkdf2:", "scrypt:"))

    client.post("/admin/register", data={"account": "x", "password": "a", "confirm_password": "b", "level": "1"})
    assert not sql("SELECT * FROM ROOT WHERE account='x'")

    helper_client = admin_main.app.test_client()
    login(helper_client, "helper", "pw1")
    r = helper_client.get("/admin/manage_admins", follow_redirects=True)
    assert "只有二級管理員" in text(r)

    client.post("/admin/delete_admin/admin")  # 不能刪自己
    client.post("/admin/delete_admin/helper")
    assert [r["account"] for r in sql("SELECT account FROM ROOT")] == ["admin"]
