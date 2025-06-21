# financial_evaluation 테이블에 summary_report 컬럼 추가 마이그레이션 스크립트
# - 목적: 재무 요약 텍스트 저장용 컬럼 추가 (이미 존재하면 무시)
# - 사용법: python scripts/migrate_add_summary_report.py
import sqlite3
import os

def migrate_add_summary_report():
    db_path = os.path.join(os.path.dirname(__file__), '../db/stock_master.db')
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(financial_evaluation)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'summary_report' not in columns:
                print('Adding summary_report column to financial_evaluation...')
                cursor.execute('ALTER TABLE financial_evaluation ADD COLUMN summary_report TEXT')
                conn.commit()
                print('Successfully added summary_report column.')
            else:
                print('summary_report column already exists.')
    except Exception as e:
        print(f'Error during migration: {str(e)}')
        return False
    return True

if __name__ == "__main__":
    migrate_add_summary_report() 