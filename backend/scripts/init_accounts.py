import os
from dotenv import load_dotenv

load_dotenv()

from passlib.hash import bcrypt

from database.database import SessionLocalAccounts, accounts_engine
from database.account_models import AccountsBase, AccountUser


def main():
    # 1) 建表
    AccountsBase.metadata.create_all(bind=accounts_engine)

    # 2) 读取管理员配置
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "Aa@123456")

    # 3) 创建/重置管理员
    db = SessionLocalAccounts()
    try:
        user = db.query(AccountUser).filter(AccountUser.username == admin_username).first()
        if user:
            user.password_hash = bcrypt.hash(admin_password)
            db.commit()
            print(f"✅ 重置管理员密码: {admin_username}")
        else:
            user = AccountUser(
                username=admin_username,
                password_hash=bcrypt.hash(admin_password),
                email=None,
                status="admin",
            )
            db.add(user)
            db.commit()
            print(f"✅ 已创建管理员: {admin_username}")
    finally:
        db.close()


if __name__ == "__main__":
    main()


