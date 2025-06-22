import os
import sys
import sqlite3
from datetime import datetime, timedelta
import pandas as pd

# KRX(한국거래소) API 기반 전체 종목/일별 시세/시가총액/누락 데이터 자동 보충 모듈
# - 목적: 전체 상장종목/일별 시세/시가총액 수집 및 DB 저장, 누락 데이터 자동 보충
# - 사용법: fetch_all_stocks, fetch_daily_stocks, fill_missing_history 등 함수 활용

# venv 활성화 체크 (운영 안전)
if os.name != 'nt':
    if not hasattr(sys, 'base_prefix') or sys.prefix == sys.base_prefix:
        print("[ERROR] 반드시 venv(가상환경)에서 실행해야 합니다.")
        sys.exit(1)

try:
    from pykrx import stock
except ImportError:
    print("[ERROR] pykrx 패키지가 설치되어 있지 않습니다. venv에서 pip install pykrx 후 재실행하세요.")
    sys.exit(1)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logger import setup_logger

logger = setup_logger()

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../db/stock_master.db'))
SCHEMA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../db/schema.sql'))

def init_db():
    """DB가 존재하지 않을 때만 초기화"""
    if not os.path.exists(DB_PATH):
        logger.info("DB 파일이 없습니다. 새로 생성합니다.")
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        with sqlite3.connect(DB_PATH) as conn:
            with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
                conn.executescript(f.read())
        logger.info("DB 초기화 완료")
    else:
        logger.info("기존 DB 파일이 존재합니다. 초기화를 건너뜁니다.")

def fetch_all_stocks():
    """전체 상장 종목 정보 수집"""
    result = []
    for market, market_type in [("KOSPI", "KOSPI"), ("KOSDAQ", "KOSDAQ")]:
        df = stock.get_market_ticker_list(market=market)
        for code in df:
            name = stock.get_market_ticker_name(code)
            result.append({
                'stock_code': code,
                'stock_name': name,
                'market_type': market_type
            })
    return result

def fetch_daily_stocks(date_str: str = None):
    """특정 일자의 전체 종목 시세 정보 수집
    
    Args:
        date_str: 조회할 날짜 (YYYY-MM-DD). None이면 가장 최근 거래일
    """
    if date_str is None:
        # 오늘부터 10일 전까지 체크하여 가장 최근 거래일 찾기
        for i in range(10):
            check_date = datetime.now() - timedelta(days=i)
            check_date_str = check_date.strftime("%Y%m%d")
            df = stock.get_market_ohlcv(check_date_str)
            # 거래가 있었는지 확인 (거래량 합계 체크)
            if not df.empty and df['거래량'].sum() > 0:
                date_str = check_date.strftime("%Y-%m-%d")
                break
        else:
            raise ValueError("최근 10일간 거래일을 찾을 수 없습니다.")

    date_krx = date_str.replace("-", "")
    result = []

    # KOSPI, KOSDAQ 데이터 수집
    for market in ["KOSPI", "KOSDAQ"]:
        df = stock.get_market_ohlcv(date_krx, market=market)
        cap_df = stock.get_market_cap(date_krx, market=market)
        
        if df.empty or cap_df.empty:
            continue
            
        for code in df.index:
            # 가격 정보
            data = df.loc[code]
            # 시가총액 정보
            cap_data = cap_df.loc[code]
            
            result.append({
                'stock_code': code,
                'date': date_str,
                'open_price': int(data['시가']),
                'high_price': int(data['고가']),
                'low_price': int(data['저가']),
                'close_price': int(data['종가']),
                'volume': int(data['거래량']),
                'trading_value': int(data['거래대금']),
                'market_cap': int(cap_data['시가총액']),
                'price_change_ratio': float(data['등락률'])
            })
            
    return result

def upsert_stocks(stocks):
    """종목 정보 업데이트 (기존 데이터 유지)"""
    with sqlite3.connect(DB_PATH) as conn:
        for s in stocks:
            conn.execute(
                """
                INSERT INTO Stocks (stock_code, stock_name, market_type, last_updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(stock_code) DO UPDATE SET
                    stock_name=excluded.stock_name,
                    market_type=excluded.market_type,
                    last_updated_at=excluded.last_updated_at
                """,
                (s['stock_code'], s['stock_name'], s['market_type'], datetime.now())
            )
        conn.commit()

