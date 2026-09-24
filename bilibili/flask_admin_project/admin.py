from flask import Blueprint, render_template, request, redirect, url_for, flash, session as flask_session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = SQLAlchemy()

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

class AdminUser(db.Model):
    __tablename__ = 'ROOT'
    account = db.Column(db.String(50), primary_key=True)
    password = db.Column(db.String(255))
    level = db.Column(db.Integer, default=1)

    def __init__(self, account, password, level=1):
        self.account = account
        self.password = password
        self.level = level

class SupportedCrypto(db.Model):
    __tablename__ = 'coin_list'
    coin_id = db.Column(db.String(10), primary_key=True)
    coin_name = db.Column(db.String(50))

class User(db.Model):
    __tablename__ = 'user_list'
    user_id = db.Column(db.String(50), primary_key=True)
    balance = db.Column(db.Float, default=5000000)
    # 刪除使用者時一併刪除其交易紀錄與追蹤清單
    investments = db.relationship('Investment', backref='user', lazy=True, cascade='all, delete-orphan')
    tracking_list = db.relationship('TrackingItem', backref='user', lazy=True, cascade='all, delete-orphan')

class Investment(db.Model):
    __tablename__ = 'history_trade'
    user_id = db.Column(db.String(50), db.ForeignKey('user_list.user_id', ondelete='CASCADE'), primary_key=True)
    coin_id = db.Column(db.String(10), db.ForeignKey('coin_list.coin_id'), primary_key=True)
    trade_time = db.Column(db.DateTime, primary_key=True)
    quantity = db.Column(db.Float)
    price = db.Column(db.Float)
    action = db.Column(db.Enum('buy', 'sell'))

class TrackingItem(db.Model):
    __tablename__ = 'follow_list'
    user_id = db.Column(db.String(50), db.ForeignKey('user_list.user_id'), primary_key=True)
    coin_id = db.Column(db.String(10), db.ForeignKey('coin_list.coin_id'), primary_key=True)
    coin = db.relationship('SupportedCrypto', backref='tracking_items')

# 密碼雜湊；舊資料若仍為明文，登入時照樣可以比對
HASH_PREFIXES = ('pbkdf2:', 'scrypt:')

def hash_password(password):
    return generate_password_hash(password)

def verify_password(stored, given):
    if not stored:
        return False
    if stored.startswith(HASH_PREFIXES):
        return check_password_hash(stored, given)
    return stored == given

def get_db_session():
    return db.session

def get_admin_user_by_account(db_session, account):
    return db_session.query(AdminUser).filter_by(account=account).first()

def get_all_supported_cryptos_db(db_session):
    return db_session.query(SupportedCrypto).order_by(SupportedCrypto.coin_id).all()

def add_supported_crypto_db(db_session, symbol, name):
    try:
        if db_session.query(SupportedCrypto).filter_by(coin_id=symbol).first():
            raise ValueError(f"幣種符號 {symbol} 已存在。")
        new_crypto = SupportedCrypto(coin_id=symbol, coin_name=name)
        db_session.add(new_crypto)
        db_session.commit()
        return new_crypto
    except:
        db_session.rollback()
        raise

def get_supported_crypto_by_id_db(db_session, crypto_id):
    return db_session.query(SupportedCrypto).filter_by(coin_id=crypto_id).first()

# 計算幣種在各資料表中被引用的筆數
def count_coin_references(db_session, crypto_id):
    counts = {}
    for table in ('history_trade', 'follow_list', 'price', 'price_history'):
        counts[table] = db_session.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE coin_id = :coin_id"), {'coin_id': crypto_id}
        ).scalar()
    return counts

