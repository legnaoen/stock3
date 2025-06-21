import sqlite3
import pandas as pd
import os
import numpy as np
from datetime import datetime

class MomentumAnalyzer:
    """
    테마/업종의 일별 데이터를 기반으로 모멘텀을 분석하고 모든 기초 지표를 생성하는 클래스.
    
    [역할과 책임 (Role & Responsibilities)]
    - 이 분석기는 1차적인 기초 데이터를 계산하는 역할만 수행합니다.
    - 가격/거래대금 모멘텀, RSI, 주도주 모멘텀 등 모든 객관적인 수치들을 계산하여 `momentum_analysis` 테이블에 저장합니다.
    - 최종 투자 의견을 생성하거나 복합적인 판단을 내리지 않습니다.
    - 이 분석기의 결과물은 `InvestmentAnalyzer`의 유일한 입력 데이터 소스로 사용됩니다.
    """
    # --- 설정(Configuration) ---
    PRICE_MOMENTUM_PERIODS = [3, 5, 10]
    VOLUME_MOMENTUM_PERIODS = [3, 5]
    FETCH_DAYS_BUFFER = 30

    def __init__(self, theme_db_path='db/theme_industry.db', master_db_path='db/stock_master.db'):
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.theme_db_path = os.path.join(project_root, theme_db_path)
        self.master_db_path = os.path.join(project_root, master_db_path)
        
        if not os.path.exists(self.theme_db_path):
            raise FileNotFoundError(f"테마/업종 DB 파일을 찾을 수 없습니다: {self.theme_db_path}")
        if not os.path.exists(self.master_db_path):
            raise FileNotFoundError(f"마스터 DB 파일을 찾을 수 없습니다: {self.master_db_path}")

    def _get_theme_db_connection(self):
        return sqlite3.connect(self.theme_db_path)
    
    def _get_master_db_connection(self):
        return sqlite3.connect(self.master_db_path)

    def fetch_performance_data(self, target_type='THEME', days=60):
        """
        지정된 기간 동안의 테마 또는 업종의 일별 데이터를 불러옵니다.
        이름 정보를 포함하기 위해 마스터 DB를 ATTACH하여 사용합니다.

        :param target_type: 'THEME' 또는 'INDUSTRY'
        :param days: 불러올 데이터의 최근 일수
        :return: Pandas DataFrame
        """
        if target_type.upper() not in ['THEME', 'INDUSTRY']:
            raise ValueError("target_type은 'THEME' 또는 'INDUSTRY'여야 합니다.")

        table_name = f"{target_type.lower()}_daily_performance"
        id_column = f"{target_type.lower()}_id"
        master_table_name = f"{target_type.lower()}_master"
        name_column = f"{target_type.lower()}_name"
        
        query = f"""
        SELECT p.*, m.{name_column}
        FROM {table_name} p
        JOIN master.{master_table_name} m ON p.{id_column} = m.{id_column}
        WHERE p.date IN (
            SELECT DISTINCT date
            FROM {table_name}
            ORDER BY date DESC
            LIMIT ?
        )
        ORDER BY p.{id_column}, p.date;
        """

        try:
            with self._get_theme_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("ATTACH DATABASE ? AS master", (self.master_db_path,))
                df = pd.read_sql_query(query, conn, params=(days,))
                cursor.execute("DETACH DATABASE master")

            if df.empty:
                print(f"경고: {table_name} 테이블에서 데이터를 찾을 수 없습니다.")
                return df

            df.rename(columns={id_column: 'target_id', name_column: 'target_name'}, inplace=True)
            df['date'] = pd.to_datetime(df['date'])
            return df
            
        except pd.io.sql.DatabaseError as e:
            if f"no such table: master.{master_table_name}" in str(e):
                print(f"오류: 마스터 DB({self.master_db_path})에 '{master_table_name}' 테이블이 없습니다.")
            else:
                print(f"데이터베이스 오류 발생: {e}")
            return pd.DataFrame()
        except Exception as e:
            print(f"데이터 조회 중 오류 발생: {e}")
            return pd.DataFrame()

    def calculate_leader_momentum(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        주어진 데이터프레임의 'leader_stock_codes'를 기반으로 주도주 모멘텀을 계산합니다.
        """
        if df.empty or 'leader_stock_codes' not in df.columns:
            df['leader_count'] = 0
            df['leader_momentum'] = 0.0
            return df

        # 날짜별로 주도주 코드를 집계하여 DB 조회를 최소화
        all_leader_codes_by_date = {}
        for _, row in df.iterrows():
            date_str = row['date'].strftime('%Y-%m-%d')
            if pd.notna(row['leader_stock_codes']):
                if date_str not in all_leader_codes_by_date:
                    all_leader_codes_by_date[date_str] = set()
                all_leader_codes_by_date[date_str].update(row['leader_stock_codes'].split(','))

        # 날짜별 주도주 등락률을 저장할 딕셔너리
        stock_perf_by_date = {}
        with self._get_master_db_connection() as master_conn:
            for date_str, codes in all_leader_codes_by_date.items():
                if not codes: continue
                placeholders = ','.join(['?'] * len(codes))
                stock_query = f"SELECT stock_code, price_change_ratio FROM DailyStocks WHERE date = ? AND stock_code IN ({placeholders})"
                params = [date_str] + list(codes)
                stock_perf_df = pd.read_sql_query(stock_query, master_conn, params=params)
                stock_perf_by_date[date_str] = stock_perf_df.set_index('stock_code')['price_change_ratio'].to_dict()

        def get_leader_metrics(row):
            date_str = row['date'].strftime('%Y-%m-%d')
            codes_str = row['leader_stock_codes']
            
            if pd.isna(codes_str) or not codes_str or date_str not in stock_perf_by_date:
                return 0, 0.0

            codes = codes_str.split(',')
            perf_map = stock_perf_by_date[date_str]
            
            valid_perfs = [perf_map.get(c) for c in codes if c in perf_map and pd.notna(perf_map.get(c))]
            
            count = len(valid_perfs)
            momentum = sum(valid_perfs) / count if count > 0 else 0.0
            return count, round(momentum, 2)

        df[['leader_count', 'leader_momentum']] = df.apply(get_leader_metrics, axis=1, result_type='expand')
        return df

    def calculate_momentum_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        주어진 데이터프레임에 모든 모멘텀 지표들을 계산하여 추가합니다.
        """
        if df.empty:
            return df
        
        df = df.sort_values(by=['target_id', 'date'])

        # --- 가격 모멘텀 계산 ---
        df['price_momentum_1d'] = df['price_change_ratio']
        df['daily_return_factor'] = 1 + df['price_change_ratio'] / 100
        grouped = df.groupby('target_id')['daily_return_factor']
        for n in self.PRICE_MOMENTUM_PERIODS:
            df[f'price_momentum_{n}d'] = grouped.rolling(window=n, min_periods=n).apply(np.prod, raw=True).reset_index(level=0, drop=True)
            df[f'price_momentum_{n}d'] = (df[f'price_momentum_{n}d'] - 1) * 100
        
        # --- 거래대금 모멘텀 계산 ---
        grouped_trading_value = df.groupby('target_id')['trading_value']
        df['volume_momentum_1d'] = grouped_trading_value.pct_change(1) * 100
        for n in self.VOLUME_MOMENTUM_PERIODS:
            ma = grouped_trading_value.rolling(window=n, min_periods=n).mean()
            df[f'volume_momentum_{n}d'] = ma.groupby('target_id').pct_change(1).reset_index(level=0, drop=True) * 100

        # --- RSI 계산 ---
        rsi_period = 14
        price_change = df.groupby('target_id')['price_change_ratio'].diff(1).fillna(0)
        gain = price_change.where(price_change > 0, 0)
        loss = -price_change.where(price_change < 0, 0)
        avg_gain = gain.groupby(df['target_id']).rolling(window=rsi_period, min_periods=1).mean().reset_index(level=0, drop=True)
        avg_loss = loss.groupby(df['target_id']).rolling(window=rsi_period, min_periods=1).mean().reset_index(level=0, drop=True)
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        df['rsi_value'] = rsi.replace([np.inf, -np.inf], 100).fillna(50)

        # --- 주도주 모멘텀 계산 ---
        df = self.calculate_leader_momentum(df)

        df = df.drop(columns=['daily_return_factor'], errors='ignore')
        return df

    def save_analysis_results(self, df: pd.DataFrame, target_type: str):
        if df.empty:
            print("저장할 데이터가 없습니다.")
            return

        table_name = 'momentum_analysis'
        
        # 저장할 컬럼 목록을 명시적으로 정의
        columns_to_save = [
            'target_id', 'target_type', 'date',
            'price_momentum_1d', 'volume_momentum_1d', 'rsi_value',
            'leader_count', 'leader_momentum'
        ]
        for n in self.PRICE_MOMENTUM_PERIODS:
            columns_to_save.append(f'price_momentum_{n}d')
        for n in self.VOLUME_MOMENTUM_PERIODS:
            columns_to_save.append(f'volume_momentum_{n}d')
        
        # df에서 필요한 컬럼만 선택하고, 없는 경우 기본값으로 채움
        data_to_save = pd.DataFrame()
        for col in columns_to_save:
            if col in df.columns:
                data_to_save[col] = df[col]
        
        # target_type과 date 형식 변환
        data_to_save['target_type'] = target_type.upper()
        data_to_save['date'] = df['date'].dt.strftime('%Y-%m-%d')
        
        data_to_save = data_to_save.where(pd.notnull(data_to_save), None)

        with self._get_theme_db_connection() as conn:
            cursor = conn.cursor()
            dates_to_update = data_to_save['date'].unique().tolist()
            
            try:
                conn.execute("BEGIN TRANSACTION")
                delete_query = f"DELETE FROM {table_name} WHERE target_type = ? AND date IN ({','.join(['?']*len(dates_to_update))})"
                params = [target_type.upper()] + dates_to_update
                cursor.execute(delete_query, params)
                print(f"'{target_type}' 유형의 {len(dates_to_update)}개 날짜에 대한 기존 데이터를 삭제했습니다.")
                
                data_to_save.to_sql(table_name, conn, if_exists='append', index=False)
                
                conn.commit()
                print(f"{len(data_to_save)}개의 분석 결과가 '{table_name}' 테이블에 성공적으로 저장되었습니다.")

            except sqlite3.Error as e:
                print(f"데이터 저장 중 오류 발생: {e}")
                conn.rollback()

    def analyze(self, target_type='THEME', save=True):
        max_period = max(self.PRICE_MOMENTUM_PERIODS + [14]) # RSI 기간 포함
        required_days = max_period + self.FETCH_DAYS_BUFFER
        
        print(f"--- {target_type} 모멘텀 분석 및 저장 실행 ({required_days}일치 데이터) ---")
        
        performance_data = self.fetch_performance_data(target_type=target_type, days=required_days)
        if performance_data.empty:
            return pd.DataFrame()

        analysis_result = self.calculate_momentum_indicators(performance_data)

        if save and not analysis_result.empty:
            self.save_analysis_results(analysis_result, target_type)
        
        print("\n[분석 결과 확인] 최근 데이터 (메모리상):")
        print(analysis_result[['target_id', 'target_name', 'date', 'price_momentum_1d', 'price_momentum_3d', 'rsi_value', 'leader_count', 'leader_momentum']].dropna().tail())
        
        return analysis_result

def main():
    analyzer = MomentumAnalyzer()
    analyzer.analyze(target_type='THEME', save=True)
    print("\n" + "="*50 + "\n")
    analyzer.analyze(target_type='INDUSTRY', save=True)

if __name__ == "__main__":
    main() 