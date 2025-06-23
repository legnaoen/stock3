# ---
# [지표 ON/OFF 기능] 아래 factors_base는 항상 사용, factors_optional은 True/False로 ON/OFF 가능
# 예시: {'volume_momentum_3d': True, ...}로 조절
# 기본값: price_momentum_3d, price_momentum_5d, price_momentum_10d, rsi_value만 사용
# ---
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
import pandas as pd
from backtest_momentum_strategy import run_backtest_with_weights
from datetime import datetime
from src.analyzer.momentum_analyzer import MomentumAnalyzer
from src.analyzer.investment_analyzer import InvestmentAnalyzer
import random

RESULTS_CSV = 'results/optimized_momentum_weights.csv'

# 항상 사용하는 고정 factor (항상 ON, UI에서 해제 불가)
factors_base = [
    'price_momentum_1d',
    'price_momentum_3d',
    'price_momentum_5d',
    'price_momentum_10d',
    'rsi_value'
]
# ON/OFF 가능한 선택 factor (UI에서만 ON/OFF 가능)
factors_optional = {
    'volume_momentum_1d': False,
    'volume_momentum_3d': False,
    'volume_momentum_5d': False,
    'leader_count': False,
    'leader_momentum': False,
}

MAX_COMBOS = 200

def get_active_factors_and_all_factors():
    """
    ON/OFF 상태에 따라 활성화된 지표와 전체 지표 리스트를 반환
    """
    all_factors = list(factors_base) + list(factors_optional.keys())
    active_factors = list(factors_base)
    for k, v in factors_optional.items():
        if v:
            active_factors.append(k)
    return active_factors, all_factors

def generate_weight_combinations(factors, step=0.1, tolerance=0.01, fixed_factors=None, min_weight=0.01):
    """
    factors: ['price_momentum_1d', ...]
    step: 0.1 → 0, 0.1, 0.2, ..., 1.0
    tolerance: 합이 1에서 이만큼 벗어나도 허용
    fixed_factors: 고정지표 리스트(여기에 포함된 지표는 최소 min_weight 이상)
    min_weight: 고정지표 최소 가중치
    """
    import itertools
    import numpy as np
    n = len(factors)
    grid = np.arange(0, 1+step, step)
    combos = []
    for weights in itertools.product(grid, repeat=n):
        if abs(sum(weights) - 1) <= tolerance:
            if fixed_factors:
                # 고정지표는 최소 min_weight 이상이어야 함
                if any(w < min_weight for k, w in zip(factors, weights) if k in fixed_factors):
                    continue
            combos.append(dict(zip(factors, weights)))
    return combos

if __name__ == "__main__":
    # 1. 가중치 조합 생성 (ON/OFF 반영)
    active_factors, all_factors = get_active_factors_and_all_factors()
    combos = generate_weight_combinations(active_factors, step=0.05, tolerance=0.05, fixed_factors=factors_base, min_weight=0.01)
    if len(combos) > MAX_COMBOS:
        combos = random.sample(combos, MAX_COMBOS)
    print(f"[INFO] 사용 지표(ON): {active_factors}")
    print(f"[INFO] 전체 지표: {all_factors}")
    print(f"[INFO] 총 {len(combos)}개 가중치 조합 생성")

    # 2. 분석기 인스턴스 준비
    analyzer = MomentumAnalyzer()
    invest_analyzer = InvestmentAnalyzer()
    today = datetime.now().strftime('%Y-%m-%d')
    target_type = 'THEME'

    periods = [1, 3, 5, 10, 20]
    results = []
    for i, weights in enumerate(combos):
        # OFF된 지표는 0으로 세팅하여 모든 지표 컬럼을 포함
        full_weights = {k: (weights[k] if k in weights else 0.0) for k in all_factors}
        print(f"\n[LOOP] {i+1}/{len(combos)}: {full_weights}")
        analyzer.analyze(target_type=target_type, save=True)
        invest_analyzer.analyze(date=today)
        res = run_backtest_with_weights(full_weights, periods=periods)
        result_row = {**full_weights}
        for n in periods:
            result_row[f'BUY_hit_rate_{n}d'] = res.get(f'BUY_hit_rate_{n}d', None)
            result_row[f'BUY_avg_return_{n}d'] = res.get(f'BUY_avg_return_{n}d', None)
        results.append(result_row)
        print(f"[RESULT] BUY 적중률/수익률: " + ', '.join([f"{n}d: {result_row[f'BUY_hit_rate_{n}d']}, {result_row[f'BUY_avg_return_{n}d']}" for n in periods]))

    df = pd.DataFrame(results)
    df = df.sort_values(by='BUY_hit_rate_5d', ascending=False)
    df.to_csv(RESULTS_CSV, index=False)
    print(f"\n[최고 성과 상위 5개] (5일 BUY 적중률 기준)")
    print(df.head(5))
    print(f"\n[전체 결과 CSV 저장 완료] {RESULTS_CSV}") 