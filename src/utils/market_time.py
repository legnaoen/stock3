from datetime import datetime, time, timedelta
import pytz
import sqlite3
import os

KST = pytz.timezone('Asia/Seoul')

def get_market_date():
    """
    데이터 처리에 사용될 올바른 시장(거래) 날짜를 반환합니다.
    - DB에 저장된 가장 최신 거래일을 조회합니다.
    - 단, 장 마감(15:30) 이전이거나, 조회된 날짜가 오늘과 같은 경우,
      안정성을 위해 하루를 뺀 날짜(이전 거래일)를 사용하도록 유도할 수 있습니다.
    - 현재 로직: DB의 MAX(date)를 반환. 데이터 적재 시점이 기준이 됨.
    """
    DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../db/stock_master.db'))
    
    # 먼저 krx_collector가 마지막으로 기록한 날짜를 조회
    try:
        with sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(date) FROM DailyStocks")
            db_date_str = cursor.fetchone()[0]

            if db_date_str:
                now_kst = datetime.now(KST)
                db_date = datetime.strptime(db_date_str, '%Y-%m-%d').date()
                
                # DB 최신 날짜가 오늘이고, 아직 장 마감(15:30) 전이면 하루를 뺀다.
                if db_date == now_kst.date() and now_kst.time() < time(15, 30):
                     # 실제로는 어제 날짜의 데이터가 최신이므로, DB에서 어제 날짜를 다시 찾는다.
                    cursor.execute("SELECT date FROM DailyStocks WHERE date < ? ORDER BY date DESC LIMIT 1", (db_date_str,))
                    prev_date = cursor.fetchone()
                    if prev_date:
                        return prev_date[0]

                return db_date_str

    except Exception as e:
        print(f"DB 조회 중 오류 발생: {e}")

    # 모든 예외 발생 시, KST 기준 어제 날짜를 반환
    return (datetime.now(KST) - timedelta(days=1)).strftime('%Y-%m-%d')

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