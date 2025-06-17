from datetime import datetime, time, timedelta
import pytz
import sqlite3
import os

KST = pytz.timezone('Asia/Seoul')

def get_market_date():
    """
    DB에 실제 데이터가 존재하는 가장 최근 날짜(전일 등)를 반환.
    사용자가 '빠른 새로고침' 등으로 오늘 데이터가 적재되기 전까지는 오늘로 넘어가지 않음.
    """
    DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../db/stock_master.db'))
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT date FROM DailyStocks ORDER BY date DESC LIMIT 1")
            row = cursor.fetchone()
            if row and row[0]:
                return row[0]
    except Exception:
        pass
    # DB 조회 실패 시 fallback: 오늘 날짜
    return datetime.now().strftime('%Y-%m-%d')

def is_market_open():
    """
    현재 장 운영 시간인지 확인
    - 평일 09:00 ~ 15:30
    """
    now = datetime.now(KST)
    
    # 주말 체크
    if now.weekday() >= 5:  # 5: 토요일, 6: 일요일
        return False
    
    current_time = now.time()
    market_start = time(9, 0)  # 09:00
    market_end = time(15, 30)  # 15:30
    
    return market_start <= current_time <= market_end

def get_market_status():
    """
    현재 장 상태 반환
    Returns:
        str: 'OPEN' (장 운영 중)
             'CLOSED' (장 종료)
             'WAITING' (장 시작 전)
    """
    now = datetime.now(KST)
    
    # 주말 체크
    if now.weekday() >= 5:
        return 'CLOSED'
    
    current_time = now.time()
    market_start = time(9, 0)  # 09:00
    market_end = time(15, 30)  # 15:30
    
    if current_time < market_start:
        return 'WAITING'
    elif current_time > market_end:
        return 'CLOSED'
    else:
        return 'OPEN' 