import sqlite3
import os

def migrate():
    """
    momentum_analysis 테이블에 leader_count와 leader_momentum 컬럼을 추가합니다.
    이미 컬럼이 존재하는 경우 오류를 무시하고 계속 진행합니다.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(project_root, 'db', 'theme_industry.db')

    print(f"DB 경로: {db_path}")
    if not os.path.exists(db_path):
        print(f"[ERROR] DB 파일을 찾을 수 없습니다: {db_path}")
        return

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            print("momentum_analysis 테이블에 컬럼 추가 시도...")
            
            try:
                cursor.execute("ALTER TABLE momentum_analysis ADD COLUMN leader_count INTEGER DEFAULT 0")
                print("- leader_count 컬럼 추가 성공.")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print("- leader_count 컬럼이 이미 존재합니다.")
                else:
                    raise e

            try:
                cursor.execute("ALTER TABLE momentum_analysis ADD COLUMN leader_momentum REAL DEFAULT 0.0")
                print("- leader_momentum 컬럼 추가 성공.")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print("- leader_momentum 컬럼이 이미 존재합니다.")
                else:
                    raise e
            
            conn.commit()
            print("\\n마이그레이션이 성공적으로 완료되었습니다.")

    except Exception as e:
        print(f"마이그레이션 중 오류 발생: {e}")

if __name__ == "__main__":
    migrate() 