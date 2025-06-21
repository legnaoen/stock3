# 시장지수(KOSPI/KOSDAQ) 데이터 수집 및 모멘텀 계산/DB 저장 스크립트
# - 목적: momentum_analysis의 날짜 범위에 맞춰 시장지수(코스피/코스닥) 데이터를 수집하고, 모멘텀을 계산해 DB에 저장
# - 사용법: python scripts/collect_market_index.py
import sys, os
import sqlite3
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from src.collector.market_index_collector import collect_market_index_daily
from src.analyzer.market_index_analyzer import calc_index_momentum, save_index_momentum_to_db

DB_PATH = os.path.join(os.path.dirname(__file__), '../db/theme_industry.db')

def get_date_range():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute('SELECT MIN(date), MAX(date) FROM momentum_analysis')
        min_date, max_date = cur.fetchone()
        # YYYY-MM-DD -> YYYYMMDD
        min_date = min_date.replace('-', '') if min_date else None
        max_date = max_date.replace('-', '') if max_date else None
        return min_date, max_date

if __name__ == "__main__":
    min_date, max_date = get_date_range()
    print(f"[INFO] momentum_analysis 기준 날짜 범위: {min_date} ~ {max_date}")
    for index_name in ['KOSPI', 'KOSDAQ']:
        print(f"[{index_name}] 데이터 수집 중...")
        df = collect_market_index_daily(index_name, min_date, max_date)
        print(f"{index_name} 샘플:")
        print(df.head())
        df = calc_index_momentum(df)
        print(f"{index_name} 모멘텀 샘플:")
        print(df.head(10))
        save_index_momentum_to_db(df)
        print(f"{index_name} DB 저장 완료\n")
    print("전체 지수 데이터 수집/모멘텀/DB 저장 완료!") 