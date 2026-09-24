from flask import Flask, redirect, url_for
from sqlalchemy.engine import URL
from admin import admin_bp, db, AdminUser, hash_password
from dotenv import load_dotenv
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 讀取 .env（以本檔所在目錄為準，不受啟動位置影響）
load_dotenv(dotenv_path=os.path.join(BASE_DIR, "get.env"))

# 初始化 Flask app
app = Flask(__name__, template_folder='templates')
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")

# 設定資料庫連線資訊
app.config['SQLALCHEMY_DATABASE_URI'] = URL.create(
    "mysql+pymysql",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", 3306)),
    database=os.getenv("DB_NAME"),
    query={"charset": "utf8mb4"},
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"pool_pre_ping": True}

db.init_app(app)

# 初始化管理員帳號（依 get.env 建立二級管理員，密碼以雜湊儲存）
def init_admin():
    account = os.getenv("ADMIN_ACCOUNT")
    password = os.getenv("ADMIN_PASSWORD")
    if not account or not password:
        print("ℹ️ 未設定 ADMIN_ACCOUNT / ADMIN_PASSWORD，略過建立預設管理員")
        return

    with app.app_context():
        try:
            if AdminUser.query.filter_by(account=account).first():
                print("ℹ️ 管理員帳號已存在")
                return
            db.session.add(AdminUser(account=account, password=hash_password(password), level=2))
            db.session.commit()
            print("✅ 成功建立預設管理員帳號")
        except Exception as e:
            print("⚠️ 建立帳號錯誤：", e)
            db.session.rollback()

# 註冊後台 blueprint
app.register_blueprint(admin_bp)

@app.route("/")
def index():
    return redirect(url_for("admin.dashboard"))

# 啟動主程式（使用 5001，避免與主後端 app.py 的 5000 衝突）
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    init_admin()
    app.run(port=int(os.getenv("ADMIN_PORT", 5001)), debug=os.getenv("FLASK_DEBUG") == "1")
