# momentum_analysis 테이블에 rsi_value 컬럼 추가 마이그레이션 스크립트
# - 목적: RSI 지표 컬럼을 테이블에 추가 (이미 존재하면 무시)
# - 사용법: python scripts/migrate_add_rsi.py
import sqlite3
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(PROJECT_ROOT, 'db', 'theme_industry.db')

def migrate():
    """
    momentum_analysis 테이블에 rsi_value 컬럼을 추가합니다.
    이미 컬럼이 존재하면 아무 작업도 수행하지 않습니다.
    """
    db_path = DB_PATH
    
    print(f"[INFO] 데이터베이스 파일 경로: {db_path}")
    if not os.path.exists(db_path):
        print(f"[ERROR] 데이터베이스 파일({db_path})을 찾을 수 없습니다.")
        return

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 1. 테이블 정보 확인
            cursor.execute("PRAGMA table_info(momentum_analysis)")
            columns = [info[1] for info in cursor.fetchall()]
            
            # 2. 컬럼 존재 여부 체크
            if 'rsi_value' in columns:
                print("[SKIP] 'rsi_value' 컬럼이 이미 'momentum_analysis' 테이블에 존재합니다.")
            else:
                # 3. 컬럼 추가
                print("[RUN] 'momentum_analysis' 테이블에 'rsi_value' 컬럼을 추가합니다...")
                cursor.execute("ALTER TABLE momentum_analysis ADD COLUMN rsi_value FLOAT")
                print("[SUCCESS] 컬럼 추가 완료.")

            # 4. 변경된 스키마 확인 (선택사항)
            print("\n[INFO] 변경 후 'momentum_analysis' 테이블 스키마:")
            cursor.execute("PRAGMA table_info(momentum_analysis)")
            for info in cursor.fetchall():
                print(f"  - {info[1]} ({info[2]})")

    except sqlite3.Error as e:
        print(f"[ERROR] 데이터베이스 작업 중 오류 발생: {e}")

if __name__ == '__main__':
    migrate() 