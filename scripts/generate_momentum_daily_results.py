import os
import sys
import pandas as pd
import sqlite3
from datetime import datetime
import numpy as np
sys.path.append(os.path.join(os.path.dirname(__file__)))
from backtest_momentum_strategy import run_backtest_with_weights
from src.analyzer.trend_score_utils import calc_trend_score, normalize_score, score_to_opinion

# 1. 최적화된 추천 가중치 1세트 불러오기 (상위 1개)
opt_csv = 'results/optimized_momentum_weights.csv'
opt_df = pd.read_csv(opt_csv)
# 가중치 컬럼만 추출
weight_cols = [c for c in opt_df.columns if '_dir' not in c and c not in ['date','strong_buy_count','buy_count'] and not c.startswith('BUY_')]
weights = {k: opt_df.iloc[0][k] for k in weight_cols if not pd.isnull(opt_df.iloc[0][k])}

# 2. DB에서 날짜 리스트 추출
db_path = 'db/theme_industry.db'
with sqlite3.connect(db_path) as conn:
    dates = pd.read_sql_query("SELECT DISTINCT date FROM momentum_analysis ORDER BY date DESC", conn)['date'].tolist()

results = []
periods = [5, 10, 20]
signal_types = ['STRONG_BUY', 'BUY', 'HOLD', 'SELL']

for date in dates:
    with sqlite3.connect(db_path) as conn:
        # 날짜별 snapshot 집계: 해당 날짜 데이터만 사용
        df = pd.read_sql_query(
            f"""
            SELECT io.opinion_type, ma.price_momentum_5d, ma.price_momentum_10d, ma.price_momentum_20d
            FROM investment_opinion io
            LEFT JOIN momentum_analysis ma
            ON io.target_id = ma.target_id AND io.target_type = ma.target_type AND io.date = ma.date
            WHERE io.date = ?
            """,
            conn, params=[date])
        row = {'date': date}
        for op in signal_types:
            mask = df['opinion_type'] == op
            cnt = mask.sum()
            for n in periods:
                col = f'price_momentum_{n}d'
                rets = df.loc[mask, col]
                avg_ret = rets.mean() if cnt else '-'
                if op in ['STRONG_BUY','BUY']:
                    hit = (rets > 0).sum()
                elif op == 'SELL':
                    hit = (rets < 0).sum()
                else:
                    hit = (rets > 0).sum()
                hit_rate = hit / cnt * 100 if cnt > 0 else '-'
                row[f'{op}_count_{n}d'] = cnt
                row[f'{op}_hit_rate_{n}d'] = hit_rate
                row[f'{op}_avg_return_{n}d'] = avg_ret
        # 지수 모멘텀(3/5/10일) 추출
        df_idx = pd.read_sql_query("SELECT momentum_3d, momentum_5d, momentum_10d FROM market_index_daily WHERE date = ? AND index_name = 'KOSPI'", conn, params=[date])
        if not df_idx.empty:
            row['idx_momentum_3d'] = df_idx.iloc[0]['momentum_3d']
            row['idx_momentum_5d'] = df_idx.iloc[0]['momentum_5d']
            row['idx_momentum_10d'] = df_idx.iloc[0]['momentum_10d']
        else:
            row['idx_momentum_3d'] = row['idx_momentum_5d'] = row['idx_momentum_10d'] = None
        results.append(row)
    print(f"[진행] {date} 완료: {row}")

# 3. 결과 저장
out_csv = 'results/momentum_daily_results.csv'
pd.DataFrame(results).to_csv(out_csv, index=False)
print(f"[CSV 저장 완료] {out_csv}")

# --- 재발 방지: 임시 테이블/누적 SELECT 사용 금지, 날짜별 snapshot 집계만 허용 ---