def update_supported_crypto_db(db_session, crypto_id, new_symbol, new_name):
    try:
        crypto = db_session.query(SupportedCrypto).filter_by(coin_id=crypto_id).first()
        if not crypto:
            return None
        if new_symbol != crypto_id:
            if db_session.query(SupportedCrypto).filter_by(coin_id=new_symbol).first():
                raise ValueError(f"幣種符號 {new_symbol} 已被其他幣種使用。")
            if any(count_coin_references(db_session, crypto_id).values()):
                raise ValueError("此幣種已有價格、追蹤或交易資料，無法修改符號，只能修改名稱。")
            crypto.coin_id = new_symbol
        crypto.coin_name = new_name
        db_session.commit()
        return crypto
    except:
        db_session.rollback()
        raise

def delete_supported_crypto_db(db_session, crypto_id):
    try:
        crypto = db_session.query(SupportedCrypto).filter_by(coin_id=crypto_id).first()
        if not crypto:
            return False
        if count_coin_references(db_session, crypto_id)['history_trade']:
            raise ValueError("仍有使用者持有或交易過此幣種，無法刪除。")
        # 價格與追蹤資料會隨幣種一併刪除
        for table in ('follow_list', 'price', 'price_history'):
            db_session.execute(text(f"DELETE FROM {table} WHERE coin_id = :coin_id"), {'coin_id': crypto_id})
        db_session.delete(crypto)
        db_session.commit()
        return True
    except:
        db_session.rollback()
        raise

def get_user_by_line_id_db(db_session, line_user_id):
    return db_session.query(User).filter_by(user_id=line_user_id).first()

def delete_user_db(db_session, line_user_id):
    try:
        user = db_session.query(User).filter_by(user_id=line_user_id).first()
        if user:
            db_session.delete(user)
            db_session.commit()
            return True
        return False
    except:
        db_session.rollback()
        raise

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_user_id' not in flask_session:
            flash('請先登入以訪問此頁面。', 'warning')
            return redirect(url_for('admin.login', next=request.full_path))
        return f(*args, **kwargs)
    return decorated_function

