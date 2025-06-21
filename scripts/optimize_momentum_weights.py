# ---
# [지표 ON/OFF 기능] 아래 factors_base는 항상 사용, factors_optional은 True/False로 ON/OFF 가능
# 예시: {'volume_momentum_3d': True, ...}로 조절
# 기본값: price_momentum_3d, price_momentum_5d, price_momentum_10d, rsi_value만 사용
# ---
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
import pandas as pd
from backtest_momentum_strategy import run_backtest_with_weights, generate_weight_combinations
from datetime import datetime
from src.analyzer.momentum_analyzer import MomentumAnalyzer
from src.analyzer.investment_analyzer import InvestmentAnalyzer

RESULTS_CSV = 'results/optimized_momentum_weights.csv'

# 항상 사용하는 기본 factor
factors_base = [
    'price_momentum_3d',
    'price_momentum_5d',
    'price_momentum_10d',
    'rsi_value'
]
# ON/OFF 가능한 확장 factor
factors_optional = {
    'volume_momentum_3d': False,
    'volume_momentum_5d': False,
    'trend_score': False,
    # 'leader_count': False,  # 필요시 추가
    # 'leader_momentum': False,  # 필요시 추가
}

def get_active_factors():
    factors = list(factors_base)
    for k, v in factors_optional.items():
        if v:
            factors.append(k)
    return factors

if __name__ == "__main__":
    # 1. 가중치 조합 생성 (ON/OFF 반영)
    factors = get_active_factors()
    combos = generate_weight_combinations(factors, step=0.2, tolerance=0.05)
    print(f"[INFO] 사용 지표: {factors}")
    print(f"[INFO] 총 {len(combos)}개 가중치 조합 생성")

    # 2. 분석기 인스턴스 준비
    analyzer = MomentumAnalyzer()
    invest_analyzer = InvestmentAnalyzer()
    today = datetime.now().strftime('%Y-%m-%d')
    target_type = 'THEME'

    results = []
    for i, weights in enumerate(combos):
        print(f"\n[LOOP] {i+1}/{len(combos)}: {weights}")
        analyzer.analyze(target_type=target_type, save=True)
        invest_analyzer.analyze(date=today)
        res = run_backtest_with_weights(weights)
        buy_hit_5d = res.get('BUY_hit_rate_5d', None)
        buy_ret_5d = res.get('BUY_avg_return_5d', None)
        result_row = {**weights, 'BUY_hit_rate_5d': buy_hit_5d, 'BUY_avg_return_5d': buy_ret_5d}
        results.append(result_row)
        print(f"[RESULT] 5일 BUY 적중률: {buy_hit_5d}, 5일 BUY 평균수익률: {buy_ret_5d}")

    df = pd.DataFrame(results)
    df = df.sort_values(by='BUY_hit_rate_5d', ascending=False)
    df.to_csv(RESULTS_CSV, index=False)
    print(f"\n[최고 성과 상위 5개] (5일 BUY 적중률 기준)")
    print(df.head(5))
    print(f"\n[전체 결과 CSV 저장 완료] {RESULTS_CSV}") 