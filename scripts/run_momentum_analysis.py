# 전체 모멘텀 분석 자동화 파이프라인 실행 스크립트
# - 목적: 지수 수집 → 업종/테마 모멘텀 집계 → 투자 의견 생성 → 백테스트/분석까지 전체 자동 실행
# - 사용법: python scripts/run_momentum_analysis.py
# - scripts/ 폴더 내 개별 스크립트를 순차 실행하여 전체 파이프라인을 한 번에 돌림
import subprocess

steps = [
    ("지수 데이터 수집/모멘텀 계산", "python scripts/collect_market_index.py"),
    ("업종/테마 모멘텀 데이터 집계/보충", "python scripts/backfill_daily_performance.py"),
    ("투자 의견 자동 생성/보충", "python scripts/backfill_investment_opinion.py"),
    ("모멘텀/적중률/상관관계 분석", "python scripts/backtest_momentum_strategy.py"),
]

def run_step(desc, cmd):
    print(f"\n[실행] {desc} ...")
    result = subprocess.run(cmd, shell=True)
    if result.returncode == 0:
        print(f"[완료] {desc}")
    else:
        print(f"[오류] {desc} (코드: {result.returncode})")
    return result.returncode

if __name__ == "__main__":
    for desc, cmd in steps:
        run_step(desc, cmd)
    print("\n[전체 모멘텀 분석 파이프라인 완료]") 