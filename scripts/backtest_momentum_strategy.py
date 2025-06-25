"""
업종/테마 모멘텀 전략 백테스트/가중치 실험 스크립트
- 목적: 다양한 가중치 조합으로 업종/테마별 과거 전체 히스토리 신호/성과 자동 분석
- 사용법: python scripts/backtest_momentum_strategy.py
- 확장: 결과 csv 저장, 최적화 자동화, 신호/지표 추가 등
"""
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
import sqlite3
import pandas as pd
from src.analyzer.momentum_signal_generator import MomentumSignalGenerator
from collections import defaultdict
import numpy as np
from src.analyzer.trend_score_utils import calc_trend_score, normalize_score, score_to_opinion

def run_backtest_with_weights(weights, db_path='db/theme_industry.db', periods=[1,3,5,10], direction=None, table_name='momentum_analysis'):
    """
    주어진 가중치(weights)와 direction(지표별 방향)으로 신호 생성~백테스트~성과 집계를 한 번에 실행
    반환: 주요 성과 dict (예: {'STRONG_BUY_avg_return_5d': xx, ...})
    """
    import pandas as pd
    import numpy as np
    from src.analyzer.momentum_signal_generator import MomentumSignalGenerator
    import sqlite3

    signal_types = ['STRONG_BUY', 'BUY', 'HOLD', 'SELL']
    signal_stats = {op: {n: {'count':0, 'hit':0, 'sum_ret':0} for n in periods} for op in signal_types}
    all_results = []
    with sqlite3.connect(db_path) as conn:
        df_ids = pd.read_sql_query(f"SELECT DISTINCT target_id, target_type FROM {table_name}", conn)
        generator = MomentumSignalGenerator(weights)
        for _, row in df_ids.iterrows():
            target_id, target_type = row['target_id'], row['target_type']
            df = pd.read_sql_query(
                f"SELECT date, price_momentum_1d, price_momentum_3d, price_momentum_5d, price_momentum_10d, rsi_value FROM {table_name} WHERE target_id = ? AND target_type = ? ORDER BY date ASC",
                conn, params=[target_id, target_type])
            if len(df) < 30:
                continue
            # 1. raw score 계산
            df['score_raw'] = df.apply(lambda row: calc_trend_score(row, weights, direction=direction), axis=1)
            # 2. 0~100 정규화
            min_val = df['score_raw'].min()
            max_val = df['score_raw'].max()
            df['score'] = df['score_raw'].apply(lambda x: normalize_score(x, min_val, max_val))
            # 3. opinion 변환
            df['opinion'] = df['score'].apply(score_to_opinion)
            for n in periods:
                df[f'return_{n}d'] = df.get(f'price_momentum_{n}d', 0)
            for op in signal_types:
                mask = df['opinion'] == op
                cnt = mask.sum()
                if cnt == 0:
                    continue
                for n in periods:
                    rets = df.loc[mask, f'return_{n}d']
                    avg_ret = rets.mean()
                    if op in ['STRONG_BUY','BUY']:
                        hit = (rets > 0).sum()
                    elif op == 'SELL':
                        hit = (rets < 0).sum()
                    else:
                        hit = (rets > 0).sum()  # HOLD는 참고용
                    signal_stats[op][n]['count'] += cnt
                    signal_stats[op][n]['hit'] += hit
                    signal_stats[op][n]['sum_ret'] += avg_ret * cnt if not pd.isna(avg_ret) else 0
    # 주요 성과 요약 dict
    result = {}
    for op in signal_types:
        for n in periods:
            cnt = signal_stats[op][n]['count']
            avg_ret = signal_stats[op][n]['sum_ret'] / cnt if cnt else np.nan
            hit_rate = signal_stats[op][n]['hit'] / cnt * 100 if cnt else np.nan
            result[f'{op}_count_{n}d'] = cnt
            result[f'{op}_hit_rate_{n}d'] = hit_rate
            result[f'{op}_avg_return_{n}d'] = avg_ret
    result['all_results'] = all_results  # 상세 결과 필요시
    return result

