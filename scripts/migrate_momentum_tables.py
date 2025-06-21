import sqlite3
import os

def apply_schema(db_path, schema_path):
    """
    지정된 SQL 스키마 파일을 데이터베이스에 적용합니다.
    """
    if not os.path.exists(schema_path):
        print(f"오류: 스키마 파일을 찾을 수 없습니다 - {schema_path}")
        return

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print(f"데이터베이스 연결 성공: {db_path}")

        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        # 여러 SQL 문이 있을 수 있으므로 executescript 사용
        cursor.executescript(schema_sql)
        conn.commit()
        print(f"'{schema_path}' 스키마가 성공적으로 적용되었습니다.")

    except sqlite3.Error as e:
        print(f"SQLite 오류 발생: {e}")
    finally:
        if conn:
            conn.close()
            print("데이터베이스 연결이 종료되었습니다.")

if __name__ == '__main__':
    # 프로젝트 루트 디렉토리 기준으로 경로 설정
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(project_root, 'db', 'theme_industry.db')
    schema_path = os.path.join(project_root, 'db', 'schema_momentum.sql')
    
    apply_schema(db_path, schema_path) 