"""
[임시 스크립트] 시가총액(market_cap) 데이터 보충용

- 목적: DailyStocks 테이블에서 market_cap이 0으로 저장된 과거 데이터를 pykrx API로 조회해 보충
- 사용법: python scripts/fill_missing_market_cap.py
- 주의: 이미 값이 채워진 row는 건드리지 않음. DB 백업 후 실행 권장
- 재사용: 과거 데이터 보정, 신규 데이터 오류 발생 시 반복 사용 가능
"""
import os
import sqlite3
from datetime import datetime, timedelta
from pykrx import stock
import time

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../db/stock_master.db'))

# 보충할 기간 설정 (예: 최근 2년)
START_DATE = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')
END_DATE = datetime.now().strftime('%Y-%m-%d')

# 1. market_cap이 0인 row만 추출
with sqlite3.connect(DB_PATH) as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT date FROM DailyStocks WHERE market_cap = 0 AND date >= ? AND date <= ? ORDER BY date", (START_DATE, END_DATE))
    target_dates = [row[0] for row in cursor.fetchall()]
    cursor.execute("SELECT DISTINCT stock_code FROM DailyStocks WHERE market_cap = 0 AND date >= ? AND date <= ?", (START_DATE, END_DATE))
    target_codes = [row[0] for row in cursor.fetchall()]

print(f"[INFO] 보충 대상 날짜: {len(target_dates)}개, 종목: {len(target_codes)}개")

# 2. 날짜별, 종목별로 pykrx에서 시가총액 조회 후 DB 업데이트
for date in target_dates:
    date_krx = date.replace('-', '')
    try:
        # KOSPI/KOSDAQ 모두 조회
        for market in ["KOSPI", "KOSDAQ"]:
            cap_df = stock.get_market_cap(date_krx, market=market)
            if cap_df.empty:
                continue
            for code in target_codes:
                if code not in cap_df.index:
                    continue
                market_cap = int(cap_df.loc[code]['시가총액'])
                if market_cap == 0:
                    continue
                # DB 업데이트
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("""
                        UPDATE DailyStocks SET market_cap = ? WHERE stock_code = ? AND date = ? AND market_cap = 0
                    """, (market_cap, code, date))
                    conn.commit()
        print(f"[OK] {date} 보충 완료")
        time.sleep(0.2)  # KRX 서버 부하 방지
    except Exception as e:
        print(f"[ERR] {date} 처리 중 오류: {e}")

print("[DONE] market_cap 보충 작업 완료") 