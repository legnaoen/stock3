import os
import sys
import sqlite3
import pandas as pd
from datetime import datetime

# 프로젝트 루트를 경로에 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# venv 활성화 체크
if sys.prefix == sys.base_prefix:
    print("[ERROR] 반드시 venv(가상환경)에서 실행해야 합니다.")
    sys.exit(1)

class InvestmentAnalyzer:
    """
    기초 분석 데이터(모멘텀, RSI 등)를 바탕으로 종합적인 투자 의견을 생성하는 클래스.

    [역할과 책임 (Role & Responsibilities)]
    - `MomentumAnalyzer`가 생성한 기초 데이터를 `momentum_analysis` 테이블에서 읽어옵니다.
    - 기초 데이터를 조합하여 '종합 추세 점수(trend_score)'와 같은 고차원적인 분석 지표를 계산합니다.
    - 최종적으로 '투자 의견(opinion_type)'을 생성하고 `investment_opinion` 테이블에 저장합니다.
    - 이 분석기는 기초 데이터 계산 로직을 포함하지 않으며, 반드시 `MomentumAnalyzer` 실행 이후에 동작해야 합니다.

    [종합 추세 점수 (Trend Score) 계산 로직]
    - 목적: 시장의 추세를 '방향성', '신뢰도', '질'의 관점에서 종합적으로 평가.
    - 계산식: `trend_score` = (가격 점수 * 0.4) + (거래대금 점수 * 0.3) + (주도주 점수 * 0.3) + (RSI 가점)
      1. 가격 모멘텀 (40%): 추세의 방향성. 단기~중기 추세 반영.
         - (price_momentum_1d*0.2 + 3d*0.3 + 5d*0.3 + 10d*0.2)
      2. 거래대금 모멘텀 (30%): 추세의 신뢰도. 거래가 실린 움직임에 가중치.
         - (volume_momentum_1d*0.3 + 3d*0.4 + 5d*0.3)
      3. 주도주 강도 (30%): 추세의 질. 테마를 이끄는 주도주의 실제 성과 반영.
         - (leader_momentum*0.6 + (leader_count/10)*0.4)
      4. RSI (보너스/패널티): 과매수/과매도 조정.
         - ((rsi_value - 50) * 0.1)
    - 비고: 모든 가중치와 계산식은 향후 백테스팅을 통해 고도화될 수 있음.
    """
    def __init__(self, theme_db_path='db/theme_industry.db', master_db_path='db/stock_master.db'):
        """
        분석기 초기화. 데이터베이스 경로를 설정합니다.
        """
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.theme_db_path = os.path.join(project_root, theme_db_path)
        self.master_db_path = os.path.join(project_root, master_db_path)
        
        if not os.path.exists(self.theme_db_path):
            raise FileNotFoundError(f"테마/업종 DB 파일을 찾을 수 없습니다: {self.theme_db_path}")
        if not os.path.exists(self.master_db_path):
            raise FileNotFoundError(f"마스터 DB 파일을 찾을 수 없습니다: {self.master_db_path}")

    def _get_theme_db_connection(self):
        """테마/업종 DB 연결을 반환합니다."""
        return sqlite3.connect(self.theme_db_path)
    
    def _get_master_db_connection(self):
        """마스터 DB 연결을 반환합니다."""
        return sqlite3.connect(self.master_db_path)

    def fetch_momentum_data(self, date: str) -> pd.DataFrame:
        """
        지정된 날짜의 모멘텀 분석 데이터를 불러옵니다.
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

    def fetch_leader_stock_data(self, date: str) -> pd.DataFrame:
        """
        지정된 날짜의 업종/테마별 주도주 정보를 불러옵니다.
        - 주도주 코드 리스트
        - 주도주 수
        - 주도주 평균 등락률
        """
        query = """
        WITH combined_performance AS (
            SELECT 'INDUSTRY' as target_type, industry_id as target_id, leader_stock_codes FROM industry_daily_performance WHERE date = ?
            UNION ALL
            SELECT 'THEME' as target_type, theme_id as target_id, leader_stock_codes FROM theme_daily_performance WHERE date = ?
        )
        SELECT * FROM combined_performance WHERE leader_stock_codes IS NOT NULL AND leader_stock_codes != ''
        """
        try:
            with self._get_theme_db_connection() as conn:
                # 1. 주도주 코드 목록 가져오기
                leaders_df = pd.read_sql_query(query, conn, params=(date, date))

            if leaders_df.empty:
                return pd.DataFrame()

            # 2. 모든 주도주 코드를 한번에 조회하기 위해 집합으로 만들기
            all_leader_codes = set()
            leaders_df['leader_stock_codes'].str.split(',').apply(lambda x: all_leader_codes.update(x))
            
            if not all_leader_codes:
                return pd.DataFrame()

            # 3. DailyStocks에서 해당 종목들의 등락률 가져오기
            stock_query = f"SELECT stock_code, price_change_ratio FROM DailyStocks WHERE date = ? AND stock_code IN ({','.join(['?']*len(all_leader_codes))})"
            with self._get_master_db_connection() as master_conn:
                stock_perf_df = pd.read_sql_query(stock_query, master_conn, params=[date] + list(all_leader_codes))
            
            stock_perf_map = stock_perf_df.set_index('stock_code')['price_change_ratio'].to_dict()

            # 4. 주도주 수와 평균 등락률 계산
            def calculate_leader_metrics(codes_str):
                if not codes_str:
                    return 0, 0.0
                codes = codes_str.split(',')
                
                valid_perfs = [stock_perf_map.get(c) for c in codes if stock_perf_map.get(c) is not None]
                
                count = len(valid_perfs)
                momentum = sum(valid_perfs) / count if count > 0 else 0.0
                return count, round(momentum, 2)

            leaders_df[['leader_count', 'leader_momentum']] = leaders_df['leader_stock_codes'].apply(
                lambda x: pd.Series(calculate_leader_metrics(x))
            )

            return leaders_df[['target_id', 'target_type', 'leader_count', 'leader_momentum']]

        except Exception as e:
            print(f"[ERROR] 주도주 데이터 로딩 중 오류 발생: {e}")
            return pd.DataFrame()

    def calculate_trend_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        종합 추세 강도 점수(trend_score)를 계산합니다.
        점수는 0~100 사이 값으로 정규화될 수 있으나, 여기서는 가중치 합으로 계산합니다.
        """
        print("[INFO] 종합 추세 강도 점수 계산 중...")

        # 각 점수를 계산하기 전에 NaN 값을 0으로 채움
        df.fillna(0, inplace=True)

        # 가격 모멘텀 점수 (40점 만점)
        # 각 기간의 가중치를 곱하여 합산.
        price_score = (
            df['price_momentum_1d'] * 0.2 +
            df['price_momentum_3d'] * 0.3 +
            df['price_momentum_5d'] * 0.3 +
            df['price_momentum_10d'] * 0.2
        )
        # 점수화 (단순 가중치, 정규화는 추후 개선)
        df['price_score'] = price_score * 0.4 # 가중치 40%

        # 거래대금 모멘텀 점수 (30점 만점)
        volume_score = (
            df['volume_momentum_1d'] * 0.3 +
            df['volume_momentum_3d'] * 0.4 +
            df['volume_momentum_5d'] * 0.3
        )
        df['volume_score'] = volume_score * 0.3 # 가중치 30%

        # 주도주 강도 점수 (30점 만점)
        # 주도주 모멘텀과 수에 가중치를 부여.
        # leader_count는 최대 10개 정도로 가정하고 점수화
        leader_score = (
            df['leader_momentum'] * 0.6 +
            (df['leader_count'] / 10).clip(0, 1) * 0.4 
        )
        df['leader_score'] = leader_score * 0.3 # 가중치 30%
        
        # RSI 점수 (보너스 또는 패널티)
        # RSI가 70 이상이면 과매수, 30 이하면 과매도. 50이 중립.
        # 여기서는 단순 합산을 위해 50을 빼서 0을 중립으로 만듦.
        rsi_score = (df['rsi_value'] - 50) * 0.1 # 전체 점수에 미치는 영향력 10%
        
        # 최종 종합 점수
        df['trend_score'] = (df['price_score'] + df['volume_score'] + df['leader_score'] + rsi_score)
        
        # 최종 점수를 0~100 사이로 클리핑
        df['trend_score'] = df['trend_score'].clip(0, 100)
        
        print("[INFO] 추세 점수 계산 완료.")
        return df

    def generate_opinions(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        분석 데이터를 기반으로 투자 의견을 생성합니다.
        """
        print("[INFO] 투자 의견 생성 중...")

        def get_opinion(score):
            if score >= 80:
                return 'STRONG_BUY'
            elif score >= 60:
                return 'BUY'
            elif score >= 40:
                return 'HOLD'
            else:
                return 'SELL'

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

        # 1. trend_score 업데이트
        print(f"[INFO] {len(df)}개의 trend_score를 momentum_analysis 테이블에 업데이트합니다...")
        try:
            with self._get_theme_db_connection() as conn:
                cursor = conn.cursor()
                # [BUG FIX] df.to_records()는 executemany에 필요한 파라미터 순서를 보장하지 않아
                # UPDATE가 실패하는 문제를 야기할 수 있습니다.
                # 따라서 명시적으로 튜플 리스트를 생성하여 파라미터 순서를 보장합니다.
                update_data = [
                    (row['trend_score'], row['target_id'], row['target_type'], row['date'])
                    for index, row in df.iterrows()
                ]
                
                cursor.executemany(
                    "UPDATE momentum_analysis SET trend_score = ? WHERE target_id = ? AND target_type = ? AND date = ?",
                    update_data
                )
                conn.commit()
                print("[SUCCESS] trend_score 업데이트 완료.")
        except Exception as e:
            print(f"[ERROR] trend_score 업데이트 중 오류 발생: {e}")


        # 2. investment_opinion 저장
        print(f"[INFO] {len(df)}개의 투자 의견을 investment_opinion 테이블에 저장합니다...")
        opinions_to_save = df[['target_id', 'target_type', 'date', 'opinion_type']].copy()
        try:
            with self._get_theme_db_connection() as conn:
                cursor = conn.cursor()
                
                # 해당 날짜의 기존 데이터 삭제
                delete_query = "DELETE FROM investment_opinion WHERE date = ?"
                cursor.execute(delete_query, (date,))
                
                # 새 데이터 추가
                opinions_to_save.to_sql('investment_opinion', conn, if_exists='append', index=False)
                
                print(f"[SUCCESS] 투자 의견 저장 완료.")

        except Exception as e:
            print(f"[ERROR] 투자 의견 저장 중 오류 발생: {e}")


    def analyze(self, date: str):
        """
        지정된 날짜에 대한 투자 의견 분석을 수행합니다.
        """
        print(f"--- {date} 투자 의견 분석 시작 ---")
        
        # 1. 기초 모멘텀 데이터 로딩
        momentum_df = self.fetch_momentum_data(date)
        if momentum_df.empty:
            print(f"[FAIL] {date} 분석을 중단합니다.")
            return

        print(f"[INFO] {date}의 모멘텀 데이터 {len(momentum_df)}건 로딩 완료.")
        
        # 2. 주도주 데이터 로딩
        leader_df = self.fetch_leader_stock_data(date)
        if leader_df.empty:
            print(f"[WARN] {date}에 대한 주도주 데이터가 없습니다.")
            # 주도주 데이터가 없어도 분석을 중단하지 않고, 해당 값은 0으로 처리되도록 함
            analysis_df = momentum_df
            analysis_df['leader_count'] = 0
            analysis_df['leader_momentum'] = 0.0
        else:
            print(f"[INFO] {date}의 주도주 데이터 {len(leader_df)}건 로딩 및 계산 완료.")
            # 3. 데이터 병합
            analysis_df = pd.merge(momentum_df, leader_df, on=['target_id', 'target_type'], how='left')
            analysis_df[['leader_count', 'leader_momentum']] = analysis_df[['leader_count', 'leader_momentum']].fillna(0)

        # 4. 종합 추세 점수 계산
        analysis_df = self.calculate_trend_score(analysis_df)

        # 5. 투자 의견 생성
        final_df = self.generate_opinions(analysis_df)
        
        # 6. 결과 저장
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