if __name__ == "__main__":
    DB_PATH = 'db/theme_industry.db'

    # 실험할 가중치 조합 예시
    weight_sets = [
        {'price_momentum_3d': 0.2, 'price_momentum_5d': 0.4, 'price_momentum_10d': 0.3, 'rsi_value': 0.1},
        {'price_momentum_3d': 0.1, 'price_momentum_5d': 0.6, 'price_momentum_10d': 0.2, 'rsi_value': 0.1},
    ]

    RESULTS_DIR = 'results'
    os.makedirs(RESULTS_DIR, exist_ok=True)
    periods = [1, 3, 5, 10, 20]

    # 여러 기간 BUY 성과만 기록
    opt_results = []
    for weights in weight_sets:
        res = run_backtest_with_weights(weights, db_path=DB_PATH, periods=periods)
        row = {**weights}
        row.update(res)  # 모든 신호별 성과를 row에 추가
        opt_results.append(row)
    pd.DataFrame(opt_results).to_csv('results/optimized_momentum_weights.csv', index=False)
    print(f"\n[CSV 저장 완료] results/optimized_momentum_weights.csv")

    # 신호별/기간별 요약 표 생성 (불필요하므로 주석 처리)
    # rows = []
    # for op in ['BUY','SELL','HOLD']:
    #     row = {'신호': op, 'count': signal_stats[op][1]['count']}
    #     for n in periods:
    #         cnt = signal_stats[op][n]['count']
    #         avg_ret = signal_stats[op][n]['sum_ret'] / cnt if cnt else np.nan
    #         hit_rate = signal_stats[op][n]['hit'] / cnt * 100 if cnt else np.nan
    #         row[f'{n}d_평균수익'] = round(avg_ret,2) if not np.isnan(avg_ret) else '-'
    #         row[f'{n}d_적중률'] = f"{hit_rate:.2f}%" if not np.isnan(hit_rate) else '-'
    #     rows.append(row)

    # summary_df = pd.DataFrame(rows)
    # print("\n[신호별 기간별 평균 수익률/적중률 요약]")
    # print(summary_df.to_string(index=False))

    """
    실제 사용자에게 노출되는 investment_opinion 테이블의 opinion_type(STRONG_BUY, BUY, HOLD, SELL) 기준으로
    각 신호별 1,3,5,10,20일 수익률/적중률을 집계하는 스크립트
    """
    RESULTS_CSV = os.path.join(RESULTS_DIR, 'backtest_opinion_results.csv')
    os.makedirs(RESULTS_DIR, exist_ok=True)

    periods = [1, 3, 5, 10, 20]

    with sqlite3.connect(DB_PATH) as conn:
        # 투자 의견 데이터 로드
        df_op = pd.read_sql_query(
            "SELECT target_id, target_type, date, opinion_type FROM investment_opinion",
            conn
        )
        # 모멘텀(실제 수익률) 데이터 로드
        df_mom = pd.read_sql_query(
            "SELECT target_id, target_type, date, price_momentum_1d, price_momentum_3d, price_momentum_5d, price_momentum_10d FROM momentum_analysis",
            conn
        )
        # 20일 수익률 직접 계산
        df_mom = df_mom.sort_values(['target_id','target_type','date'])
        df_mom['price_momentum_20d'] = np.nan
        for (tid, ttype), group in df_mom.groupby(['target_id','target_type']):
            idx = group.index
            # 20일 뒤의 1d 모멘텀을 누적합으로 계산 (단순 누적합, 실제 가격 기반이 아니므로 참고용)
            # 실제 가격이 있다면 (close 등) (future_close - now_close)/now_close로 계산해야 함
            # 여기서는 1d 모멘텀을 단순 합산
            vals = group['price_momentum_1d'].to_numpy()
            # 20일 뒤까지 누적합
            for i in range(len(idx)-20):
                df_mom.loc[idx[i], 'price_momentum_20d'] = np.sum(vals[i:i+20])
        # 날짜별로 target_id, target_type, date 기준으로 조인
        df = pd.merge(df_op, df_mom, on=['target_id','target_type','date'], how='left')
        # 시장(코스피) 모멘텀(1/3/5/10/20d) 조인
        df_idx = pd.read_sql_query(
            "SELECT date, momentum_1d, momentum_3d, momentum_5d, momentum_10d, momentum_20d FROM market_index_daily WHERE index_name='KOSPI'",
            conn
        )
        df = pd.merge(df, df_idx, on='date', how='left')

        # 조인 후 데이터 분포/결측치 확인 로그 추가
        print(f"[DEBUG] 조인 후 전체 row 수: {len(df)}")
        print(f"[DEBUG] 조인 후 BUY 신호 row 수: {(df['opinion_type']=='BUY').sum()}")
        print(f"[DEBUG] price_momentum_1d NaN 비율: {df['price_momentum_1d'].isna().mean()*100:.2f}%")
        print(f"[DEBUG] momentum_1d NaN 비율: {df['momentum_1d'].isna().mean()*100:.2f}%")
        print(f"[DEBUG] 날짜 분포: {df['date'].min()} ~ {df['date'].max()}")
        print(f"[DEBUG] 샘플 데이터 (상위 5개):\n{df.head()}\n")

        # 20일 모멘텀 값이 없는 row에 대해 계산/보충
        df_mom = pd.read_sql_query(
            "SELECT id, target_id, target_type, date, price_momentum_1d FROM momentum_analysis ORDER BY target_id, target_type, date",
            conn
        )
        df_mom['price_momentum_20d'] = None
        for (tid, ttype), group in df_mom.groupby(['target_id','target_type']):
            idx = group.index
            vals = group['price_momentum_1d'].to_numpy()
            for i in range(len(idx)-20):
                df_mom.loc[idx[i], 'price_momentum_20d'] = float(np.sum(vals[i:i+20]))
        # DB에 업데이트
        with conn:
            for _, row in df_mom.iterrows():
                if row['price_momentum_20d'] is not None:
                    conn.execute(
                        "UPDATE momentum_analysis SET price_momentum_20d = ? WHERE id = ?",
                        (row['price_momentum_20d'], int(row['id']))
                    )

    signal_types = ['STRONG_BUY', 'BUY', 'HOLD', 'SELL']
    rows = []
    for op in signal_types:
        mask = df['opinion_type'] == op
        row = {'신호': op, 'count': mask.sum()}
        for n in periods:
            col = f'price_momentum_{n}d'
            rets = df.loc[mask, col]
            avg_ret = rets.mean()
            if op in ['STRONG_BUY','BUY']:
                hit = (rets > 0).sum()
            elif op == 'SELL':
                hit = (rets < 0).sum()
            else:
                hit = (rets > 0).sum()  # HOLD는 참고용
            hit_rate = hit / mask.sum() * 100 if mask.sum() else np.nan
            row[f'{n}d_평균수익'] = round(avg_ret,2) if not np.isnan(avg_ret) else '-'
            row[f'{n}d_적중률'] = f"{hit_rate:.2f}%" if not np.isnan(hit_rate) else '-'
        rows.append(row)

    summary_df = pd.DataFrame(rows)
    print("\n[실제 투자 의견 기준 신호별 기간별 평균 수익률/적중률 요약]")
    print(summary_df.to_string(index=False))
    # CSV 저장
    summary_df.to_csv(RESULTS_CSV, index=False)
    print(f"\n[CSV 저장 완료] {RESULTS_CSV}")

    # 1/3/5/10/20일 기간별 매수 신호 적중률/상관계수 분석
    print("\n[매수 신호 수익률 적중률 & 시장 모멘텀 상관관계 분석표]")
    print(f"{'기간':<6}{'시장↑ 적중률':>12}{'시장↓ 적중률':>12}{'상관계수':>12}")
    mask_buy_or_strong = df['opinion_type'].isin(['BUY','STRONG_BUY'])
    buy_df = df[mask_buy_or_strong].copy()
    for d in periods:
        mom_col = f'price_momentum_{d}d'
        idx_col = f'momentum_{d}d'
        if mom_col not in buy_df.columns or idx_col not in buy_df.columns:
            continue
        sub = buy_df.dropna(subset=[mom_col, idx_col]).copy()
        if sub.empty:
            up_hit = down_hit = corr = float('nan')
        else:
            sub['market_up'] = sub[idx_col] > 0
            hit = (sub[mom_col] > 0)
            up_hit = hit[sub['market_up']].mean() * 100 if sub['market_up'].sum() else float('nan')
            down_hit = hit[~sub['market_up']].mean() * 100 if (~sub['market_up']).sum() else float('nan')
            corr = sub[mom_col].corr(sub[idx_col])
        rows.append({'period': d, 'up_hit': up_hit, 'down_hit': down_hit, 'corr': corr})

    # 최고값 찾기 및 표 출력 (방어 로직 추가, dict 키 체크)
    valid_rows = [r for r in rows if isinstance(r, dict) and 'up_hit' in r]
    if not valid_rows or all(pd.isna(r['up_hit']) for r in valid_rows):
        print("\n[매수 신호 수익률 적중률 & 시장 모멘텀 상관관계 분석표]")
        print("(해당 데이터가 없어 결과를 출력할 수 없습니다.)")
    else:
        up_max = max([r['up_hit'] for r in valid_rows if not pd.isna(r['up_hit'])], default=None)
        down_max = max([r['down_hit'] for r in valid_rows if not pd.isna(r['down_hit'])], default=None)
        corr_max = max([r['corr'] for r in valid_rows if not pd.isna(r['corr'])], default=None)

        print("\n[매수 신호 수익률 적중률 & 시장 모멘텀 상관관계 분석표]")
        print(f"{'기간':<6}{'시장↑ 적중률':>12}{'시장↓ 적중률':>12}{'상관계수':>12}")
        for r in valid_rows:
            up_star = '★' if r['up_hit'] == up_max else ''
            down_star = '★' if r['down_hit'] == down_max else ''
            corr_star = '★' if r['corr'] == corr_max else ''
            print(f"{str(r['period'])+'일':<6}{r['up_hit']:10.2f}%{up_star:>2}{r['down_hit']:10.2f}%{down_star:>2}{r['corr']:10.3f}{corr_star:>2}")

        # 시장 모멘텀이 양수일 때만 매수하는 전략의 전체 적중률
        all_up = pd.concat([
            buy_df.dropna(subset=[f'price_momentum_{d}d', f'momentum_{d}d'])[[f'price_momentum_{d}d', f'momentum_{d}d']].assign(period=d)
            for d in periods if f'price_momentum_{d}d' in buy_df.columns and f'momentum_{d}d' in buy_df.columns
        ], ignore_index=True)
        if not all_up.empty:
            # 가장 최근 d 기준으로 컬럼명 변경
            d_last = periods[-1]
            all_up = all_up.rename(columns={f'price_momentum_{d_last}d': 'ret', f'momentum_{d_last}d': 'idx_mom'})
            all_up = all_up[all_up['idx_mom'] > 0]
            if not all_up.empty:
                strat_hit = (all_up['ret'] > 0).mean() * 100
                print(f"\n[전략 참고] 시장 모멘텀이 양수일 때만 매수 시 전체 적중률: {strat_hit:.2f}%")
            else:
                print("\n[전략 참고] 시장 모멘텀이 양수일 때만 매수 시 전체 적중률: (데이터 없음)")
        else:
            print("\n[전략 참고] 시장 모멘텀이 양수일 때만 매수 시 전체 적중률: (데이터 없음)")

def generate_weight_combinations(factors, step=0.1, tolerance=0.01):
    """
    factors: ['price_momentum_3d', 'price_momentum_5d', ...]
    step: 0.1 → 0, 0.1, 0.2, ..., 1.0
    tolerance: 합이 1에서 이만큼 벗어나도 허용
    """
    import itertools
    import numpy as np
    n = len(factors)
    grid = np.arange(0, 1+step, step)
    combos = []
    for weights in itertools.product(grid, repeat=n):
        if abs(sum(weights) - 1) <= tolerance:
            combos.append(dict(zip(factors, weights)))
    return combos

if __name__ == "__main__":
    # 기존 파이프라인 실행 후, 가중치 조합 생성 테스트
    factors = ['price_momentum_3d', 'price_momentum_5d', 'price_momentum_10d', 'rsi_value']
    combos = generate_weight_combinations(factors, step=0.2, tolerance=0.05)
    print(f"[TEST] 생성된 가중치 조합 개수: {len(combos)}")
    for i, w in enumerate(combos[:5]):
        print(f"조합 {i+1}: {w}") 