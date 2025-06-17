import os
import sys
import sqlite3
from datetime import datetime
from typing import List, Dict

# venv 활성화 체크
if sys.prefix == sys.base_prefix:
    print("[ERROR] 반드시 venv(가상환경)에서 실행해야 합니다.")
    sys.exit(1)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logger import setup_logger

logger = setup_logger()

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../db/stock_master.db'))
THEME_INDUSTRY_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../db/theme_industry.db'))

def get_today() -> str:
    """오늘 날짜를 YYYY-MM-DD 형식으로 반환"""
    return datetime.today().strftime('%Y-%m-%d')

def get_sector_info(sector_type: str, sector_id: int, date: str = None) -> Dict:
    """테마/업종 기본 정보 조회"""
    if not date:
        date = get_today()
        
    if sector_type not in ['theme', 'industry']:
        raise ValueError("sector_type must be either 'theme' or 'industry'")
        
    query = f"""
    SELECT 
        t.{sector_type}_name as name,
        p.price_change_ratio,
        p.volume,
        p.market_cap,
        p.trading_value,
        (
            SELECT COUNT(DISTINCT m.stock_code)
            FROM {sector_type}_stock_mapping m
            WHERE m.{sector_type}_id = t.{sector_type}_id
        ) as total_stocks,
        (
            SELECT COUNT(DISTINCT m.stock_code)
            FROM {sector_type}_stock_mapping m
            JOIN DailyStocks d ON m.stock_code = d.stock_code
            WHERE m.{sector_type}_id = t.{sector_type}_id
            AND d.date = ?
            AND d.price_change_ratio > 0
        ) as up_stocks,
        (
            SELECT COUNT(DISTINCT m.stock_code)
            FROM {sector_type}_stock_mapping m
            JOIN DailyStocks d ON m.stock_code = d.stock_code
            WHERE m.{sector_type}_id = t.{sector_type}_id
            AND d.date = ?
            AND d.price_change_ratio < 0
        ) as down_stocks
    FROM {sector_type}_master t
    LEFT JOIN {sector_type}_daily_performance p 
        ON t.{sector_type}_id = p.{sector_type}_id AND p.date = ?
    WHERE t.{sector_type}_id = ?
    """
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (date, date, date, sector_id))
            row = cursor.fetchone()
            
            if not row:
                return None
                
            return {
                'name': row[0],
                'price_change_ratio': row[1] if row[1] is not None else 0.0,
                'volume': row[2] if row[2] is not None else 0,
                'market_cap': row[3] if row[3] is not None else 0,
                'trading_value': row[4] if row[4] is not None else 0,
                'total_stocks': row[5],
                'up_stocks': row[6],
                'down_stocks': row[7]
            }
    except Exception as e:
        logger.error(f"Error getting sector info: {str(e)}")
        raise

def get_sector_stocks(sector_type: str, sector_id: int, date: str = None) -> List[Dict]:
    """테마/업종에 속한 종목 리스트와 상세 정보 조회 (주가 데이터가 없어도 종목은 항상 표시)"""
    if not date:
        date = get_today()
        
    if sector_type not in ['theme', 'industry']:
        raise ValueError("sector_type must be either 'theme' or 'industry'")
        
    query = f"""
    SELECT 
        s.stock_code,
        s.stock_name,
        d.price_change_ratio,
        d.close_price,
        d.volume,
        d.trading_value,
        d.market_cap
    FROM {sector_type}_stock_mapping m
    JOIN Stocks s ON m.stock_code = s.stock_code
    LEFT JOIN DailyStocks d ON s.stock_code = d.stock_code AND d.date = ?
    WHERE m.{sector_type}_id = ?
    ORDER BY d.price_change_ratio DESC
    """
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (date, sector_id))
            rows = cursor.fetchall()
            
            return [{
                'stock_code': row[0],
                'stock_name': row[1],
                'price_change_ratio': row[2] if row[2] is not None else 0.0,
                'close_price': row[3] if row[3] is not None else '-',
                'volume': row[4] if row[4] is not None else '-',
                'trading_value': row[5] if row[5] is not None else '-',
                'market_cap': row[6] if row[6] is not None else '-'
            } for row in rows]
    except Exception as e:
        logger.error(f"Error getting sector stocks: {str(e)}")
        raise

if __name__ == "__main__":
    # 테스트 코드
    test_theme_id = 1  # 테스트용 테마 ID
    test_industry_id = 1  # 테스트용 업종 ID
    
    print("\n=== 테마 정보 테스트 ===")
    theme_info = get_sector_info('theme', test_theme_id)
    if theme_info:
        print(f"테마명: {theme_info['name']}")
        print(f"등락률: {theme_info['price_change_ratio']}%")
        print(f"종목수: {theme_info['total_stocks']} (상승 {theme_info['up_stocks']}, 하락 {theme_info['down_stocks']})")
    
    print("\n=== 테마 종목 리스트 테스트 ===")
    theme_stocks = get_sector_stocks('theme', test_theme_id)
    for stock in theme_stocks[:5]:  # 상위 5개만 출력
        print(f"{stock['stock_name']}: {stock['price_change_ratio']}%") 