# 只有二級管理員可以操作的頁面
def level2_required(message):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            current_admin = get_admin_user_by_account(get_db_session(), flask_session.get('admin_account'))
            if not current_admin or current_admin.level != 2:
                flash(message, 'danger')
                return redirect(url_for('admin.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@admin_bp.route('/register', methods=['GET', 'POST'])
@login_required
@level2_required('只有二級管理員可以註冊新管理員帳號。')
def register():
    if request.method == 'POST':
        username = request.form.get('account', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        level = request.form.get('level', '1')

        if not username or not password:
            flash('請填寫所有欄位', 'danger')
            return redirect(url_for('admin.register'))

        if password != confirm_password:
            flash('兩次輸入的密碼不一致', 'danger')
            return redirect(url_for('admin.register'))

        if level not in ('1', '2'):
            flash('管理員等級不正確', 'danger')
            return redirect(url_for('admin.register'))

        db_session = get_db_session()
        try:
            if get_admin_user_by_account(db_session, username):
                flash('帳號已存在', 'danger')
                return redirect(url_for('admin.register'))

            db_session.add(AdminUser(account=username, password=hash_password(password), level=int(level)))
            db_session.commit()
            flash(f'管理員 {username} 註冊成功', 'success')
            return redirect(url_for('admin.manage_admins'))
        except Exception as e:
            db_session.rollback()
            logger.error(f"註冊錯誤: {e}")
            flash('註冊失敗，請稍後再試', 'danger')
            return redirect(url_for('admin.register'))

    return render_template('admin/register.html')

@admin_bp.route('/manage_admins')
@login_required
@level2_required('只有二級管理員可以管理其他管理員帳號。')
def manage_admins():
    admins = get_db_session().query(AdminUser).all()
    return render_template('admin/manage_admins.html', admins=admins)

@admin_bp.route('/delete_admin/<string:account>', methods=['POST'])
@login_required
@level2_required('只有二級管理員可以刪除其他管理員帳號。')
def delete_admin(account):
    db_session = get_db_session()
    try:
        if account == flask_session.get('admin_account'):
            flash('不能刪除自己的帳號。', 'danger')
            return redirect(url_for('admin.manage_admins'))

        admin_to_delete = get_admin_user_by_account(db_session, account)
        if not admin_to_delete:
            flash('找不到指定的管理員帳號。', 'danger')
        elif admin_to_delete.level == 2:
            flash('不能刪除二級管理員帳號。', 'danger')
        else:
            db_session.delete(admin_to_delete)
            db_session.commit()
            flash(f'管理員帳號 {account} 已成功刪除。', 'success')
    except Exception as e:
        db_session.rollback()
        logger.error(f"Delete admin error: {e}")
        flash('刪除管理員時發生錯誤。', 'danger')
    return redirect(url_for('admin.manage_admins'))

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        account = request.form.get('account', '').strip()
        password = request.form.get('password', '')
        next_page = request.form.get('next', '')

        if not account or not password:
            flash('請輸入帳號和密碼。', 'danger')
            return render_template('admin/login.html')

        try:
            admin = get_admin_user_by_account(get_db_session(), account)
        except Exception as e:
            logger.error(f"登入過程發生錯誤: {e}")
            flash('登入時發生錯誤，請稍後再試。', 'danger')
            return render_template('admin/login.html')

        # 帳號不存在與密碼錯誤顯示相同訊息，避免被探測帳號
        if admin is None or not verify_password(admin.password, password):
            logger.warning(f"登入失敗：{account}")
            flash('帳號或密碼錯誤。', 'danger')
            return render_template('admin/login.html')

        # 登入成功：寫入 session
        flask_session['admin_user_id'] = admin.account
        flask_session['admin_account'] = admin.account
        flask_session['admin_level'] = int(admin.level)
        logger.info(f"管理員 {admin.account} 登入成功")
        flash('登入成功!', 'success')

        # 只允許站內相對路徑，避免開放重新導向
        if next_page.startswith('/') and not next_page.startswith('//'):
            return redirect(next_page)
        return redirect(url_for('admin.dashboard'))

    return render_template('admin/login.html')


@admin_bp.route('/logout')
@login_required
def logout():
    flask_session.pop('admin_user_id', None)
    flask_session.pop('admin_account', None)
    flask_session.pop('admin_level', None)
    flash('您已成功登出。', 'info')
    return redirect(url_for('admin.login'))

@admin_bp.route('/')
def index():
    if 'admin_user_id' in flask_session:
        return redirect(url_for('admin.dashboard'))
    return redirect(url_for('admin.login'))

@admin_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('admin/dashboard.html', admin_account=flask_session.get('admin_account'))

@admin_bp.route('/cryptos', methods=['GET'])
@login_required
def manage_cryptos():
    cryptos = get_all_supported_cryptos_db(get_db_session())
    return render_template('admin/manage_cryptos.html', cryptos=cryptos)

@admin_bp.route('/cryptos/add', methods=['GET', 'POST'])
@login_required
def add_crypto():
    if request.method == 'POST':
        symbol = request.form.get('symbol', '').strip().upper()
        name = request.form.get('name', '').strip()
        try:
            if not symbol or not name:
                flash('幣種符號和名稱為必填。', 'danger')
            else:
                add_supported_crypto_db(get_db_session(), symbol, name)
                flash(f'幣種 {name} ({symbol}) 已成功新增。', 'success')
                return redirect(url_for('admin.manage_cryptos'))
        except ValueError as ve:
            flash(str(ve), 'warning')
        except Exception as e:
            logger.error(f"Add crypto error: {e}")
            flash('新增幣種時發生錯誤。', 'danger')
    return render_template('admin/add_crypto.html')

@admin_bp.route('/cryptos/edit/<string:crypto_id>', methods=['GET', 'POST'])
@login_required
def edit_crypto(crypto_id):
    db_session = get_db_session()
    crypto = get_supported_crypto_by_id_db(db_session, crypto_id)
    if not crypto:
        flash('找不到指定的幣種。', 'danger')
        return redirect(url_for('admin.manage_cryptos'))

    if request.method == 'POST':
        new_symbol = request.form.get('symbol', '').strip().upper()
        new_name = request.form.get('name', '').strip()

        if not new_symbol or not new_name:
            flash('幣種符號和名稱為必填。', 'danger')
        else:
            try:
                update_supported_crypto_db(db_session, crypto_id, new_symbol, new_name)
                flash(f'幣種 {new_name} ({new_symbol}) 已成功更新。', 'success')
                return redirect(url_for('admin.manage_cryptos'))
            except ValueError as ve:
                flash(str(ve), 'warning')
                crypto = get_supported_crypto_by_id_db(db_session, crypto_id)
            except Exception as e:
                logger.error(f"Edit crypto error: {e}")
                flash('更新幣種時發生錯誤。', 'danger')
                crypto = get_supported_crypto_by_id_db(db_session, crypto_id)
    return render_template('admin/edit_crypto.html', crypto=crypto)

@admin_bp.route('/cryptos/delete/<string:crypto_id>', methods=['POST'])
@login_required
def delete_crypto(crypto_id):
    try:
        if delete_supported_crypto_db(get_db_session(), crypto_id):
            flash('幣種已成功刪除。', 'success')
        else:
            flash('找不到要刪除的幣種。', 'danger')
    except ValueError as ve:
        flash(str(ve), 'warning')
    except Exception as e:
        logger.error(f"Delete crypto error: {e}")
        flash('刪除幣種時發生錯誤。', 'danger')
    return redirect(url_for('admin.manage_cryptos'))

@admin_bp.route('/users', methods=['GET'])
@login_required
def manage_users():
    users = get_db_session().query(User).order_by(User.user_id).all()
    return render_template('admin/manage_users.html', users=users)

@admin_bp.route('/users/view/<string:line_user_id>')
@login_required
def view_user_details(line_user_id):
    db_session = get_db_session()
    user = get_user_by_line_id_db(db_session, line_user_id)
    if not user:
        flash('找不到指定的使用者。', 'danger')
        return redirect(url_for('admin.manage_users'))

    investments = db_session.query(Investment, SupportedCrypto.coin_name).\
        join(SupportedCrypto, Investment.coin_id == SupportedCrypto.coin_id).\
        filter(Investment.user_id == line_user_id).\
        order_by(Investment.trade_time.desc()).all()

    investments_formatted = [
        {
            'crypto_name': coin_name,
            'coin_id': inv.coin_id,
            'action': inv.action,
            'quantity': inv.quantity or 0,
            'total_value': (inv.quantity or 0) * (inv.price or 0),
            'price': inv.price or 0,
            'trade_time': inv.trade_time
        } for inv, coin_name in investments
    ]

    tracking_list = db_session.query(TrackingItem, SupportedCrypto.coin_name).\
        join(SupportedCrypto, TrackingItem.coin_id == SupportedCrypto.coin_id).\
        filter(TrackingItem.user_id == line_user_id).all()

    tracking_list_formatted = [
        {'crypto_name': coin_name, 'coin_id': item.coin_id}
        for item, coin_name in tracking_list
    ]

    return render_template('admin/view_user_details.html',
                           user=user,
                           investments=investments_formatted,
                           tracking_list=tracking_list_formatted)

@admin_bp.route('/users/delete/<string:line_user_id>', methods=['POST'])
@login_required
def delete_user_admin(line_user_id):
    try:
        if delete_user_db(get_db_session(), line_user_id):
            flash(f'使用者 {line_user_id} 及其資料已成功刪除。', 'success')
        else:
            flash(f'找不到使用者 {line_user_id}。', 'danger')
    except Exception as e:
        logger.error(f"Delete user error: {e}")
        flash('刪除使用者時發生錯誤。', 'danger')
    return redirect(url_for('admin.manage_users'))
