import os
import sys
import sqlite3
import pandas as pd
from datetime import datetime
from src.analyzer.trend_score_utils import calc_trend_score, normalize_score, score_to_opinion

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

# [구조] 현재 투자의견 산출에는 market_index_daily(지수 모멘텀) 데이터가 직접 반영되지 않음
# - 업종/테마 자체의 모멘텀/지표만으로 trend_score, opinion_type 산출
# - 실전: momentum_weights_active.csv, 실험/리포트: optimized_momentum_weights.csv 등 별도 파일

def load_weights_from_csv(csv_path='results/momentum_weights_active.csv'):
    """
    가중치 CSV(가로형)에서 is_active=1, 최신 timestamp 세트의 가중치를 딕셔너리로 반환
    """
    df = pd.read_csv(csv_path)
    # is_active가 int가 아닐 경우를 대비해 변환
    if df['is_active'].dtype != int:
        df['is_active'] = df['is_active'].astype(int)
    active = df[df['is_active'] == 1]
    if active.empty:
        raise ValueError('활성화된(is_active=1) 가중치 세트가 없습니다.')
    # 최신 timestamp
    latest_time = active['timestamp'].max()
    latest_set = active[active['timestamp'] == latest_time]
    if isinstance(latest_set, pd.DataFrame):
        latest_set = latest_set.iloc[0]
    # factor 컬럼만 추출
    factor_cols = [col for col in df.columns if col not in ['timestamp','tag','is_active','comment']]
    weights = {col: float(latest_set[col]) for col in factor_cols}
    print(f"[load_weights_from_csv] 적용 가중치: {weights}")
    return weights

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
                df = pd.read_sql_query(query, conn, params=[date])
            print(f"[fetch_momentum_data] {date} row 수: {len(df)}")
            if not df.empty:
                for col in ['target_id','target_type','trend_score','price_momentum_1d','leader_momentum']:
                    if col in df.columns:
                        print(f"  {col} 결측치: {df[col].isna().mean()*100:.1f}% (샘플: {df[col].head(3).tolist()})")
            if df.empty:
                print(f"[WARN] {date}에 대한 모멘텀 데이터가 없습니다.")
            return df
        except Exception as e:
            print(f"[ERROR] 모멘텀 데이터 로딩 중 오류 발생: {e}")
            return pd.DataFrame()

    def calculate_trend_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        종합 추세 강도 점수(trend_score)를 계산합니다.
        (공통 모듈 함수로 일원화)
        """
        print("[calculate_trend_score] trend_score 계산 중...")
        df.fillna(0, inplace=True)
        weights = load_weights_from_csv()
        # 1. raw score 계산 (row-wise)
        df['trend_score_raw'] = df.apply(lambda row: calc_trend_score(row, weights), axis=1)
        # 2. min/max 구해서 0~100 정규화
        min_val = df['trend_score_raw'].min()
        max_val = df['trend_score_raw'].max()
        df['trend_score'] = df['trend_score_raw'].apply(lambda x: normalize_score(x, min_val, max_val))
        print(f"[calculate_trend_score] trend_score 결측치: {df['trend_score'].isna().mean()*100:.1f}% (샘플: {df['trend_score'].head(3).tolist()})")
        print(f"[calculate_trend_score] 통계: min={df['trend_score'].min()}, max={df['trend_score'].max()}, mean={df['trend_score'].mean():.2f}")
        return df

    def generate_opinions(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        분석 데이터를 기반으로 투자 의견을 생성합니다.
        (공통 모듈 함수로 일원화)
        """
        print("[generate_opinions] 투자 의견 생성 중...")
        df['opinion_type'] = df['trend_score'].apply(score_to_opinion)
        print("[generate_opinions] 등급별 분포:")
        for op in ['STRONG_BUY','BUY','HOLD','SELL']:
            print(f"  {op}: {(df['opinion_type']==op).sum()}개")
        print("[generate_opinions] 샘플:")
        print(df[['target_id','trend_score','opinion_type']].head(3))
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

        print(f"[save_analysis_results] {len(df)}개 row 저장 시도...")
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
        print(f"\n{'='*30}\n[투자의견분석] 실행 시작: {date}")
        analysis_df = self.fetch_momentum_data(date)
        if analysis_df.empty:
            print(f"[FAIL] {date} 분석을 중단합니다.")
            return
        print(f"[INFO] {date}의 모멘텀 데이터 {len(analysis_df)}건 로딩 완료.")
        analysis_df = self.calculate_trend_score(analysis_df)
        final_df = self.generate_opinions(analysis_df)
        self.save_analysis_results(final_df, date)
        print(f"[투자의견분석] 실행 종료: {date}\n{'='*30}")


if __name__ == '__main__':
    from src.utils.market_time import get_market_date

    # 클래스 사용 예시
    # 특정 날짜를 지정하거나, 최근 거래일을 사용
    analysis_date = get_market_date() 
    
    analyzer = InvestmentAnalyzer()
    analyzer.analyze(date=analysis_date) 