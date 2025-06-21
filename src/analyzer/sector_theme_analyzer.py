import os
import sys
import sqlite3
from datetime import datetime
from typing import List, Dict, Tuple
from src.utils.market_time import get_market_date

# venv 활성화 체크
if sys.prefix == sys.base_prefix:
    print("[ERROR] 반드시 venv(가상환경)에서 실행해야 합니다.")
    sys.exit(1)

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../db/stock_master.db'))
THEME_INDUSTRY_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../db/theme_industry.db'))

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
    업종별 등락률을 시가총액 가중평균으로 계산하고 선택적으로 DB에 저장
    
    Args:
        date: 날짜 (YYYY-MM-DD). None인 경우 최근 거래일 사용
        save_to_db: DB에 결과를 저장할지 여부
        
    Returns:
        업종별 등락률 리스트 (시가총액 가중평균 기준 내림차순 정렬)
    """
    if not date:
        date = get_market_date()
        
    query = """
    WITH industry_stats AS (
        SELECT 
            i.industry_id,
            i.industry_name,
            ROUND(SUM(d.price_change_ratio * d.market_cap) / SUM(d.market_cap), 2) as weighted_change_rate,
            SUM(d.volume) as total_volume,
            SUM(d.market_cap) as total_market_cap,
            SUM(d.trading_value) as total_trading_value,
            COUNT(DISTINCT m.stock_code) as total_stocks,
            SUM(CASE WHEN d.price_change_ratio > 0 THEN 1 ELSE 0 END) as up_stocks,
            SUM(CASE WHEN d.price_change_ratio < 0 THEN 1 ELSE 0 END) as down_stocks,
            SUM(CASE WHEN d.price_change_ratio = 0 THEN 1 ELSE 0 END) as unchanged_stocks,
            GROUP_CONCAT(
                CASE 
                    WHEN d.market_cap >= (SELECT market_cap FROM DailyStocks d2 
                                        WHERE d2.stock_code = m.stock_code 
                                        AND d2.date = ? 
                                        ORDER BY d2.market_cap DESC 
                                        LIMIT 1 OFFSET 4) 
                    THEN m.stock_code 
                END
            ) as leader_stock_codes
        FROM industry_master i
        JOIN industry_stock_mapping m ON i.industry_id = m.industry_id
        JOIN DailyStocks d ON m.stock_code = d.stock_code
        WHERE d.date = ?
        GROUP BY i.industry_id, i.industry_name
    )
    SELECT 
        industry_id,
        industry_name,
        weighted_change_rate,
        total_volume,
        total_market_cap,
        total_trading_value,
        total_stocks,
        up_stocks,
        down_stocks,
        unchanged_stocks,
        leader_stock_codes
    FROM industry_stats
    ORDER BY weighted_change_rate DESC
    """
    
    results = []
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (date, date))
        rows = cursor.fetchall()
        
        for rank, row in enumerate(rows, 1):  # 순위는 1부터 시작
            result = {
                'id': row[0],
                'name': row[1],
                'change_rate': row[2],
                'volume': row[3],
                'market_cap': row[4],
                'trading_value': row[5],
                'total_stocks': row[6],
                'up_stocks': row[7],
                'down_stocks': row[8],
                'unchanged_stocks': row[9],
                'leader_stocks': row[10],
                'rank': rank  # 순위 정보 추가
            }
            results.append(result)
            
            if save_to_db:
                with sqlite3.connect(THEME_INDUSTRY_DB) as perf_conn:
                    perf_conn.execute("""
                        INSERT OR REPLACE INTO industry_daily_performance
                        (industry_id, date, price_change_ratio, volume, market_cap, trading_value,
                         leader_stock_codes, rank)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (row[0], date, row[2], row[3], row[4], row[5], row[10], rank))
    
    return results

