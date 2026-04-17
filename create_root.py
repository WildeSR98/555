"""
Скрипт создания системного root-пользователя.
Запустить один раз: python create_root.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime
from src.database import get_session
from src.models import User

def create_root():
    session = get_session()
    try:
        existing = session.query(User).filter(User.username == 'root').first()
        if existing:
            if existing.role != 'ROOT':
                existing.role = 'ROOT'
                existing.set_password('Sw23edcx')
                existing.is_active = True
                session.commit()
                print("[OK] Polzovatel 'root' obnovlen do roli ROOT.")
            else:
                print("[INFO] Polzovatel 'root' uzhe sushchestvuet.")
            return

        root_user = User(
            username='root',
            first_name='',
            last_name='',
            role='ROOT',
            is_active=True,
            is_superuser=True,
            is_staff=True,
            date_joined=datetime.now(),
        )
        root_user.set_password('Sw23edcx')
        session.add(root_user)
        session.commit()
        print("[OK] Root-polzovatel sozdan uspeshno.")
    except Exception as e:
        print(f"[ERROR] {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == '__main__':
    create_root()