def upsert_daily_stocks(daily_data):
    """일별 시세 정보 업데이트 (같은 날짜는 덮어쓰기)"""
    with sqlite3.connect(DB_PATH) as conn:
        for d in daily_data:
            conn.execute(
                """
                INSERT OR REPLACE INTO DailyStocks 
                (stock_code, date, open_price, high_price, low_price, close_price,
                 volume, trading_value, market_cap, price_change_ratio)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (d['stock_code'], d['date'], d['open_price'], d['high_price'],
                 d['low_price'], d['close_price'], d['volume'], d['trading_value'],
                 d['market_cap'], d['price_change_ratio'])
            )
        conn.commit()

def get_missing_dates(stock_code, days=60):
    """특정 종목의 최근 N영업일 중 DB에 없는 날짜 리스트 반환"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT date FROM DailyStocks WHERE stock_code = ? ORDER BY date DESC LIMIT ?", (stock_code, days))
        existing_dates = set(row[0] for row in cursor.fetchall())
    # pykrx로 최근 N영업일 구하기
    today = datetime.now().strftime('%Y%m%d')
    df = stock.get_market_ohlcv_by_date((datetime.now() - timedelta(days=days*2)).strftime('%Y%m%d'), today, stock_code)
    all_dates = [d.strftime('%Y-%m-%d') for d in df.index]
    missing = [d for d in all_dates if d not in existing_dates]
    return missing

def get_trading_value_from_row(row):
    # 다양한 컬럼명에 대응
    for col in ['거래대금', '거래대금(원)', 'VALUE']:
        if col in row:
            return int(row[col])
    return 0

def fill_missing_history(days=60):
    """전체 종목에 대해 최근 N영업일 중 DB에 없는 일별 시세를 pykrx로 보충 저장"""
    logger.info(f"[백필] 최근 {days}영업일 누락분 보충 시작")
    with sqlite3.connect(DB_PATH) as conn:
        codes = [row[0] for row in conn.execute("SELECT stock_code FROM Stocks").fetchall()]
    for code in codes:
        missing_dates = get_missing_dates(code, days)
        if not missing_dates:
            continue
        today = datetime.now().strftime('%Y%m%d')
        df = stock.get_market_ohlcv_by_date((datetime.now() - timedelta(days=days*2)).strftime('%Y%m%d'), today, code)
        for date in missing_dates:
            if date not in df.index.strftime('%Y-%m-%d'):
                continue
            row = df.loc[df.index.strftime('%Y-%m-%d') == date].iloc[0]
            trading_value = get_trading_value_from_row(row)
            d = {
                'stock_code': code,
                'date': date,
                'open_price': int(row['시가']) if '시가' in row else 0,
                'high_price': int(row['고가']) if '고가' in row else 0,
                'low_price': int(row['저가']) if '저가' in row else 0,
                'close_price': int(row['종가']) if '종가' in row else 0,
                'volume': int(row['거래량']) if '거래량' in row else 0,
                'trading_value': trading_value,
                'market_cap': 0,  # 필요시 추가 조회
                'price_change_ratio': float(row['등락률']) if '등락률' in row else 0.0
            }
            upsert_daily_stocks([d])
        logger.info(f"{code}: {len(missing_dates)}개 날짜 보충 완료")
    logger.info("[백필] 누락분 보충 완료")

def main():
    # DB 초기화 (필요한 경우에만)
    init_db()
    
    # 전체 종목 정보 업데이트
    logger.info("전체 상장 종목 수집 중...")
    stocks = fetch_all_stocks()
    logger.info(f"수집 종목 수: {len(stocks)}")
    upsert_stocks(stocks)
    logger.info("Stocks 테이블 업데이트 완료")
    
    # 일별 시세 정보 수집
    logger.info("일별 시세 정보 수집 중...")
    daily_data = fetch_daily_stocks()
    if daily_data:
        upsert_daily_stocks(daily_data)
        logger.info(f"DailyStocks 테이블 업데이트 완료 (데이터 수: {len(daily_data)})")
    else:
        logger.warning("수집된 일별 시세 데이터가 없습니다.")

if __name__ == "__main__":
    if '--backfill' in sys.argv:
        fill_missing_history(days=60)
    else:
        main()
