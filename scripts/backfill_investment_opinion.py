"""
[임시 스크립트] 투자 의견(investment_opinion) 자동 생성/보충용

- 목적: momentum_analysis 테이블의 과거 모든 날짜에 대해 trend_score 기준으로 투자 의견(매수/매도/보유 등)을 자동 생성 및 investment_opinion 테이블에 저장
- 사용법: python scripts/backfill_investment_opinion.py
- 주의: 이미 저장된 날짜의 의견은 덮어쓸 수 있음. DB 백업 후 실행 권장
- 재사용: 과거 데이터 보정, 전략 백테스트, 신규 데이터 적재 시 반복 사용 가능
"""
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from src.analyzer.investment_analyzer import InvestmentAnalyzer
import sqlite3

# DB에서 날짜 리스트 추출
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../db/theme_industry.db'))

def get_all_dates():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT date FROM momentum_analysis ORDER BY date ASC;")
        return [row[0] for row in cursor.fetchall()]

def main():
    analyzer = InvestmentAnalyzer(theme_db_path=DB_PATH)
    dates = get_all_dates()
    print(f"[INFO] 총 {len(dates)}개 날짜에 대해 투자 의견을 생성합니다.")
    for date in dates:
        print(f"[RUN] {date} 분석...")
        analyzer.analyze(date)
    print("[DONE] 모든 날짜에 대한 투자 의견 생성 완료.")

if __name__ == "__main__":
    main() 