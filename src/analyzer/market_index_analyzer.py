import pandas as pd
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
import sqlite3

# 시장지수(KOSPI/KOSDAQ 등) 일별 모멘텀(수익률) 계산 및 DB 저장 모듈
# - 목적: 지수 데이터에서 1/3/5/10/20일 모멘텀 계산 및 DB 저장
# - 사용법: calc_index_momentum, save_index_momentum_to_db 함수 활용

# [구조] market_index_daily 테이블에 지수 모멘텀을 저장하지만, 업종/테마 분석/투자의견 산출에는 직접 사용되지 않음

def calc_index_momentum(df):
    """
    일별 지수 데이터에서 1/3/5/10/20일 모멘텀(수익률, %) 컬럼을 계산해 반환
    df: date, index_name, close 등 포함 DataFrame
    return: 모멘텀 컬럼이 추가된 DataFrame
    """
    df = df.sort_values(['index_name', 'date']).copy()
    for n in [1, 3, 5, 10, 20]:
        df[f'momentum_{n}d'] = df.groupby('index_name')['close'].pct_change(periods=n) * 100
    return df

def save_index_momentum_to_db(df, db_path='db/theme_industry.db'):
    """
    계산된 지수 모멘텀 DataFrame을 market_index_daily 테이블에 저장/업데이트 (중복시 REPLACE)
    """
    cols = ['date','index_name','open','high','low','close','volume','trading_value',
            'momentum_1d','momentum_3d','momentum_5d','momentum_10d','momentum_20d']
    df = df[cols].copy()
    with sqlite3.connect(db_path) as conn:
        sql = f"""
        REPLACE INTO market_index_daily
        ({', '.join(cols)})
        VALUES ({', '.join(['?']*len(cols))})
        """
        conn.executemany(sql, df.values.tolist())
        conn.commit()

# 테스트용 샘플 실행
if __name__ == "__main__":
    # 샘플 데이터 생성 또는 collector에서 불러오기
    from src.collector.market_index_collector import collect_market_index_daily
    df_kospi = collect_market_index_daily('KOSPI', '20240101', '20240630')
    df_kospi = calc_index_momentum(df_kospi)
    print(df_kospi.head(10))
    save_index_momentum_to_db(df_kospi)
    print('DB 저장 완료') 