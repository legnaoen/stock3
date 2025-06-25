"""
scripts/optimize_momentum_weights.py

[주요 기능]
- 다양한 가중치 조합(랜덤 Dirichlet 방식)으로 모멘텀 전략 백테스트/최적화 실행
- 실험 결과를 optimized_momentum_weights.csv에 저장

[중요사항/주의점]
- 가중치 조합은 최대 200개까지만 랜덤 생성(속도/메모리 최적화)
- 고정 factor(min_weight) 조건, 합 1(tolerance) 조건 robust하게 적용
- 실전/실험 csv의 컬럼명 일치 여부에 주의(실전 적용 시 헤더 확인)
- 예외 발생 시 print/log로 진단 가능
"""
# ---
# [지표 ON/OFF 기능] 아래 factors_base는 항상 사용, factors_optional은 True/False로 ON/OFF 가능
# 예시: {'volume_momentum_3d': True, ...}로 조절
# 기본값: price_momentum_3d, price_momentum_5d, price_momentum_10d, rsi_value만 사용
# ---
print('[DEBUG] 스크립트 진입')
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
import pandas as pd
from backtest_momentum_strategy import run_backtest_with_weights
from datetime import datetime
from src.analyzer.momentum_analyzer import MomentumAnalyzer
from src.analyzer.investment_analyzer import InvestmentAnalyzer
import random
import json
import sqlite3

RESULTS_CSV = 'results/optimized_momentum_weights.csv'

# 항상 사용하는 고정 factor (항상 ON, UI에서 해제 불가)
factors_base = []  # 기본지표 없음
# ON/OFF 가능한 선택 factor (UI에서만 ON/OFF 가능)
factors_optional = {
    'price_momentum_1d': False,
    'price_momentum_3d': False,  # 원래대로 복구
    'price_momentum_5d': False,  # 원래대로 복구
    'price_momentum_10d': False,
    'rsi_value': False,
    'volume_momentum_1d': False,
    'volume_momentum_3d': False,
    'volume_momentum_5d': False,
    'leader_count': False,
    'leader_momentum': False,
}

def get_active_factors_and_all_factors():
    """
    ON/OFF 상태에 따라 활성화된 지표와 전체 지표 리스트를 반환
    """
    all_factors = list(factors_optional.keys())
    active_factors = [k for k, v in factors_optional.items() if v]
    return active_factors, all_factors

def generate_weight_combinations(factors, step=0.1, tolerance=0.01, fixed_factors=None, min_weight=0.01, max_combos=200):
    import numpy as np
    combos = []
    seen = set()
    n = len(factors)
    max_trials = 10000
    trials = 0
    while len(combos) < max_combos and trials < max_trials:
        trials += 1
        # 1. 랜덤 분포 생성 (합이 1)
        weights = np.random.dirichlet(np.ones(n), 1)[0]
        # 2. 고정 factor는 min_weight 이상이어야 함
        if fixed_factors:
            if any(w < min_weight for k, w in zip(factors, weights) if k in fixed_factors):
                continue
        # 3. tolerance 조건
        if abs(sum(weights) - 1) > tolerance:
            continue
        # 4. 중복 방지
        key = tuple(np.round(weights, 4))
        if key in seen:
            continue
        seen.add(key)
        combos.append(dict(zip(factors, weights)))
    return combos

