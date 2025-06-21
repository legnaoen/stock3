import os
import sys
import sqlite3
import pandas as pd
from datetime import datetime
from typing import List, Dict, Tuple
from src.utils.market_time import get_market_date

# venv 활성화 체크
if sys.prefix == sys.base_prefix:
    print("[ERROR] 반드시 venv(가상환경)에서 실행해야 합니다.")
    sys.exit(1)

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../db/stock_master.db'))
THEME_INDUSTRY_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../db/theme_industry.db'))

# 업종/테마별 일일 성과 집계, 주도주 선정, DB 저장, 상세 분석 모듈
# - 목적: 업종/테마별 성과 집계, 주도주 선정, DB 저장, 상세 분석 함수 제공
# - 사용법: get_industry_performance, get_theme_performance 등 함수 활용

def init_performance_tables():
    """성과 테이블 초기화"""
    with sqlite3.connect(THEME_INDUSTRY_DB) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS industry_daily_performance (
            industry_id INTEGER,
            date TEXT,
            price_change_ratio FLOAT,  -- 시가총액 가중 등락률
            volume INTEGER,  -- 업종 전체 거래량
            market_cap BIGINT,  -- 업종 전체 시가총액
            trading_value BIGINT,  -- 업종 전체 거래대금
            leader_stock_codes TEXT,  -- 시가총액 상위 종목코드들 (콤마로 구분)
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (industry_id, date)
        );

        CREATE TABLE IF NOT EXISTS theme_daily_performance (
            theme_id INTEGER,
            date TEXT,
            price_change_ratio FLOAT,  -- 단순 평균 등락률
            market_cap_weighted_ratio FLOAT,  -- 시가총액 가중 등락률 (참고용)
            volume INTEGER,  -- 테마 전체 거래량
            market_cap BIGINT,  -- 테마 전체 시가총액
            trading_value BIGINT,  -- 테마 전체 거래대금
            leader_stock_codes TEXT,  -- 주도주 종목코드들 (콤마로 구분)
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (theme_id, date)
        );
        """)

        print("[INFO] 성과 테이블 초기화 완료")

def get_industry_performance(date: str = None, save_to_db: bool = True) -> List[Dict]:
    """
    업종별 성과를 계산하고, 통계 기반 로직으로 주도주를 선정하여 DB에 저장합니다.
    - 주도주 로직은 get_theme_performance와 동일하게 적용됩니다.
    - 업종 성과는 시가총액 가중 등락률을 사용합니다.
    """
    if not date:
        date = get_market_date()

    query = """
    SELECT
        m.industry_id,
        i.industry_name,
        m.stock_code,
        st.stock_name,
        d.price_change_ratio,
        d.trading_value,
        d.market_cap,
        d.volume
    FROM industry_stock_mapping m
    JOIN industry_master i ON m.industry_id = i.industry_id
    JOIN DailyStocks d ON m.stock_code = d.stock_code
    JOIN Stocks st ON d.stock_code = st.stock_code
    WHERE d.date = ?
    """
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(query, conn, params=(date,))

    if df.empty:
        return []
        
    # Pandas를 사용하여 그룹별 통계 계산
    stats = df.groupby('industry_id').agg(
        total_stocks_in_industry=('stock_code', 'count'),
        avg_change_rate=('price_change_ratio', 'mean'),
        stdev_change_rate=('price_change_ratio', 'std'),
        avg_trading_value=('trading_value', 'mean'),
        stdev_trading_value=('trading_value', 'std'),
        median_trading_value=('trading_value', 'median')
    ).reset_index()
    
    df = pd.merge(df, stats, on='industry_id')
    # NaN 값을 0으로 채움 (표준편차 계산 시 샘플이 1개인 경우 등)
    df.fillna({'stdev_change_rate': 0, 'stdev_trading_value': 0}, inplace=True)

    # 1단계: 1차 후보군 선정 (규칙 확장)
    # 경로 A(일반): 등락률 5% 이상 & 거래대금 30억 이상
    # 경로 B(폭등주 예외): 등락률 20% 이상
    df_filtered = df[
        ((df['price_change_ratio'] >= 5) & (df['trading_value'] >= 3000000000)) |
        (df['price_change_ratio'] >= 20)
    ].copy()

    leader_stocks_by_industry = {}
    for industry_id, group in df_filtered.groupby('industry_id'):
        total_stocks = group['total_stocks_in_industry'].iloc[0]
        leader_candidates = pd.DataFrame()

        if total_stocks <= 5:
            leader_candidates = group
        else:
            # [수정] 중앙값 기준 완화 (x3 -> x2)
            median_val = group['median_trading_value'].iloc[0]
            leader_candidates = group[group['trading_value'] > median_val * 2]

        if not leader_candidates.empty:
            stdev_rate = leader_candidates['stdev_change_rate'].iloc[0]
            stdev_val = leader_candidates['stdev_trading_value'].iloc[0]
            rate_zscore = ((leader_candidates['price_change_ratio'] - leader_candidates['avg_change_rate']) / stdev_rate) if stdev_rate > 0 else 0
            value_zscore = ((leader_candidates['trading_value'] - leader_candidates['avg_trading_value']) / stdev_val) if stdev_val > 0 else 0
            leader_candidates.loc[:, 'rank_score'] = (value_zscore * 0.6) + (rate_zscore * 0.4)
            top_leaders = leader_candidates.nlargest(5, 'rank_score')
            leader_stocks_by_industry[industry_id] = ','.join(top_leaders['stock_code'])

    # 4단계: "주도주 없음" 방지 장치
    all_industry_ids = df['industry_id'].unique()
    for industry_id in all_industry_ids:
        if industry_id not in leader_stocks_by_industry or not leader_stocks_by_industry[industry_id]:
            industry_df = df[df['industry_id'] == industry_id]
            # 등락률 0% 초과 종목 중 1위 선정
            top_stock = industry_df[industry_df['price_change_ratio'] > 0].nlargest(1, 'price_change_ratio')
            if not top_stock.empty:
                leader_stocks_by_industry[industry_id] = top_stock['stock_code'].iloc[0]

    # 업종별 전체 성과 집계 (시가총액 가중 방식)
    def weighted_avg(x):
        try:
            return (x['price_change_ratio'] * x['market_cap']).sum() / x['market_cap'].sum()
        except ZeroDivisionError:
            return 0

    industry_performance = df.groupby(['industry_id', 'industry_name']).apply(lambda x: pd.Series({
        'weighted_change_rate': weighted_avg(x),
        'total_volume': x['volume'].sum(),
        'total_market_cap': x['market_cap'].sum(),
        'total_trading_value': x['trading_value'].sum(),
        'total_stocks': x['stock_code'].nunique(),
        'up_stocks': (x['price_change_ratio'] > 0).sum(),
        'down_stocks': (x['price_change_ratio'] < 0).sum(),
        'unchanged_stocks': (x['price_change_ratio'] == 0).sum(),
        'leader_stocks': leader_stocks_by_industry.get(x.name[0], '')
    })).reset_index()

    industry_performance = industry_performance.sort_values(by='weighted_change_rate', ascending=False).reset_index(drop=True)
    industry_performance['rank'] = industry_performance.index + 1
    
    results = industry_performance.to_dict('records')

    if save_to_db and not industry_performance.empty:
        db_data_to_save = industry_performance[[
            'industry_id', 'weighted_change_rate', 'total_volume', 'total_market_cap',
            'total_trading_value', 'leader_stocks', 'rank'
        ]].copy()
        db_data_to_save['date'] = date
        db_data_to_save = db_data_to_save[[
            'industry_id', 'date', 'weighted_change_rate', 'total_volume',
            'total_market_cap', 'total_trading_value', 'leader_stocks', 'rank'
        ]]

        with sqlite3.connect(THEME_INDUSTRY_DB) as perf_conn:
            perf_conn.execute("DELETE FROM industry_daily_performance WHERE date = ?", (date,))
            perf_conn.executemany("""
                INSERT INTO industry_daily_performance
                (industry_id, date, price_change_ratio, volume, market_cap, trading_value,
                 leader_stock_codes, rank)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, db_data_to_save.to_records(index=False).tolist())
    
    return results

