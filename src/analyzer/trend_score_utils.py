# trend_score_utils.py
# 모멘텀/투자의견 산식 공통 모듈 (실전/백테스트 완전 일치 목적)

import numpy as np

# 1. trend_score 계산 (가장 단순: 지표×가중치 합산)
def calc_trend_score(row, weights):
    score = 0.0
    for k, w in weights.items():
        score += float(row.get(k, 0.0)) * float(w)
    return score

# 2. 0~100 정규화 (min/max 입력, 값이 같으면 0)
def normalize_score(score, min_val, max_val):
    if max_val == min_val:
        return 0.0
    return (score - min_val) / (max_val - min_val) * 100

# 3. opinion 변환 (임계값 기준)
def score_to_opinion(score):
    if score >= 80:
        return 'STRONG_BUY'
    elif score >= 60:
        return 'BUY'
    elif score >= 40:
        return 'HOLD'
    else:
        return 'SELL' 