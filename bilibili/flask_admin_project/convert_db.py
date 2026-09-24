"""資料庫初始化：建立資料庫並套用 database/schema.sql

用法：python convert_db.py
連線資訊讀取自同目錄的 get.env
"""
import os
import sys
import pymysql
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(BASE_DIR, "..", "..", "database", "schema.sql")

load_dotenv(dotenv_path=os.path.join(BASE_DIR, "get.env"))


def split_statements(sql):
    """去除註解後以分號切割 SQL 敘述"""
    lines = [line for line in sql.splitlines() if not line.strip().startswith("--")]
    return [stmt.strip() for stmt in "\n".join(lines).split(";") if stmt.strip()]


def setup_mysql_database():
    db_name = os.getenv("DB_NAME", "bilibili")
    try:
        conn = pymysql.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            charset="utf8mb4",
        )
    except pymysql.err.OperationalError as e:
        print(f"無法連線到 MySQL，請確認服務已啟動且 get.env 設定正確：{e}")
        sys.exit(1)

    try:
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4")
            cursor.execute(f"USE `{db_name}`")
            print(f"成功建立 / 選擇資料庫 {db_name}")

            with open(SCHEMA_PATH, encoding="utf-8") as f:
                for statement in split_statements(f.read()):
                    cursor.execute(statement)
        conn.commit()
        print("資料表建立完成！請執行 python main.py 啟動後台，系統會依 get.env 建立預設管理員。")
    except Exception as e:
        conn.rollback()
        print(f"設定資料庫時發生錯誤：{e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    setup_mysql_database()