def get_theme_performance(date: str = None, save_to_db: bool = True) -> List[Dict]:
    """
    테마별 성과를 계산하고, 통계 기반의 새로운 로직으로 주도주를 선정하여 DB에 저장합니다.
    - 주도주 선정 로직 (v3) / 업종 로직과 동일
    - 테마 성과는 단순 평균 등락률과 시가총액 가중 등락률을 모두 계산.
    """
    if not date:
        date = get_market_date()

    query = """
    SELECT
        m.theme_id,
        t.theme_name,
        m.stock_code,
        st.stock_name,
        d.price_change_ratio,
        d.trading_value,
        d.market_cap,
        d.volume
    FROM theme_stock_mapping m
    JOIN theme_master t ON m.theme_id = t.theme_id
    JOIN DailyStocks d ON m.stock_code = d.stock_code
    JOIN Stocks st ON d.stock_code = st.stock_code
    WHERE d.date = ?
    """

    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(query, conn, params=(date,))

    if df.empty:
        return []

    # Pandas를 사용하여 그룹별 통계 계산
    stats = df.groupby('theme_id').agg(
        total_stocks_in_theme=('stock_code', 'count'),
        avg_change_rate=('price_change_ratio', 'mean'),
        stdev_change_rate=('price_change_ratio', 'std'),
        avg_trading_value=('trading_value', 'mean'),
        stdev_trading_value=('trading_value', 'std'),
        median_trading_value=('trading_value', 'median')
    ).reset_index()

    df = pd.merge(df, stats, on='theme_id')
    # NaN 값을 0으로 채움 (표준편차 계산 시 샘플이 1개인 경우 등)
    df.fillna({'stdev_change_rate': 0, 'stdev_trading_value': 0}, inplace=True)

    # 1단계: 1차 후보군 선정 (규칙 확장)
    # 경로 A(일반): 등락률 5% 이상 & 거래대금 30억 이상
    # 경로 B(폭등주 예외): 등락률 20% 이상
    df_filtered = df[
        ((df['price_change_ratio'] >= 5) & (df['trading_value'] >= 3000000000)) |
        (df['price_change_ratio'] >= 20)
    ].copy()

    leader_stocks_by_theme = {}

    # 각 테마별로 주도주 선정 로직 적용
    for theme_id, group in df_filtered.groupby('theme_id'):
        total_stocks = group['total_stocks_in_theme'].iloc[0]
        
        leader_candidates = pd.DataFrame()

        # 2단계: 그룹 규모에 따른 로직 분기
        if total_stocks <= 5:
            leader_candidates = group
        else: # total_stocks > 5
            # [수정] 중앙값 기준 완화 (x3 -> x2)
            median_val = group['median_trading_value'].iloc[0]
            leader_candidates = group[group['trading_value'] > median_val * 2]

        # 3단계: 최종 주도주 선정 (랭킹 및 Top 5)
        if not leader_candidates.empty:
            stdev_rate = leader_candidates['stdev_change_rate'].iloc[0]
            stdev_val = leader_candidates['stdev_trading_value'].iloc[0]

            rate_zscore = ((leader_candidates['price_change_ratio'] - leader_candidates['avg_change_rate']) / stdev_rate) if stdev_rate > 0 else 0
            value_zscore = ((leader_candidates['trading_value'] - leader_candidates['avg_trading_value']) / stdev_val) if stdev_val > 0 else 0

            leader_candidates.loc[:, 'rank_score'] = (value_zscore * 0.6) + (rate_zscore * 0.4)

            top_leaders = leader_candidates.nlargest(5, 'rank_score')
            leader_stocks_by_theme[theme_id] = ','.join(top_leaders['stock_code'])

    # 4단계: "주도주 없음" 방지 장치
    all_theme_ids = df['theme_id'].unique()
    for theme_id in all_theme_ids:
        if theme_id not in leader_stocks_by_theme or not leader_stocks_by_theme[theme_id]:
            theme_df = df[df['theme_id'] == theme_id]
            # 등락률 0% 초과 종목 중 1위 선정
            top_stock = theme_df[theme_df['price_change_ratio'] > 0].nlargest(1, 'price_change_ratio')
            if not top_stock.empty:
                leader_stocks_by_theme[theme_id] = top_stock['stock_code'].iloc[0]

    # 테마별 전체 성과 집계
    def weighted_avg(x):
        try:
            return (x['price_change_ratio'] * x['market_cap']).sum() / x['market_cap'].sum()
        except ZeroDivisionError:
            return 0
            
    theme_performance = df.groupby(['theme_id', 'theme_name']).apply(lambda x: pd.Series({
        'simple_change_rate': x['price_change_ratio'].mean(),
        'market_cap_weighted_rate': weighted_avg(x),
        'total_volume': x['volume'].sum(),
        'total_market_cap': x['market_cap'].sum(),
        'total_trading_value': x['trading_value'].sum(),
        'total_stocks': x['stock_code'].nunique(),
        'up_stocks': (x['price_change_ratio'] > 0).sum(),
        'down_stocks': (x['price_change_ratio'] < 0).sum(),
        'unchanged_stocks': (x['price_change_ratio'] == 0).sum(),
        'leader_stocks': leader_stocks_by_theme.get(x.name[0], '')
    })).reset_index()

    # 순위 매기기 (단순 평균 등락률 기준)
    theme_performance = theme_performance.sort_values(by='simple_change_rate', ascending=False).reset_index(drop=True)
    theme_performance['rank'] = theme_performance.index + 1
    
    results = theme_performance.to_dict('records')

    if save_to_db and not theme_performance.empty:
        db_data_to_save = theme_performance[[
            'theme_id', 'simple_change_rate', 'market_cap_weighted_rate', 'total_volume', 
            'total_market_cap', 'total_trading_value', 'leader_stocks', 'rank'
        ]].copy()
        db_data_to_save['date'] = date
        
        db_data_to_save = db_data_to_save[[
            'theme_id', 'date', 'simple_change_rate', 'market_cap_weighted_rate', 'total_volume',
            'total_market_cap', 'total_trading_value', 'leader_stocks', 'rank'
        ]]

        with sqlite3.connect(THEME_INDUSTRY_DB) as perf_conn:
            perf_conn.execute("DELETE FROM theme_daily_performance WHERE date = ?", (date,))
            perf_conn.executemany("""
                INSERT INTO theme_daily_performance
                (theme_id, date, price_change_ratio, market_cap_weighted_ratio, volume, market_cap,
                 trading_value, leader_stock_codes, rank)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, db_data_to_save.to_records(index=False).tolist())
            
    return results

def get_top_stocks_by_sector(sector_id: int, sector_type: str, date: str = None, limit: int = 5) -> List[Dict]:
    """
    특정 업종/테마 내 상승률 상위 종목 조회
    
    Args:
        sector_id: 업종/테마 ID
        sector_type: 'industry' 또는 'theme'
        date: 날짜 (YYYY-MM-DD). None인 경우 최근 거래일
        limit: 조회할 종목 수
        
    Returns:
        상위 종목 리스트
    """
    if not date:
        date = get_market_date()
        
    if sector_type not in ['industry', 'theme']:
        raise ValueError("sector_type must be either 'industry' or 'theme'")
        
    mapping_table = f"{sector_type}_stock_mapping"
    sector_col = f"{sector_type}_id"
    
    query = f"""
    SELECT 
        s.stock_name,
        d.price_change_ratio,
        d.close_price,
        d.volume,
        d.trading_value,
        d.market_cap
    FROM {mapping_table} m
    JOIN Stocks s ON m.stock_code = s.stock_code
    JOIN DailyStocks d ON s.stock_code = d.stock_code
    WHERE m.{sector_col} = ? AND d.date = ?
    ORDER BY d.price_change_ratio DESC
    LIMIT ?
    """
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (sector_id, date, limit))
        results = cursor.fetchall()
        
    return [
        {
            'name': row[0],
            'change_rate': row[1],
            'close_price': row[2],
            'volume': row[3],
            'trading_value': row[4],
            'market_cap': row[5]
        }
        for row in results
    ]

def update_daily_performance(date: str = None):
    """지정된 날짜 또는 최근 거래일의 모든 업종/테마 성과를 업데이트"""
    if not date:
        date = get_market_date()
    
    print(f"[{date}] 기준 업종/테마 일일 성과 업데이트 시작...")
    
    init_performance_tables()  # 테이블이 없으면 생성
    
    try:
        # 업종 성과 계산 및 저장
        get_industry_performance(date, save_to_db=True)
        
        # 테마 성과 계산 및 저장
        get_theme_performance(date, save_to_db=True)
        
        print(f"{date} 업종/테마 성과 업데이트 완료")
        
    except Exception as e:
        print(f"Error updating performance: {str(e)}")
        raise

if __name__ == "__main__":
    init_performance_tables()

    target_date = get_market_date()
    update_daily_performance(target_date)
    
    print(f"\n[{target_date}] 기준 상위 5개 업종:")
    top_industries = get_industry_performance(target_date, save_to_db=False)
    for i in top_industries[:5]:
        print(f"- {i['industry_name']}: {i['weighted_change_rate']}% (상승 {i['up_stocks']}, 하락 {i['down_stocks']}")
        
    print(f"\n[{target_date}] 기준 상위 5개 테마:")
    top_themes = get_theme_performance(target_date, save_to_db=False)
    for t in top_themes[:5]:
        print(f"- {t['theme_name']}: {t['simple_change_rate']}% (상승 {t['up_stocks']}, 하락 {t['down_stocks']}") 