def run_daily_signal_stats(weights, db_path, date, periods=[5,10,20], direction=None, table_name='momentum_analysis'):
    """
    해당 날짜(date)에 대해 investment_opinion + momentum_analysis 조인 후 opinion_type별 count/수익률/적중률을 집계
    반환: { 'STRONG_BUY_count_5d': x, 'STRONG_BUY_avg_return_5d': y, ... }
    """
    import pandas as pd
    import numpy as np
    import sqlite3
    signal_types = ['STRONG_BUY', 'BUY', 'HOLD', 'SELL']
    result = {}
    with sqlite3.connect(db_path) as conn:
        # 투자 의견 + 실제 수익률 조인
        df = pd.read_sql_query(
            f"""
            SELECT io.opinion_type, ma.price_momentum_5d, ma.price_momentum_10d, ma.price_momentum_20d
            FROM investment_opinion io
            LEFT JOIN momentum_analysis ma
            ON io.target_id = ma.target_id AND io.target_type = ma.target_type AND io.date = ma.date
            WHERE io.date = ?
            """,
            conn, params=[date])
        if df.empty:
            return {}
        for op in signal_types:
            mask = df['opinion_type'] == op
            cnt = mask.sum()
            for n in periods:
                col = f'price_momentum_{n}d'
                rets = df.loc[mask, col]
                avg_ret = rets.mean() if cnt else '-'
                if op in ['STRONG_BUY','BUY']:
                    hit = (rets > 0).sum()
                elif op == 'SELL':
                    hit = (rets < 0).sum()
                else:
                    hit = (rets > 0).sum()
                hit_rate = hit / cnt * 100 if cnt > 0 else '-'
                result[f'{op}_count_{n}d'] = cnt
                result[f'{op}_hit_rate_{n}d'] = hit_rate
                result[f'{op}_avg_return_{n}d'] = avg_ret
    return result

# --- 1단계: 최근 2개 날짜만 테스트 ---
with sqlite3.connect(db_path) as conn:
    dates = pd.read_sql_query("SELECT DISTINCT date FROM momentum_analysis ORDER BY date DESC", conn)['date'].tolist()

print("[1단계: 날짜별 신호별 집계 샘플]")
for date in dates[:2]:
    # 임시 테이블 생성
    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE IF EXISTS temp_momentum_analysis")
        conn.execute("CREATE TABLE temp_momentum_analysis AS SELECT * FROM momentum_analysis WHERE date <= ?", [date])
    res = run_daily_signal_stats(weights, db_path, date, periods=[5,10,20], direction=None, table_name='temp_momentum_analysis')
    print(f"날짜: {date}")
    print(res)

# --- 진단: 날짜별 신호별 count 직접 출력 ---
if __name__ == "__main__":
    import sqlite3
    print("[진단] investment_opinion 테이블 날짜별 신호별 count")
    db_path = 'db/theme_industry.db'
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT date, opinion_type, COUNT(*) 
            FROM investment_opinion 
            WHERE date BETWEEN '2025-05-27' AND '2025-06-17'
            GROUP BY date, opinion_type
            ORDER BY date DESC, opinion_type;
        """)
        rows = cur.fetchall()
        for r in rows:
            print(r)

# --- 진단: 6월 17일/16일 score 분포 비교 ---
def print_score_distribution():
    import sqlite3
    import pandas as pd
    db_path = 'db/theme_industry.db'
    with sqlite3.connect(db_path) as conn:
        for d in ['2025-06-17', '2025-06-16']:
            df = pd.read_sql_query("SELECT score FROM momentum_analysis WHERE date = ?", conn, params=[d])
            print(f"\n[score 분포] {d} (count={len(df)})")
            if len(df) == 0:
                print("  데이터 없음")
                continue
            arr = df['score'].to_numpy()
            print("  상위 10개:", arr[np.argsort(-arr)[:10]].tolist())
            print("  하위 10개:", arr[np.argsort(arr)[:10]].tolist())
            print("  평균:", df['score'].mean(), ", 표준편차:", df['score'].std(), ", 최소:", df['score'].min(), ", 최대:", df['score'].max())

if __name__ == "__main__":
    print_score_distribution() 