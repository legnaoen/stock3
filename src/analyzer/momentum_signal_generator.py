# 업종/테마 모멘텀 신호(매수/매도/보유) 생성기
# - 목적: 다양한 가중치 조합으로 모멘텀 신호(종합점수, 투자 의견 등) 생성
# - 사용법: MomentumSignalGenerator 클래스 활용
"""
모멘텀 신호 생성 모듈 (업종/테마)
- 목적: 다양한 가중치 조합으로 모멘텀 신호(종합점수, 투자 의견 등) 생성
- 사용법 예시:
    generator = MomentumSignalGenerator(weights)
    score = generator.calc_score(momentum_row)
    opinion = generator.get_opinion(score)
- 확장: 신호/지표/가중치 추가, 머신러닝 기반 신호 생성 등
"""
import numpy as np
from src.analyzer.trend_score_utils import calc_trend_score, score_to_opinion

class MomentumSignalGenerator:
    def __init__(self, weights):
        """
        weights: dict, 예) {'price_momentum_3d': 0.2, 'price_momentum_5d': 0.4, ...}
        """
        self.weights = weights

    def calc_score(self, row):
        """
        row: dict 또는 pandas.Series (모멘텀/지표 값)
        return: float (가중합 종합점수)
        """
        return calc_trend_score(row, self.weights)

    def get_opinion(self, score, buy_th=None, sell_th=None):
        """
        score: float
        return: str (매수/보유/매도)
        """
        return score_to_opinion(score) 