if __name__ == "__main__":
    # [지표 ON/OFF/방향 연동] selected_factors.json이 있으면 direction 정보까지 반영
    direction = None
    tmp_path = os.path.join(os.path.dirname(__file__), '../selected_factors.json')
    print(f'[DEBUG] 임시파일 경로: {tmp_path}')
    if os.path.exists(tmp_path):
        try:
            with open(tmp_path, 'r', encoding='utf-8') as f:
                selected = json.load(f)
            print(f'[DEBUG] 임시파일 내용: {selected}')
            # selected가 {지표명: 1/-1/0} 형태면 direction으로 사용
            if isinstance(selected, dict):
                direction = selected
                for k in factors_optional.keys():
                    factors_optional[k] = (selected.get(k, 0) != 0)
            else:
                # 구버전 호환: 리스트면 ON만 True
                for k in factors_optional.keys():
                    factors_optional[k] = (k in selected)
                direction = {k: 1 if k in selected else 0 for k in factors_optional.keys()}
            os.remove(tmp_path)
            print('[DEBUG] 임시파일 삭제 완료')
        except Exception as e:
            print(f'[ERROR] 임시파일 처리 중 예외: {e}')
    # 1. 가중치 조합 생성 (ON/OFF+방향 반영, 최대 200개)
    active_factors, all_factors = get_active_factors_and_all_factors()
    # direction==0인 지표는 조합에서 제외
    if direction:
        active_factors = [k for k in active_factors if direction.get(k, 1) != 0]
    combos = generate_weight_combinations(active_factors, step=0.05, tolerance=0.05, fixed_factors=[], min_weight=0.01, max_combos=200)
    print(f"[INFO] 사용 지표(ON): {active_factors}", flush=True)
    print(f"[INFO] 전체 지표: {all_factors}", flush=True)
    print(f"[INFO] 총 {len(combos)}개 가중치 조합 생성", flush=True)

    # 2. 분석기 인스턴스 준비
    analyzer = MomentumAnalyzer()
    invest_analyzer = InvestmentAnalyzer()
    today = datetime.now().strftime('%Y-%m-%d')
    target_type = 'THEME'

    periods = [1, 3, 5, 10, 20]
    results = []
    for i, weights in enumerate(combos):
        # OFF/0인 지표는 0으로 세팅하여 모든 지표 컬럼을 포함
        full_weights = {k: (weights[k] if k in weights else 0.0) for k in all_factors}
        # direction 정보도 함께 저장
        dir_cols = {f"{k}_dir": (direction.get(k, 0) if direction else 1) for k in all_factors}
        print(f"\n[LOOP] {i+1}/{len(combos)}: {full_weights}")
        analyzer.analyze(target_type=target_type, save=True)
        invest_analyzer.analyze(date=today)
        res = run_backtest_with_weights(full_weights, periods=periods, direction=direction)
        # STRONG_BUY/BUY count 및 날짜 집계
        with sqlite3.connect('db/theme_industry.db') as conn:
            cur = conn.cursor()
            strong_buy_count = cur.execute(
                "SELECT COUNT(*) FROM investment_opinion WHERE date=? AND target_type=? AND opinion_type='STRONG_BUY'",
                (today, target_type)
            ).fetchone()[0]
            buy_count = cur.execute(
                "SELECT COUNT(*) FROM investment_opinion WHERE date=? AND target_type=? AND opinion_type='BUY'",
                (today, target_type)
            ).fetchone()[0]
        result_row = {**full_weights, **dir_cols}
        for n in periods:
            result_row[f'BUY_hit_rate_{n}d'] = res.get(f'BUY_hit_rate_{n}d', None)
            result_row[f'BUY_avg_return_{n}d'] = res.get(f'BUY_avg_return_{n}d', None)
        # 추가: 날짜, STRONG_BUY/BUY count
        result_row['date'] = today
        result_row['strong_buy_count'] = strong_buy_count
        result_row['buy_count'] = buy_count
        results.append(result_row)
        print(f"[RESULT] BUY 적중률/수익률: " + ', '.join([f"{n}d: {result_row[f'BUY_hit_rate_{n}d']}, {result_row[f'BUY_avg_return_{n}d']}" for n in periods]))

    df = pd.DataFrame(results)
    df = df.sort_values(by='BUY_hit_rate_5d', ascending=False)
    df.to_csv(RESULTS_CSV, index=False)
    print(f"\n[최고 성과 상위 5개] (5일 BUY 적중률 기준)")
    print(df.head(5))
    print(f"\n[전체 결과 CSV 저장 완료] {RESULTS_CSV}") 