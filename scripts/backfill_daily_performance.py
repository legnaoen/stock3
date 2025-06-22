import os
import sys
import sqlite3
from datetime import datetime, timedelta
import pandas as pd

# 프로젝트 루트를 경로에 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.analyzer.sector_theme_analyzer import get_industry_performance, get_theme_performance
from src.utils.market_time import get_market_date

# venv 활성화 체크
if os.name != 'nt':
    if not hasattr(sys, 'base_prefix') or sys.prefix == sys.base_prefix:
        print("[ERROR] 반드시 venv(가상환경)에서 실행해야 합니다.")
        exit(1)
    
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(PROJECT_ROOT, 'db', 'stock_master.db')
THEME_INDUSTRY_DB = os.path.join(PROJECT_ROOT, 'db', 'theme_industry.db')

# 업종/테마 일별 성과 데이터 자동 보충 스크립트
# - 목적: DailyStocks 기준으로 업종/테마별 일일 성과 데이터를 자동으로 계산/DB에 보충
# - 사용법: python scripts/backfill_daily_performance.py [--start YYYY-MM-DD --end YYYY-MM-DD]

def get_existing_dates(target_type: str) -> set:
    """DB에 이미 존재하는 데이터의 날짜를 집합 형태로 반환"""
    table_name = f"{target_type.lower()}_daily_performance"
    with sqlite3.connect(THEME_INDUSTRY_DB) as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT DISTINCT date FROM {table_name}")
        return {row[0] for row in cursor.fetchall()}

def get_available_dates_from_daily_stocks(start_date: str, end_date: str) -> list:
    """DailyStocks 테이블에서 해당 기간에 존재하는 거래일 목록을 반환"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        query = "SELECT DISTINCT date FROM DailyStocks WHERE date BETWEEN ? AND ? ORDER BY date"
        cursor.execute(query, (start_date, end_date))
        return [row[0] for row in cursor.fetchall()]

def backfill_performance_data(start_date: str, end_date: str):
    """
    지정된 기간 동안의 업종/테마 일일 성과 데이터를 채워넣습니다.
    """
    print(f"[INFO] 데이터 채우기 시작: {start_date} ~ {end_date}")

    # 1. 대상 거래일 목록 가져오기
    print("[INFO] DailyStocks 테이블에서 유효한 거래일 목록을 조회합니다...")
    available_dates = get_available_dates_from_daily_stocks(start_date, end_date)
    if not available_dates:
        print("[WARN] 해당 기간에 DailyStocks 데이터가 없습니다. 작업을 중단합니다.")
        return
    print(f"[INFO] 총 {len(available_dates)}일의 거래일이 확인되었습니다.")

    # 2. 이미 처리된 날짜 가져오기
    existing_industry_dates = get_existing_dates('INDUSTRY')
    existing_theme_dates = get_existing_dates('THEME')

    # 3. 날짜별로 반복하며 데이터 채우기
    for date_str in available_dates:
        print(f"\n--- {date_str} 데이터 처리 중 ---")

        # 업종 데이터 처리
        if date_str in existing_industry_dates:
            print(f"[SKIP] {date_str}의 업종 데이터는 이미 존재합니다.")
        else:
            print(f"[RUN] {date_str}의 업종 성과 데이터를 계산하고 저장합니다...")
            try:
                industry_results = get_industry_performance(date=date_str, save_to_db=True)
                print(f"  - 성공: {len(industry_results)}개의 업종 데이터 저장 완료.")
            except Exception as e:
                print(f"  - 오류: 업종 데이터 처리 중 오류 발생 - {e}")

        # 테마 데이터 처리
        if date_str in existing_theme_dates:
            print(f"[SKIP] {date_str}의 테마 데이터는 이미 존재합니다.")
        else:
            print(f"[RUN] {date_str}의 테마 성과 데이터를 계산하고 저장합니다...")
            try:
                theme_results = get_theme_performance(date=date_str, save_to_db=True)
                print(f"  - 성공: {len(theme_results)}개의 테마 데이터 저장 완료.")
            except Exception as e:
                print(f"  - 오류: 테마 데이터 처리 중 오류 발생 - {e}")
                
    print("\n[SUCCESS] 모든 데이터 채우기 작업이 완료되었습니다.")


if __name__ == '__main__':
    # --- 설정 ---
    # 데이터가 부족한 기간을 자동으로 설정 (오늘로부터 30일 전까지)
    end_date_obj = datetime.strptime(get_market_date(), '%Y-%m-%d')
    start_date_obj = end_date_obj - timedelta(days=30)
    
    # argparse를 사용하여 커맨드라인에서 날짜를 받을 수도 있습니다.
    # 예: python scripts/backfill_daily_performance.py --start 2025-06-01 --end 2025-06-20
    
    import argparse
    parser = argparse.ArgumentParser(description="업종/테마의 과거 일일 성과 데이터를 채워넣는 스크립트")
    parser.add_argument('--start', default=start_date_obj.strftime('%Y-%m-%d'), help="시작 날짜 (YYYY-MM-DD)")
    parser.add_argument('--end', default=end_date_obj.strftime('%Y-%m-%d'), help="종료 날짜 (YYYY-MM-DD)")
    
    args = parser.parse_args()

    backfill_performance_data(args.start, args.end) 