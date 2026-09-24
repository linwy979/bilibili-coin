import os
import sys
import subprocess
import pytest
import pymysql

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BILI = os.path.join(REPO, "bilibili")
ADMIN_DIR = os.path.join(BILI, "flask_admin_project")

# 整合測試需要一個可連線的 MySQL / MariaDB；會建立並清空 bilibili_test 資料庫
ENV = {
    "DB_HOST": os.getenv("TEST_DB_HOST", "127.0.0.1"),
    "DB_PORT": os.getenv("TEST_DB_PORT", "3306"),
    "DB_USER": os.getenv("TEST_DB_USER", "root"),
    "DB_PASSWORD": os.getenv("TEST_DB_PASSWORD", ""),
    "DB_NAME": "bilibili_test",
    "CHANNEL_ACCESS_TOKEN": "dummy-token",
    "CHANNEL_SECRET": "dummy-secret",
    "SECRET_KEY": "test-secret",
    "PUBLIC_URL": "https://example.ngrok-free.app",
    "ADMIN_ACCOUNT": "admin",
    "ADMIN_PASSWORD": "S3cure!pw",
}
os.environ.update(ENV)
sys.path[:0] = [BILI, ADMIN_DIR]


def raw_conn(db=True):
    return pymysql.connect(
        host=ENV["DB_HOST"], port=int(ENV["DB_PORT"]), user=ENV["DB_USER"],
        password=ENV["DB_PASSWORD"], database=ENV["DB_NAME"] if db else None,
        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor, autocommit=True,
    )


@pytest.fixture(scope="session", autouse=True)
def fresh_database():
    """用 convert_db.py 從零建立測試資料庫（同時驗證初始化腳本本身）"""
    with raw_conn(db=False) as c, c.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS {ENV['DB_NAME']}")
    result = subprocess.run(
        [sys.executable, os.path.join(ADMIN_DIR, "convert_db.py")],
        capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    yield


@pytest.fixture
def sql():
    def run(query, params=None):
        with raw_conn() as c, c.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()
    return run


@pytest.fixture(autouse=True)
def clean_tables(fresh_database):
    with raw_conn() as c, c.cursor() as cur:
        for t in ("history_trade", "follow_list", "price_history", "price", "user_list", "ROOT"):
            cur.execute(f"DELETE FROM {t}")
        cur.execute("DELETE FROM coin_list WHERE coin_id NOT IN ('BTC','ETH','USDT','XRP','BNB','SOL','USDC','DOGE')")
        cur.executemany(
            "INSERT INTO price (coin_id, price, update_time) VALUES (%s, %s, NOW())",
            [("BTC", 100000), ("ETH", 2500), ("DOGE", 0.2)],
        )
    yield
