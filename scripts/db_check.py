import sqlite3
import os

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../db/stock_master.db'))

def check_industry_mapping():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        # 업종 매핑이 있는 종목 수
        cur.execute('''
            SELECT COUNT(DISTINCT s.stock_code)
            FROM Stocks s
            JOIN StockIndustries si ON s.stock_code = si.stock_code
        ''')
        with_industry = cur.fetchone()[0]
        # 업종 매핑이 없는 종목 수
        cur.execute('''
            SELECT COUNT(*)
            FROM Stocks s
            WHERE s.stock_code NOT IN (SELECT stock_code FROM StockIndustries)
        ''')
        without_industry = cur.fetchone()[0]
        # 예시: 업종 없는 종목 10개
        cur.execute('''
            SELECT s.stock_code, s.stock_name
            FROM Stocks s
            WHERE s.stock_code NOT IN (SELECT stock_code FROM StockIndustries)
            LIMIT 10
        ''')
        no_industry_examples = cur.fetchall()
    print(f"[RESULT] 업종정보가 있는 종목 수: {with_industry}")
    print(f"[RESULT] 업종정보가 없는 종목 수: {without_industry}")
    if no_industry_examples:
        print("[예시] 업종정보 없는 종목 10개:")
        for code, name in no_industry_examples:
            print(f"  - {code}: {name}")
    else:
        print("[INFO] 업종정보가 없는 종목이 없습니다.")

def check_all_stats():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        # 총 종목수
        cur.execute('SELECT COUNT(*) FROM Stocks')
        total_stocks = cur.fetchone()[0]
        # 업종정보가 기록된 종목수
        cur.execute('''
            SELECT COUNT(DISTINCT s.stock_code)
            FROM Stocks s
            JOIN StockIndustries si ON s.stock_code = si.stock_code
        ''')
        with_industry = cur.fetchone()[0]
        # 테마정보가 기록된 종목수 (중복 없이)
        cur.execute('''
            SELECT COUNT(DISTINCT s.stock_code)
            FROM Stocks s
            JOIN StockThemes st ON s.stock_code = st.stock_code
        ''')
        with_theme = cur.fetchone()[0]
    print(f"[RESULT] 총 종목 수: {total_stocks}")
    print(f"[RESULT] 업종정보가 기록된 종목 수: {with_industry}")
    print(f"[RESULT] 테마정보가 기록된 종목 수: {with_theme}")

if __name__ == "__main__":
    check_industry_mapping()
    check_all_stats()