def get_theme_performance(date: str = None, save_to_db: bool = True) -> List[Dict]:
    """
    테마별 등락률을 시가총액 가중평균으로 계산하고 선택적으로 DB에 저장
    
    Args:
        date: 날짜 (YYYY-MM-DD). None인 경우 최근 거래일 사용
        save_to_db: DB에 결과를 저장할지 여부
        
    Returns:
        테마별 등락률 리스트 (시가총액 가중평균 기준 내림차순 정렬)
    """
    if not date:
        date = get_market_date()
        
    query = """
    WITH theme_stats AS (
        SELECT 
            t.theme_id,
            t.theme_name,
            ROUND(AVG(d.price_change_ratio), 2) as simple_change_rate,  -- 단순 평균
            ROUND(SUM(d.price_change_ratio * d.market_cap) / SUM(d.market_cap), 2) as weighted_change_rate,  -- 시가총액 가중평균 (참고용)
            SUM(d.volume) as total_volume,
            SUM(d.market_cap) as total_market_cap,
            SUM(d.trading_value) as total_trading_value,
            COUNT(DISTINCT m.stock_code) as total_stocks,
            SUM(CASE WHEN d.price_change_ratio > 0 THEN 1 ELSE 0 END) as up_stocks,
            SUM(CASE WHEN d.price_change_ratio < 0 THEN 1 ELSE 0 END) as down_stocks,
            SUM(CASE WHEN d.price_change_ratio = 0 THEN 1 ELSE 0 END) as unchanged_stocks,
            GROUP_CONCAT(
                CASE 
                    WHEN d.market_cap >= (SELECT market_cap FROM DailyStocks d2 
                                        WHERE d2.stock_code = m.stock_code 
                                        AND d2.date = ? 
                                        ORDER BY d2.market_cap DESC 
                                        LIMIT 1 OFFSET 4) 
                    THEN m.stock_code 
                END
            ) as leader_stock_codes
        FROM theme_master t
        JOIN theme_stock_mapping m ON t.theme_id = m.theme_id
        JOIN DailyStocks d ON m.stock_code = d.stock_code
        WHERE d.date = ?
        GROUP BY t.theme_id, t.theme_name
    )
    SELECT 
        theme_id,
        theme_name,
        simple_change_rate as weighted_change_rate,  -- 단순 평균을 주 등락률로 사용
        weighted_change_rate as market_cap_weighted_rate,  -- 시가총액 가중평균은 참고용으로 저장
        total_volume,
        total_market_cap,
        total_trading_value,
        total_stocks,
        up_stocks,
        down_stocks,
        unchanged_stocks,
        leader_stock_codes
    FROM theme_stats
    ORDER BY simple_change_rate DESC  -- 정렬 기준도 단순 평균으로 변경
    """
    
    results = []
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (date, date))
        rows = cursor.fetchall()
        
        for rank, row in enumerate(rows, 1):  # 순위는 1부터 시작
            result = {
                'id': row[0],
                'name': row[1],
                'change_rate': row[2],
                'volume': row[4],
                'market_cap': row[5],
                'trading_value': row[6],
                'total_stocks': row[7],
                'up_stocks': row[8],
                'down_stocks': row[9],
                'unchanged_stocks': row[10],
                'leader_stocks': row[11],
                'rank': rank  # 순위 정보 추가
            }
            results.append(result)
            
            if save_to_db:
                with sqlite3.connect(THEME_INDUSTRY_DB) as perf_conn:
                    perf_conn.execute("""
                        INSERT OR REPLACE INTO theme_daily_performance
                        (theme_id, date, price_change_ratio, market_cap_weighted_ratio, volume, market_cap, 
                         trading_value, leader_stock_codes, rank)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (row[0], date, row[2], row[3], row[4], row[5], row[6], row[11], rank))
    
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
        print(f"- {i['name']}: {i['change_rate']}% (상승 {i['up_stocks']}, 하락 {i['down_stocks']}")
        
    print(f"\n[{target_date}] 기준 상위 5개 테마:")
    top_themes = get_theme_performance(target_date, save_to_db=False)
    for t in top_themes[:5]:
        print(f"- {t['name']}: {t['change_rate']}% (상승 {t['up_stocks']}, 하락 {t['down_stocks']}") 