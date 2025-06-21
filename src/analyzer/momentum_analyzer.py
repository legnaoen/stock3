import sqlite3
import pandas as pd
import os
import numpy as np

class MomentumAnalyzer:
    """
    테마/업종의 일별 데이터를 기반으로 모멘텀을 분석하는 클래스.
    
    [역할과 책임 (Role & Responsibilities)]
    - 이 분석기는 1차적인 기초 데이터를 계산하는 역할만 수행합니다.
    - 가격/거래대금 모멘텀, RSI 등 객관적인 수치들을 계산하여 `momentum_analysis` 테이블에 저장합니다.
    - 최종 투자 의견을 생성하거나 복합적인 판단을 내리지 않습니다.
    - 이 분석기의 결과물은 `InvestmentAnalyzer`의 입력 데이터로 사용됩니다.
    """
    # --- 설정(Configuration) ---
    # 모멘텀 계산 기간 (단기 트레이딩)
    PRICE_MOMENTUM_PERIODS = [3, 5, 10]
    VOLUME_MOMENTUM_PERIODS = [3, 5]
    
    # 데이터 조회 시, 최대 모멘텀 기간에 여유분을 더한 기간만큼 조회
    FETCH_DAYS_BUFFER = 30

    def __init__(self, theme_db_path='db/theme_industry.db', master_db_path='db/stock_master.db'):
        """
        분석기 초기화. 데이터베이스 경로를 설정합니다.
        프로젝트 루트에서 실행하는 것을 기준으로 경로를 설정합니다.
        """
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.theme_db_path = os.path.join(project_root, theme_db_path)
        self.master_db_path = os.path.join(project_root, master_db_path)
        
        if not os.path.exists(self.theme_db_path):
            raise FileNotFoundError(f"테마/업종 DB 파일을 찾을 수 없습니다: {self.theme_db_path}")
        if not os.path.exists(self.master_db_path):
            raise FileNotFoundError(f"마스터 DB 파일을 찾을 수 없습니다: {self.master_db_path}")

    def _get_connection(self):
        """데이터베이스 연결을 반환합니다."""
        # 이제 테마/업종 DB를 기본으로 연결합니다.
        return sqlite3.connect(self.theme_db_path)

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
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # 마스터 DB를 ATTACH
                cursor.execute("ATTACH DATABASE ? AS master", (self.master_db_path,))
                
                df = pd.read_sql_query(query, conn, params=(days,))
                
                # 마스터 DB를 DETACH
                cursor.execute("DETACH DATABASE master")

            if df.empty:
                print(f"경고: {table_name} 테이블에서 데이터를 찾을 수 없습니다.")
                return df

            # 컬럼명을 'target_id', 'target_name'으로 통일하여 이후 분석을 용이하게 함
            df.rename(columns={id_column: 'target_id', name_column: 'target_name'}, inplace=True)
            
            # 'date' 컬럼을 datetime 객체로 변환
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

    def calculate_momentum_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        주어진 데이터프레임에 모멘텀 지표들을 계산하여 추가합니다.
        :param df: fetch_performance_data를 통해 얻은 원본 데이터프레임
        :return: 모멘텀 지표가 추가된 데이터프레임
        """
        if df.empty:
            return df

        # 계산을 위해 target_id와 date로 정렬
        df = df.sort_values(by=['target_id', 'date'])

        # --- 가격 모멘텀 계산 ---
        # 1일 수익률은 이미 price_change_ratio로 존재. 컬럼명만 통일.
        df['price_momentum_1d'] = df['price_change_ratio']
        
        # N일 누적 수익률 계산
        # (1 + 일일수익률/100)을 N일간 곱한 후, 다시 퍼센트로 변환
        df['daily_return_factor'] = 1 + df['price_change_ratio'] / 100
        
        grouped = df.groupby('target_id')['daily_return_factor']
        for n in self.PRICE_MOMENTUM_PERIODS: # 설정 값 사용
            # rolling().prod()를 사용하여 N일간의 누적 곱 계산
            df[f'price_momentum_{n}d'] = grouped.rolling(window=n, min_periods=n).apply(np.prod, raw=True).reset_index(level=0, drop=True)
            df[f'price_momentum_{n}d'] = (df[f'price_momentum_{n}d'] - 1) * 100
        
        # --- 거래대금 모멘텀 계산 ---
        grouped_trading_value = df.groupby('target_id')['trading_value']
        
        # 1일 거래대금 증감률
        df['volume_momentum_1d'] = grouped_trading_value.pct_change(1) * 100
        
        # N일 평균 거래대금 증감률
        for n in self.VOLUME_MOMENTUM_PERIODS: # 설정 값 사용
            # N일 이동평균을 구한 뒤, 그것의 1일 전 대비 증감률을 계산
            ma = grouped_trading_value.rolling(window=n, min_periods=n).mean()
            df[f'volume_momentum_{n}d'] = ma.groupby('target_id').pct_change(1).reset_index(level=0, drop=True) * 100

        # --- RSI 계산 ---
        rsi_period = 14
        # 'price_change_ratio'를 사용하여 일일 가격 변동률 계산
        price_change = df.groupby('target_id')['price_change_ratio'].diff(1)
        
        # 상승분과 하락분 계산
        gain = price_change.where(price_change > 0, 0)
        loss = -price_change.where(price_change < 0, 0)

        # 이동평균 계산 (Exponential Moving Average 사용이 일반적이나, 여기서는 Simple Moving Average로 구현)
        avg_gain = gain.groupby(df['target_id']).rolling(window=rsi_period, min_periods=rsi_period).mean().reset_index(level=0, drop=True)
        avg_loss = loss.groupby(df['target_id']).rolling(window=rsi_period, min_periods=rsi_period).mean().reset_index(level=0, drop=True)
        
        # RS 및 RSI 계산
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        # RSI 값이 무한대인 경우(loss가 0일 때) 100으로 처리
        df['rsi_value'] = rsi.replace([np.inf, -np.inf], 100)
        # RSI 값이 없는 경우(gain, loss 모두 0일 때) 50으로 처리할 수 있으나, 여기서는 NaN으로 둠

        df = df.drop(columns=['daily_return_factor'])
        return df

    def save_analysis_results(self, df: pd.DataFrame, target_type: str):
        """
        분석 결과를 momentum_analysis 테이블에 저장합니다.
        기존에 해당 날짜의 데이터가 있으면 삭제 후 새로 추가합니다.
        
        :param df: 분석 결과가 포함된 데이터프레임
        :param target_type: 'THEME' 또는 'INDUSTRY'
        """
        if df.empty:
            print("저장할 데이터가 없습니다.")
            return

        table_name = 'momentum_analysis'
        
        # 저장할 데이터만으로 새로운 DataFrame을 명시적으로 생성
        data_to_save = pd.DataFrame({
            'target_id': df['target_id'],
            'target_type': target_type.upper(),
            'date': df['date'].dt.strftime('%Y-%m-%d'),
            'price_momentum_1d': df.get('price_momentum_1d'),
            'volume_momentum_1d': df.get('volume_momentum_1d'),
            'rsi_value': df.get('rsi_value'),
        })

        # 설정된 기간에 따라 동적으로 모멘텀 컬럼 추가
        for n in self.PRICE_MOMENTUM_PERIODS:
            col_name = f'price_momentum_{n}d'
            data_to_save[col_name] = df.get(col_name)
        
        for n in self.VOLUME_MOMENTUM_PERIODS:
            col_name = f'volume_momentum_{n}d'
            data_to_save[col_name] = df.get(col_name)
        
        # NaN 값을 None(SQL의 NULL)으로 변환하여 DB 저장 시 오류 방지
        data_to_save = data_to_save.where(pd.notnull(data_to_save), None)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 분석 대상 날짜 목록 추출
            dates_to_update = data_to_save['date'].unique().tolist()
            
            try:
                conn.execute("BEGIN TRANSACTION")
                
                # 기존 데이터 삭제
                delete_query = f"""
                    DELETE FROM {table_name}
                    WHERE target_type = ? AND date IN ({','.join(['?']*len(dates_to_update))})
                """
                params = [target_type.upper()] + dates_to_update
                cursor.execute(delete_query, params)
                print(f"'{target_type}' 유형의 {len(dates_to_update)}개 날짜에 대한 기존 데이터를 삭제했습니다.")
                
                # 새 데이터 추가
                data_to_save.to_sql(table_name, conn, if_exists='append', index=False)
                
                conn.commit()
                print(f"{len(data_to_save)}개의 분석 결과가 '{table_name}' 테이블에 성공적으로 저장되었습니다.")

            except sqlite3.Error as e:
                print(f"데이터 저장 중 오류 발생: {e}")
                conn.rollback()

    def analyze(self, target_type='THEME', save=True):
        """
        데이터를 불러와 모멘텀 분석을 수행하고 결과를 저장합니다.
        
        :param target_type: 'THEME' 또는 'INDUSTRY'
        :param save: 결과를 DB에 저장할지 여부
        :return: 분석 결과가 포함된 데이터프레임
        """
        # 1. 데이터 불러오기
        # 분석에 필요한 최소 기간을 확보하기 위해 days 파라미터 조정 (최대 기간 + 버퍼)
        max_period = max(self.PRICE_MOMENTUM_PERIODS) if self.PRICE_MOMENTUM_PERIODS else 0
        required_days = max_period + self.FETCH_DAYS_BUFFER
        performance_data = self.fetch_performance_data(target_type=target_type, days=required_days)
        if performance_data.empty:
            return pd.DataFrame()

        # 2. 모멘텀 지표 계산
        analysis_result = self.calculate_momentum_indicators(performance_data)

        # 3. 결과 저장
        if save and not analysis_result.empty:
            self.save_analysis_results(analysis_result, target_type)

        return analysis_result

if __name__ == '__main__':
    # 클래스 사용 예시
    analyzer = MomentumAnalyzer()

    # --- 테마 모멘텀 분석 및 저장 실행 ---
    print("--- 테마 모멘텀 분석 및 저장 실행 ---")
    theme_analysis_result = analyzer.analyze(target_type='THEME', save=True)
    if not theme_analysis_result.empty:
        # analyze()가 반환한 결과에 이름이 포함되어 있는지 확인
        print("\n[분석 결과 확인] 최근 테마 분석 데이터 (메모리상):")
        print(theme_analysis_result[['target_id', 'target_name', 'date', 'price_momentum_1d', 'price_momentum_3d', 'rsi_value']].tail())


    print("\n" + "="*50 + "\n")

    # --- 업종 모멘텀 분석 및 저장 실행 ---
    print("--- 업종 모멘텀 분석 및 저장 실행 ---")
    industry_analysis_result = analyzer.analyze(target_type='INDUSTRY', save=True)
    if not industry_analysis_result.empty:
        # analyze()가 반환한 결과에 이름이 포함되어 있는지 확인
        print("\n[분석 결과 확인] 최근 업종 분석 데이터 (메모리상):")
        print(industry_analysis_result[['target_id', 'target_name', 'date', 'price_momentum_1d', 'price_momentum_3d', 'rsi_value']].tail()) 