import os
import sys
import sqlite3
import pandas as pd
from datetime import datetime

# 프로젝트 루트를 경로에 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# venv 활성화 체크
if os.name != 'nt':
    if not hasattr(sys, 'base_prefix') or sys.prefix == sys.base_prefix:
        print("[ERROR] 반드시 venv(가상환경)에서 실행해야 합니다.")
        exit(1)

# 모멘텀/RSI 등 지표 기반 종합 투자 의견(STRONG_BUY/BUY/HOLD/SELL) 자동 생성 모듈
# - 목적: momentum_analysis의 기초 지표를 바탕으로 종합 추세 점수 및 투자 의견 생성/DB 저장
# - 사용법: InvestmentAnalyzer 클래스 활용

class InvestmentAnalyzer:
    """
    기초 분석 데이터(모멘텀, RSI 등)를 바탕으로 종합적인 투자 의견을 생성하는 클래스.

    [역할과 책임 (Role & Responsibilities)]
    - `MomentumAnalyzer`가 생성한 완전한 기초 데이터를 `momentum_analysis` 테이블에서 읽어옵니다.
    - 기초 데이터를 조합하여 '종합 추세 점수(trend_score)'와 같은 고차원적인 분석 지표를 계산합니다.
    - 최종적으로 '투자 의견(opinion_type)'을 생성하고 `investment_opinion` 테이블에 저장합니다.
    - 이 분석기는 기초 데이터 계산 로직을 포함하지 않으며, 반드시 `MomentumAnalyzer` 실행 이후에 동작해야 합니다.
    """
    def __init__(self, theme_db_path='db/theme_industry.db'):
        """
        분석기 초기화. 데이터베이스 경로를 설정합니다.
        """
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.theme_db_path = os.path.join(project_root, theme_db_path)
        
        if not os.path.exists(self.theme_db_path):
            raise FileNotFoundError(f"테마/업종 DB 파일을 찾을 수 없습니다: {self.theme_db_path}")

    def _get_theme_db_connection(self):
        """테마/업종 DB 연결을 반환합니다."""
        return sqlite3.connect(self.theme_db_path)

    def fetch_momentum_data(self, date: str) -> pd.DataFrame:
        """
        지정된 날짜의 모든 모멘텀 분석 데이터를 불러옵니다.
        (모든 기초 지표 계산은 momentum_analyzer에서 완료됨)
        """
        query = "SELECT * FROM momentum_analysis WHERE date = ?"
        try:
            with self._get_theme_db_connection() as conn:
                df = pd.read_sql_query(query, conn, params=(date,))
            if df.empty:
                print(f"[WARN] {date}에 대한 모멘텀 데이터가 없습니다.")
            return df
        except Exception as e:
            print(f"[ERROR] 모멘텀 데이터 로딩 중 오류 발생: {e}")
            return pd.DataFrame()

    def calculate_trend_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        종합 추세 강도 점수(trend_score)를 계산합니다.
        점수는 0~100 사이 값으로 정규화될 수 있으나, 여기서는 가중치 합으로 계산합니다.
        """
        print("[INFO] 종합 추세 강도 점수 계산 중...")
        df.fillna(0, inplace=True)

        price_score = (
            df['price_momentum_1d'] * 0.2 +
            df['price_momentum_3d'] * 0.3 +
            df['price_momentum_5d'] * 0.3 +
            df['price_momentum_10d'] * 0.2
        )
        
        volume_score = (
            df['volume_momentum_1d'] * 0.3 +
            df['volume_momentum_3d'] * 0.4 +
            df['volume_momentum_5d'] * 0.3
        )
        
        # 주도주 모멘텀과 수에 가중치를 부여.
        leader_score = (
            df['leader_momentum'] * 0.6 +
            (df['leader_count'] / 5).clip(0, 1) * 0.4 # 주도주는 최대 5개이므로 5로 나눔
        )
        
        rsi_score = (df['rsi_value'] - 50) * 0.1
        
        df['trend_score'] = (price_score * 0.4) + (volume_score * 0.3) + (leader_score * 0.3) + rsi_score
        df['trend_score'] = df['trend_score'].clip(0, 100)
        
        print("[INFO] 추세 점수 계산 완료.")
        return df

    def generate_opinions(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        분석 데이터를 기반으로 투자 의견을 생성합니다.
        """
        print("[INFO] 투자 의견 생성 중...")
        def get_opinion(score):
            if score >= 80: return 'STRONG_BUY'
            elif score >= 60: return 'BUY'
            elif score >= 40: return 'HOLD'
            else: return 'SELL'
        df['opinion_type'] = df['trend_score'].apply(get_opinion)
        print("[INFO] 투자 의견 생성 완료.")
        return df

    def save_analysis_results(self, df: pd.DataFrame, date: str):
        """
        분석 결과를 각 테이블에 저장합니다.
        - trend_score는 momentum_analysis 테이블에 업데이트
        - 투자 의견은 investment_opinion 테이블에 저장
        """
        if df.empty:
            print("[WARN] 저장할 분석 데이터가 없습니다.")
            return

        print(f"[INFO] {len(df)}개의 trend_score를 momentum_analysis 테이블에 업데이트합니다...")
        try:
            with self._get_theme_db_connection() as conn:
                cursor = conn.cursor()
                update_data = [
                    (row['trend_score'], row['target_id'], row['target_type'], row['date'])
                    for _, row in df.iterrows()
                ]
                cursor.executemany(
                    "UPDATE momentum_analysis SET trend_score = ? WHERE target_id = ? AND target_type = ? AND date = ?",
                    update_data
                )
                conn.commit()
                print("[SUCCESS] trend_score 업데이트 완료.")
        except Exception as e:
            print(f"[ERROR] trend_score 업데이트 중 오류 발생: {e}")

        print(f"[INFO] {len(df)}개의 투자 의견을 investment_opinion 테이블에 저장합니다...")
        opinions_to_save = df[['target_id', 'target_type', 'date', 'opinion_type']].copy()
        try:
            with self._get_theme_db_connection() as conn:
                cursor = conn.cursor()
                delete_query = "DELETE FROM investment_opinion WHERE date = ?"
                cursor.execute(delete_query, (date,))
                opinions_to_save.to_sql('investment_opinion', conn, if_exists='append', index=False)
                print(f"[SUCCESS] 투자 의견 저장 완료.")
        except Exception as e:
            print(f"[ERROR] 투자 의견 저장 중 오류 발생: {e}")

    def analyze(self, date: str):
        """
        지정된 날짜에 대한 투자 의견 분석을 수행합니다.
        """
        print(f"--- {date} 투자 의견 분석 시작 ---")
        
        analysis_df = self.fetch_momentum_data(date)
        if analysis_df.empty:
            print(f"[FAIL] {date} 분석을 중단합니다.")
            return

        print(f"[INFO] {date}의 모멘텀 데이터 {len(analysis_df)}건 로딩 완료.")
        
        analysis_df = self.calculate_trend_score(analysis_df)
        final_df = self.generate_opinions(analysis_df)
        self.save_analysis_results(final_df, date)

        print("\n[ 최종 분석 요약 ]")
        print(final_df[['target_id', 'target_type', 'trend_score', 'opinion_type']].sort_values(by='trend_score', ascending=False).head(10))


if __name__ == '__main__':
    from src.utils.market_time import get_market_date

    # 클래스 사용 예시
    # 특정 날짜를 지정하거나, 최근 거래일을 사용
    analysis_date = get_market_date() 
    
    analyzer = InvestmentAnalyzer()
    analyzer.analyze(date=analysis_date) 