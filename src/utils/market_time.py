from datetime import datetime, time, timedelta
import pytz

KST = pytz.timezone('Asia/Seoul')

def get_market_date():
    """
    장 운영일 기준 날짜 반환
    - 08:30 이전: 전일
    - 08:30 이후: 당일
    """
    now = datetime.now(KST)
    market_open = now.replace(hour=8, minute=30, second=0, microsecond=0)
    
    if now < market_open:
        # 08:30 이전이면 전일 데이터 사용
        return (now - timedelta(days=1)).strftime('%Y-%m-%d')
    return now.strftime('%Y-%m-%d')

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