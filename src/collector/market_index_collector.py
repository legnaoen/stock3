import pandas as pd
from pykrx import stock

# KOSPI/KOSDAQ 등 주요 지수의 일별 시세(OHLCV) 데이터 수집 모듈
# - 목적: 지수별 일별 시세(시가/고가/저가/종가/거래량/거래대금) 수집
# - 사용법: collect_market_index_daily 함수 활용

def collect_market_index_daily(index_name, start_date, end_date):
    """
    KOSPI/KOSDAQ 등 주요 지수의 일별 시세(원본) 데이터 수집
    index_name: 'KOSPI' 또는 'KOSDAQ'
    start_date, end_date: 'YYYYMMDD' 형식
    return: DataFrame(date, index_name, open, high, low, close, volume, trading_value)
    """
    code_map = {'KOSPI': '1001', 'KOSDAQ': '2001'}
    if index_name not in code_map:
        raise ValueError('지원하지 않는 지수명')
    code = code_map[index_name]
    df = stock.get_index_ohlcv_by_date(start_date, end_date, code)
    df = df.reset_index().rename(columns={'날짜':'date', '시가':'open', '고가':'high', '저가':'low', '종가':'close', '거래량':'volume', '거래대금':'trading_value'})
    df['index_name'] = index_name
    df = df[['date','index_name','open','high','low','close','volume','trading_value']]
    df['date'] = df['date'].dt.strftime('%Y-%m-%d')
    return df

# 테스트용 샘플 실행
if __name__ == "__main__":
    df_kospi = collect_market_index_daily('KOSPI', '20240101', '20240630')
    print(df_kospi.head())
    df_kosdaq = collect_market_index_daily('KOSDAQ', '20240101', '20240630')
    print(df_kosdaq.head()) 