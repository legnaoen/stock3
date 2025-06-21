# 종목별 재무제표(성장성/수익성/안정성/시장가치) 자동 평가 및 투자 의견/리포트 생성 모듈
# - 목적: 재무제표 기반 종목 평가, 투자 의견/리포트 자동 생성 및 DB 저장
# - 사용법: FinancialStatementAnalyzer 클래스 활용
import sqlite3
from typing import Dict, List, Tuple, Optional
import json
from datetime import datetime, date
import numpy as np

class FinancialStatementAnalyzer:
    """재무제표 분석기 클래스"""
    
    def __init__(self):
        """초기화"""
        self.db_path = 'db/stock_master.db'
        self._init_weights()
        self._init_thresholds()
        self._init_templates()
        
    def _init_weights(self):
        """가중치 초기화"""
        self.weights = {
            'areas': {
                'growth': 0.3,        # 성장성
                'profitability': 0.3, # 수익성
                'stability': 0.2,     # 안정성
                'market_value': 0.2   # 시장가치
            },
            'growth': {
                'revenue_growth': 0.4,
                'operating_profit_growth': 0.3,
                'net_profit_growth': 0.3
            },
            'profitability': {
                'operating_margin': 0.5,
                'net_margin': 0.5
            },
            'stability': {
                'debt_ratio': 0.4,
                'quick_ratio': 0.3,
                'reserve_ratio': 0.3
            },
            'market_value': {
                'per': 0.5,
                'pbr': 0.3,
                'dividend_yield': 0.1,
                'dividend_payout': 0.1
            }
        }
        
    def _init_thresholds(self):
        """평가 기준값 초기화 (매우 나쁨 등급 추가, 배당성향 개선)"""
        self.thresholds = {
            # 성장성 지표 (높을수록 좋음, 5단계 세분화)
            'revenue_growth': {
                '매우_좋음': 20.0, '좋음': 15.0, '보통': 8.0, '나쁨': 4.0, '매우_나쁨': 0.0
            },
            'operating_profit_growth': {
                '매우_좋음': 25.0, '좋음': 15.0, '보통': 8.0, '나쁨': 4.0, '매우_나쁨': 0.0
            },
            'net_profit_growth': {
                '매우_좋음': 25.0, '좋음': 15.0, '보통': 8.0, '나쁨': 4.0, '매우_나쁨': 0.0
            },
            
            # 수익성 지표 (높을수록 좋음)
            'operating_margin': {
                '매우_좋음': 15.0, '좋음': 10.0, '보통': 5.0, '나쁨': 2.0, '매우_나쁨': 0.0
            },
            'net_margin': {
                '매우_좋음': 10.0, '좋음': 7.0, '보통': 4.0, '나쁨': 1.0, '매우_나쁨': 0.0
            },
            'roe': {
                '매우_좋음': 20.0, '좋음': 15.0, '보통': 10.0, '나쁨': 5.0, '매우_나쁨': 0.0
            },
            
            # 안정성 지표 (강화된 기준)
            'debt_ratio': {
                '매우_좋음': 50.0, '좋음': 70.0, '보통': 100.0, '나쁨': 150.0, '매우_나쁨': 200.0
            },
            'quick_ratio': {
                '매우_좋음': 150.0, '좋음': 120.0, '보통': 100.0, '나쁨': 80.0, '매우_나쁨': 50.0
            },
            'reserve_ratio': {
                '매우_좋음': 500.0, '좋음': 300.0, '보통': 250.0, '나쁨': 150.0, '매우_나쁨': 50.0
            },
            
            # 시장가치 지표 (PER, PBR은 낮을수록 좋음, 배당지표는 높을수록 좋음)
            'per': {
                '매우_좋음': 5.0, '좋음': 10.0, '보통': 15.0, '나쁨': 20.0, '매우_나쁨': 30.0
            },
            'pbr': {
                '매우_좋음': 0.5, '좋음': 1.0, '보통': 1.5, '나쁨': 2.0, '매우_나쁨': 3.0
            },
            'dividend_yield': {
                '매우_좋음': 5.0, '좋음': 3.0, '보통': 2.0, '나쁨': 1.0, '매우_나쁨': 0.0
            },
            # 배당성향: 적정범위 중심으로 개선
            'dividend_payout': {
                '매우_좋음': 40.0, '좋음': 30.0, '보통': 10.0, '나쁨': 0.0, '매우_나쁨': 100.0
            }
        }
        
    def _init_templates(self):
        """평가 문구 템플릿 초기화"""
        self.templates = {
            'revenue_growth': {
                '매우_좋음': '매출액이 {value:.1f}%의 높은 연평균 성장률을 기록하며 뛰어난 외형 성장을 달성하고 있습니다.',
                '좋음': '매출액이 {value:.1f}%의 양호한 연평균 성장률을 유지하고 있습니다.',
                '보통': '매출액이 {value:.1f}%의 안정적인 연평균 성장률을 유지하고 있습니다.',
                '나쁨': '매출액이 {value:.1f}%의 저조한 연평균 성장률을 기록하고 있습니다.',
                '매우_나쁨': '매출액이 {value:.1f}%의 매우 저조한 연평균 성장률을 기록하고 있어 우려됩니다.'
            },
            'operating_profit_growth': {
                '매우_좋음': '영업이익이 {value:.1f}%의 높은 성장률을 기록하며 수익성이 크게 개선되고 있습니다.',
                '좋음': '영업이익이 {value:.1f}%의 양호한 성장률을 보이고 있습니다.',
                '보통': '영업이익이 {value:.1f}%의 안정적인 성장률을 유지하고 있습니다.',
                '나쁨': '영업이익이 {value:.1f}%의 저조한 성장률을 기록하고 있습니다.',
                '매우_나쁨': '영업이익이 {value:.1f}%의 매우 저조한 성장률을 기록하고 있어 우려됩니다.'
            },
            'net_profit_growth': {
                '매우_좋음': '순이익이 {value:.1f}%의 높은 성장률을 기록하며 수익성이 크게 개선되고 있습니다.',
                '좋음': '순이익이 {value:.1f}%의 양호한 성장률을 보이고 있습니다.',
                '보통': '순이익이 {value:.1f}%의 안정적인 성장률을 유지하고 있습니다.',
                '나쁨': '순이익이 {value:.1f}%의 저조한 성장률을 기록하고 있습니다.',
                '매우_나쁨': '순이익이 {value:.1f}%의 매우 저조한 성장률을 기록하고 있어 우려됩니다.'
            },
            
            # 수익성 지표 템플릿
            'operating_margin': {
                '매우_좋음': '영업이익률이 {value:.1f}%로 매우 우수한 수준을 유지하고 있습니다.',
                '좋음': '영업이익률이 {value:.1f}%로 양호한 수준을 보이고 있습니다.',
                '보통': '영업이익률이 {value:.1f}%로 보통 수준을 유지하고 있습니다.',
                '나쁨': '영업이익률이 {value:.1f}%로 다소 저조한 수준을 보이고 있습니다.',
                '매우_나쁨': '영업이익률이 {value:.1f}%로 매우 저조한 수준을 보이고 있어 우려됩니다.'
            },
            'net_margin': {
                '매우_좋음': '순이익률이 {value:.1f}%로 매우 우수한 수준을 유지하고 있습니다.',
                '좋음': '순이익률이 {value:.1f}%로 양호한 수준을 보이고 있습니다.',
                '보통': '순이익률이 {value:.1f}%로 보통 수준을 유지하고 있습니다.',
                '나쁨': '순이익률이 {value:.1f}%로 다소 저조한 수준을 보이고 있습니다.',
                '매우_나쁨': '순이익률이 {value:.1f}%로 매우 저조한 수준을 보이고 있어 우려됩니다.'
            },
            'roe': {
                '매우_좋음': 'ROE가 {value:.1f}%로 매우 우수한 자기자본 수익성을 보이고 있습니다.',
                '좋음': 'ROE가 {value:.1f}%로 양호한 자기자본 수익성을 유지하고 있습니다.',
                '보통': 'ROE가 {value:.1f}%로 보통 수준의 자기자본 수익성을 보이고 있습니다.',
                '나쁨': 'ROE가 {value:.1f}%로 낮은 자기자본 수익성을 보이고 있어 개선이 필요합니다.',
                '매우_나쁨': 'ROE가 {value:.1f}%로 매우 낮은 자기자본 수익성을 보이고 있어 즉각적인 개선이 필요합니다.'
            },
            
            # 안정성 지표 템플릿
            'debt_ratio': {
                '매우_좋음': '부채비율이 {value:.1f}%로 매우 안정적인 재무구조를 유지하고 있습니다.',
                '좋음': '부채비율이 {value:.1f}%로 양호한 재무구조를 보이고 있습니다.',
                '보통': '부채비율이 {value:.1f}%로 보통 수준의 재무구조를 유지하고 있습니다.',
                '나쁨': '부채비율이 {value:.1f}%로 다소 높은 수준을 보이고 있어 주의가 필요합니다.',
                '매우_나쁨': '부채비율이 {value:.1f}%로 매우 높은 수준을 보이고 있어 위험합니다.'
            },
            'quick_ratio': {
                '매우_좋음': '당좌비율이 {value:.1f}%로 매우 우수한 단기 지급능력을 보유하고 있습니다.',
                '좋음': '당좌비율이 {value:.1f}%로 양호한 단기 지급능력을 보유하고 있습니다.',
                '보통': '당좌비율이 {value:.1f}%로 보통 수준의 단기 지급능력을 보유하고 있습니다.',
                '나쁨': '당좌비율이 {value:.1f}%로 다소 낮은 단기 지급능력을 보이고 있어 주의가 필요합니다.',
                '매우_나쁨': '당좌비율이 {value:.1f}%로 매우 낮은 단기 지급능력을 보이고 있어 위험합니다.'
            },
            'reserve_ratio': {
                '매우_좋음': '유보율이 {value:.1f}%로 매우 높은 수준의 내부유보를 보유하고 있습니다.',
                '좋음': '유보율이 {value:.1f}%로 양호한 수준의 내부유보를 보유하고 있습니다.',
                '보통': '유보율이 {value:.1f}%로 보통 수준의 내부유보를 보유하고 있습니다.',
                '나쁨': '유보율이 {value:.1f}%로 다소 낮은 수준의 내부유보를 보이고 있어 주의가 필요합니다.',
                '매우_나쁨': '유보율이 {value:.1f}%로 매우 낮은 수준의 내부유보를 보이고 있어 위험합니다.'
            },
            
            # 시장가치 지표 템플릿
            'per': {
                '매우_좋음': 'PER이 {value:.1f}배로 매우 저평가된 상태입니다.',
                '좋음': 'PER이 {value:.1f}배로 저평가된 상태입니다.',
                '보통': 'PER이 {value:.1f}배로 적정 수준의 밸류에이션을 보이고 있습니다.',
                '나쁨': 'PER이 {value:.1f}배로 다소 고평가된 상태입니다.',
                '매우_나쁨': 'PER이 {value:.1f}배로 매우 고평가된 상태입니다.'
            },
            'pbr': {
                '매우_좋음': 'PBR이 {value:.1f}배로 매우 저평가된 상태입니다.',
                '좋음': 'PBR이 {value:.1f}배로 저평가된 상태입니다.',
                '보통': 'PBR이 {value:.1f}배로 보통 수준의 밸류에이션을 보이고 있습니다.',
                '나쁨': 'PBR이 {value:.1f}배로 다소 고평가된 상태입니다.',
                '매우_나쁨': 'PBR이 {value:.1f}배로 매우 고평가된 상태입니다.'
            },
            'dividend_yield': {
                '매우_좋음': '배당수익률이 {value:.1f}%로 매우 높은 수준의 배당 매력도를 보이고 있습니다.',
                '좋음': '배당수익률이 {value:.1f}%로 양호한 수준의 배당 매력도를 보이고 있습니다.',
                '보통': '배당수익률이 {value:.1f}%로 보통 수준의 배당 매력도를 보이고 있습니다.',
                '나쁨': '배당수익률이 {value:.1f}%로 다소 낮은 수준의 배당 매력도를 보이고 있습니다.',
                '매우_나쁨': '배당수익률이 {value:.1f}%로 매우 낮은 수준의 배당 매력도를 보이고 있습니다.'
            },
            'dividend_payout': {
                '매우_좋음': '배당성향이 {value:.1f}%로 매우 높은 수준의 주주환원 정책을 보이고 있습니다.',
                '좋음': '배당성향이 {value:.1f}%로 양호한 수준의 주주환원 정책을 보이고 있습니다.',
                '보통': '배당성향이 {value:.1f}%로 보통 수준의 주주환원 정책을 보이고 있습니다.',
                '나쁨': '배당성향이 {value:.1f}%로 다소 낮은 수준의 주주환원 정책을 보이고 있습니다.',
                '매우_나쁨': '배당성향이 {value:.1f}%로 매우 낮은 수준의 주주환원 정책을 보이고 있습니다.'
            }
        }
        
        self.final_templates = {
            '매우_좋음': '{company_name}은(는) 전반적으로 매우 우수한 재무 상태를 보이고 있습니다. 성장성, 수익성, 안정성이 모두 뛰어나며, 적극적인 매수를 추천합니다.',
            '좋음': '{company_name}은(는) 전반적으로 양호한 재무 상태를 보이고 있습니다. 현재 주가 수준에서 매수를 고려해볼 만합니다.',
            '보통': '{company_name}은(는) 전반적으로 무난한 재무 상태를 보이고 있습니다. 현재 주가 수준에서는 보유가 적절해 보입니다.',
            '나쁨': '{company_name}은(는) 성장성 둔화, 수익성 저하 또는 재무 안정성 측면에서 주의가 필요합니다. 투자 결정 시 신중한 검토가 요구되며, 매도유의 의견을 제시합니다.',
            '매우_나쁨': '{company_name}은(는) 주요 재무 지표가 전반적으로 악화되고 있어 심각한 재무 위험에 직면해 있습니다. 지속적인 모니터링과 개선 노력이 없다면 기업 가치 하락이 예상됩니다. 매도 의견을 제시합니다.'
        }
        
    def analyze(self, ticker: str, eval_date: Optional[date] = None) -> Dict:
        """
        주어진 종목의 재무제표를 분석하고 평가 결과를 반환합니다.
        
        Args:
            ticker (str): 종목코드
            eval_date (Optional[date]): 평가 기준일. 기본값은 오늘
            
        Returns:
            Dict: 평가 결과
        """
        if eval_date is None:
            eval_date = date.today()
            
        # 재무 데이터 조회
        financial_data = self._get_financial_data(ticker)
        if not financial_data:
            return {
                'success': False,
                'message': f'재무 데이터를 찾을 수 없습니다. (종목코드: {ticker})'
            }
            
        try:
            # 영역별 평가 수행
            growth_result = self._evaluate_growth(financial_data)
            profitability_result = self._evaluate_profitability(financial_data)
            stability_result = self._evaluate_stability(financial_data)
            market_value_result = self._evaluate_market_value(financial_data)
            
            # 영역별 점수가 없는 경우 0점 처리
            growth_score = growth_result['score'] if growth_result['evaluations'] else 0
            profitability_score = profitability_result['score'] if profitability_result['evaluations'] else 0
            stability_score = stability_result['score'] if stability_result['evaluations'] else 0
            market_value_score = market_value_result['score'] if market_value_result['evaluations'] else 0
            
            # 종합 평가
            total_weight = 0
            total_score = 0
            
            if growth_result['evaluations']:
                total_score += growth_score * self.weights['areas']['growth']
                total_weight += self.weights['areas']['growth']
                
            if profitability_result['evaluations']:
                total_score += profitability_score * self.weights['areas']['profitability']
                total_weight += self.weights['areas']['profitability']
                
            if stability_result['evaluations']:
                total_score += stability_score * self.weights['areas']['stability']
                total_weight += self.weights['areas']['stability']
                
            if market_value_result['evaluations']:
                total_score += market_value_score * self.weights['areas']['market_value']
                total_weight += self.weights['areas']['market_value']
                
            if total_weight > 0:
                final_score = total_score / total_weight
            else:
                final_score = 0
            
            # 투자 의견 결정 (5단계)
            if final_score >= 4.5:
                investment_opinion = '강력 매수'
                evaluation_grade = '매우_좋음'
            elif final_score >= 3.5:
                investment_opinion = '매수/보유'
                evaluation_grade = '좋음'
            elif final_score >= 2.5:
                investment_opinion = '관망/보유'
                evaluation_grade = '보통'
            elif final_score >= 1.5:
                investment_opinion = '매도 유의'
                evaluation_grade = '나쁨'
            else:
                investment_opinion = '매도'
                evaluation_grade = '매우_나쁨'
                
            # 평가 결과 저장
            growth_grade = self._get_grade(growth_score)
            profitability_grade = self._get_grade(profitability_score)
            stability_grade = self._get_grade(stability_score)
            market_value_grade = self._get_grade(market_value_score)
            total_grade = self._get_grade(final_score)
            evaluation_details = {
                'growth': growth_result,
                'growth_grade': growth_grade,
                'profitability': profitability_result,
                'profitability_grade': profitability_grade,
                'stability': stability_result,
                'stability_grade': stability_grade,
                'market_value': market_value_result,
                'market_value_grade': market_value_grade,
                'total_grade': total_grade
            }
            # 각 영역별 모든 세부 의견을 리스트로 추출
            def get_all_descriptions(result):
                return [ev['description'] for ev in result.get('evaluations', [])]
            summary_details = {
                '성장성': get_all_descriptions(growth_result),
                '수익성': get_all_descriptions(profitability_result),
                '안정성': get_all_descriptions(stability_result),
                '시장가치': get_all_descriptions(market_value_result)
            }
            summary = {
                '종합': self.final_templates[evaluation_grade].format(
                    company_name=self._get_company_name(ticker)
                ),
                **summary_details
            }
            self._save_evaluation_result(
                ticker=ticker,
                eval_date=eval_date,
                growth_score=growth_score,
                profitability_score=profitability_score,
                stability_score=stability_score,
                market_value_score=market_value_score,
                total_score=final_score,
                investment_opinion=investment_opinion,
                evaluation_details=evaluation_details,
                summary_report=summary['종합']
            )
            
            return {
                'success': True,
                'ticker': ticker,
                'eval_date': eval_date or datetime.today().date(),
                'growth_score': growth_score,
                'growth_grade': growth_grade,
                'profitability_score': profitability_score,
                'profitability_grade': profitability_grade,
                'stability_score': stability_score,
                'stability_grade': stability_grade,
                'market_value_score': market_value_score,
                'market_value_grade': market_value_grade,
                'total_score': final_score,
                'total_grade': total_grade,
                'investment_opinion': investment_opinion,
                'evaluation_details': evaluation_details,
                'summary': summary
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'평가 중 오류가 발생했습니다: {str(e)}'
            }
            
    def _get_financial_data(self, ticker: str) -> Dict:
        """DB에서 재무 데이터를 조회합니다. 각 지표별로 [{'year': y, 'period': p, 'value': v}, ...] 형태로 반환."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT year, period, revenue, operating_profit, net_profit, operating_margin, net_margin, roe, debt_ratio, quick_ratio, reserve_ratio, eps, per, bps, pbr, cash_dividend, dividend_yield, dividend_payout, industry_per
                FROM financial_info
                WHERE ticker = ? AND period = 'Y'
                ORDER BY year ASC
            """, (ticker,))
            rows = cursor.fetchall()
            if not rows:
                return {}
            columns = ['year', 'period', 'revenue', 'operating_profit', 'net_profit', 'operating_margin', 'net_margin', 'roe', 'debt_ratio', 'quick_ratio', 'reserve_ratio', 'eps', 'per', 'bps', 'pbr', 'cash_dividend', 'dividend_yield', 'dividend_payout', 'industry_per']
            data = {col: [] for col in columns[2:]}
            for row in rows:
                y, p = row[0], row[1]
                for idx, col in enumerate(columns[2:], 2):
                    data[col].append({'year': y, 'period': p, 'value': row[idx]})
            return data
            
    def _get_company_name(self, ticker: str) -> str:
        """종목코드로 기업명을 조회합니다."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT stock_name
                FROM Stocks
                WHERE stock_code = ?
            """, (ticker,))
            
            result = cursor.fetchone()
            return result[0] if result else ticker
            
    def _calculate_growth_rate(self, values: List[float], years: int) -> Optional[float]:
        """CAGR(연평균 성장률) 계산."""
        if len(values) < 2 or not all(isinstance(x, (int, float)) for x in values[:2]):
            return None
        start, end = values[0], values[-1]
        if start <= 0 or years <= 0:
            return None
        try:
            return (pow(end / start, 1 / years) - 1) * 100
        except Exception:
            return None
            
    def _calculate_score(self, value: float, thresholds: Dict[str, float]) -> float:
        """주어진 값에 대한 점수를 계산합니다. (매우 나쁨 등급 반영)"""
        # 높을수록 좋은 지표
        if thresholds.get('매우_좋음', 0) > thresholds.get('나쁨', 0):
            if value >= thresholds['매우_좋음']:
                return 5.0
            elif value >= thresholds['좋음']:
                return 4.0
            elif value >= thresholds['보통']:
                return 3.0
            elif value >= thresholds['나쁨']:
                return 2.0
            elif value >= thresholds.get('매우_나쁨', float('-inf')):
                return 1.0
            else:
                return 1.0
        # 낮을수록 좋은 지표
        else:
            if value <= thresholds['매우_좋음']:
                return 5.0
            elif value <= thresholds['좋음']:
                return 4.0
            elif value <= thresholds['보통']:
                return 3.0
            elif value <= thresholds['나쁨']:
                return 2.0
            elif value <= thresholds.get('매우_나쁨', float('inf')):
                return 1.0
            else:
                return 1.0
            
    def _evaluate_growth(self, data: Dict) -> Dict:
        """성장성 지표를 평가합니다. (CAGR 공식 적용, 실제값만 사용, 음수/0 예외처리, 템플릿 메시지 적용)"""
        results = {
            'evaluations': [],
            'score': 0.0
        }
        # 매출액 성장률 (CAGR)
        if 'revenue' in data:
            values = sorted(data['revenue'], key=lambda x: int(x['year']))
            valid_values = [v for v in values if isinstance(v['value'], (int, float)) and v['value'] is not None]
            if len(valid_values) >= 2:
                start, end = valid_values[0], valid_values[-1]
                years = int(end['year']) - int(start['year'])
                if years > 0:
                    if start['value'] <= 0 or end['value'] <= 0:
                        cagr = None
                        score = 0.0
                        grade = '매우_나쁨'
                        template_key = self.GRADE_TO_TEMPLATE_KEY.get(grade, '보통')
                        desc = self.templates['revenue_growth'][template_key].format(value=0.0) + f" (평가연도: {end['year']})"
                    else:
                        cagr = self._calculate_growth_rate([start['value'], end['value']], years)
                        if isinstance(cagr, complex):
                            score = 0.0
                            grade = '매우_나쁨'
                            template_key = self.GRADE_TO_TEMPLATE_KEY.get(grade, '보통')
                            desc = self.templates['revenue_growth'][template_key].format(value=0.0) + f" (평가연도: {end['year']})"
                        else:
                            score = self._calculate_score(cagr, self.thresholds['revenue_growth'])
                            grade = self._get_grade(score)
                            template_key = self.GRADE_TO_TEMPLATE_KEY.get(grade, '보통')
                            desc = self.templates['revenue_growth'][template_key].format(value=cagr) + f" (평가연도: {start['year']}→{end['year']})"
                    results['evaluations'].append({
                        'metric': 'revenue_growth',
                        'value': cagr if cagr is not None else 0.0,
                        'score': score,
                        'description': desc
                    })
        # 영업이익 성장률 (CAGR)
        if 'operating_profit' in data:
            values = sorted(data['operating_profit'], key=lambda x: int(x['year']))
            valid_values = [v for v in values if isinstance(v['value'], (int, float)) and v['value'] is not None]
            if len(valid_values) >= 2:
                start, end = valid_values[0], valid_values[-1]
                years = int(end['year']) - int(start['year'])
                if years > 0:
                    if start['value'] <= 0 or end['value'] <= 0:
                        cagr = None
                        score = 0.0
                        grade = '매우_나쁨'
                        template_key = self.GRADE_TO_TEMPLATE_KEY.get(grade, '보통')
                        desc = self.templates['operating_profit_growth'][template_key].format(value=0.0) + f" (평가연도: {end['year']})"
                    else:
                        cagr = self._calculate_growth_rate([start['value'], end['value']], years)
                        if isinstance(cagr, complex):
                            score = 0.0
                            grade = '매우_나쁨'
                            template_key = self.GRADE_TO_TEMPLATE_KEY.get(grade, '보통')
                            desc = self.templates['operating_profit_growth'][template_key].format(value=0.0) + f" (평가연도: {end['year']})"
                        else:
                            score = self._calculate_score(cagr, self.thresholds['operating_profit_growth'])
                            grade = self._get_grade(score)
                            template_key = self.GRADE_TO_TEMPLATE_KEY.get(grade, '보통')
                            desc = self.templates['operating_profit_growth'][template_key].format(value=cagr) + f" (평가연도: {start['year']}→{end['year']})"
                    results['evaluations'].append({
                        'metric': 'operating_profit_growth',
                        'value': cagr if cagr is not None else 0.0,
                        'score': score,
                        'description': desc
                    })
        # 순이익 성장률 (CAGR)
        if 'net_profit' in data:
            values = sorted(data['net_profit'], key=lambda x: int(x['year']))
            valid_values = [v for v in values if isinstance(v['value'], (int, float)) and v['value'] is not None]
            if len(valid_values) >= 2:
                start, end = valid_values[0], valid_values[-1]
                years = int(end['year']) - int(start['year'])
                if years > 0:
                    if start['value'] <= 0 or end['value'] <= 0:
                        cagr = None
                        score = 0.0
                        grade = '매우_나쁨'
                        template_key = self.GRADE_TO_TEMPLATE_KEY.get(grade, '보통')
                        desc = self.templates['net_profit_growth'][template_key].format(value=0.0) + f" (평가연도: {end['year']})"
                    else:
                        cagr = self._calculate_growth_rate([start['value'], end['value']], years)
                        if isinstance(cagr, complex):
                            score = 0.0
                            grade = '매우_나쁨'
                            template_key = self.GRADE_TO_TEMPLATE_KEY.get(grade, '보통')
                            desc = self.templates['net_profit_growth'][template_key].format(value=0.0) + f" (평가연도: {end['year']})"
                        else:
                            score = self._calculate_score(cagr, self.thresholds['net_profit_growth'])
                            grade = self._get_grade(score)
                            template_key = self.GRADE_TO_TEMPLATE_KEY.get(grade, '보통')
                            desc = self.templates['net_profit_growth'][template_key].format(value=cagr) + f" (평가연도: {start['year']}→{end['year']})"
                    results['evaluations'].append({
                        'metric': 'net_profit_growth',
                        'value': cagr if cagr is not None else 0.0,
                        'score': score,
                        'description': desc
                    })
        # 가중 평균 점수 계산
        scores = [e['score'] for e in results['evaluations']]
        if scores:
            results['score'] = round(
                scores[0] * 0.4 + (scores[1] if len(scores)>1 else 0) * 0.3 + (scores[2] if len(scores)>2 else 0) * 0.3, 2)
        return results
        
    def _evaluate_profitability(self, data: Dict) -> Dict:
        """수익성 지표를 평가합니다. (실제값만 사용, 음수/0 예외처리, 템플릿 메시지 적용)"""
        results = {
            'evaluations': [],
            'score': 0.0
        }
        # 영업이익률
        if 'operating_margin' in data:
            values = sorted(data['operating_margin'], key=lambda x: int(x['year']))
            valid_values = [v for v in values if isinstance(v['value'], (int, float)) and v['value'] is not None]
            if valid_values:
                end = valid_values[-1]
                score = self._calculate_score(end['value'], self.thresholds['operating_margin'])
                grade = self._get_grade(score)
                template_key = self.GRADE_TO_TEMPLATE_KEY.get(grade, '보통')
                desc = self.templates['operating_margin'][template_key].format(value=end['value']) + f" (평가연도: {end['year']})"
                results['evaluations'].append({
                    'metric': 'operating_margin',
                    'value': end['value'],
                    'score': score,
                    'description': desc
                })
        # 순이익률
        if 'net_margin' in data:
            values = sorted(data['net_margin'], key=lambda x: int(x['year']))
            valid_values = [v for v in values if isinstance(v['value'], (int, float)) and v['value'] is not None]
            if valid_values:
                end = valid_values[-1]
                score = self._calculate_score(end['value'], self.thresholds['net_margin'])
                grade = self._get_grade(score)
                template_key = self.GRADE_TO_TEMPLATE_KEY.get(grade, '보통')
                desc = self.templates['net_margin'][template_key].format(value=end['value']) + f" (평가연도: {end['year']})"
                results['evaluations'].append({
                    'metric': 'net_margin',
                    'value': end['value'],
                    'score': score,
                    'description': desc
                })
        # ROE
        if 'roe' in data:
            values = sorted(data['roe'], key=lambda x: int(x['year']))
            valid_values = [v for v in values if isinstance(v['value'], (int, float)) and v['value'] is not None]
            if valid_values:
                end = valid_values[-1]
                if end['value'] <= 0:
                    score = 0.0
                    grade = '매우_나쁨'
                    template_key = self.GRADE_TO_TEMPLATE_KEY.get(grade, '보통')
                    desc = self.templates['roe'][template_key].format(value=0.0) + f" (평가연도: {end['year']})"
                else:
                    score = self._calculate_score(end['value'], self.thresholds['roe'])
                    grade = self._get_grade(score)
                    template_key = self.GRADE_TO_TEMPLATE_KEY.get(grade, '보통')
                    desc = self.templates['roe'][template_key].format(value=end['value']) + f" (평가연도: {end['year']})"
                results['evaluations'].append({
                    'metric': 'roe',
                    'value': end['value'],
                    'score': score,
                    'description': desc
                })
        # 가중 평균 점수 계산
        scores = [e['score'] for e in results['evaluations']]
        if scores:
            results['score'] = round(
                scores[0] * 0.4 + (scores[1] if len(scores)>1 else 0) * 0.3 + (scores[2] if len(scores)>2 else 0) * 0.3, 2)
        return results
        
    def _get_latest_valid(self, data_list):
        """최신 연도부터 값이 있는 첫 번째 데이터 반환."""
        for item in sorted(data_list, key=lambda x: int(x['year']), reverse=True):
            if item['value'] is not None and item['value'] != 0:
                return item
        return None
        
    def _evaluate_stability(self, data: Dict) -> Dict:
        """안정성 지표를 평가합니다."""
        results = {
            'evaluations': [],
            'score': 0.0
        }
        # 부채비율
        if 'debt_ratio' in data and data['debt_ratio']:
            dr = self._get_latest_valid(data['debt_ratio'])
            if dr:
                print(f"[안정성-부채비율] {dr['year']}년: {dr['value']}")
                score = self._calculate_score(dr['value'], self.thresholds['debt_ratio'])
                grade = self._get_grade(score)
                template_key = self.GRADE_TO_TEMPLATE_KEY.get(grade, '보통')
                results['evaluations'].append({
                    'metric': 'debt_ratio',
                    'value': dr['value'],
                    'score': score,
                    'description': self.templates['debt_ratio'].get(
                        template_key,
                        self.templates['debt_ratio']['보통']
                    ).format(value=dr['value']) + f" (평가연도: {dr['year']})"
                })
                results['score'] += score * self.weights['stability']['debt_ratio']
            else:
                print("[안정성-부채비율] 데이터 부족")
        # 당좌비율
        if 'quick_ratio' in data and data['quick_ratio']:
            qr = self._get_latest_valid(data['quick_ratio'])
            if qr:
                print(f"[안정성-당좌비율] {qr['year']}년: {qr['value']}")
                score = self._calculate_score(qr['value'], self.thresholds['quick_ratio'])
                grade = self._get_grade(score)
                template_key = self.GRADE_TO_TEMPLATE_KEY.get(grade, '보통')
                results['evaluations'].append({
                    'metric': 'quick_ratio',
                    'value': qr['value'],
                    'score': score,
                    'description': self.templates['quick_ratio'].get(
                        template_key,
                        self.templates['quick_ratio']['보통']
                    ).format(value=qr['value']) + f" (평가연도: {qr['year']})"
                })
                results['score'] += score * self.weights['stability']['quick_ratio']
            else:
                print("[안정성-당좌비율] 데이터 부족")
        # 유보율
        if 'reserve_ratio' in data and data['reserve_ratio']:
            rr = self._get_latest_valid(data['reserve_ratio'])
            if rr:
                print(f"[안정성-유보율] {rr['year']}년: {rr['value']}")
                score = self._calculate_score(rr['value'], self.thresholds['reserve_ratio'])
                grade = self._get_grade(score)
                template_key = self.GRADE_TO_TEMPLATE_KEY.get(grade, '보통')
                results['evaluations'].append({
                    'metric': 'reserve_ratio',
                    'value': rr['value'],
                    'score': score,
                    'description': self.templates['reserve_ratio'].get(
                        template_key,
                        self.templates['reserve_ratio']['보통']
                    ).format(value=rr['value']) + f" (평가연도: {rr['year']})"
                })
                results['score'] += score * self.weights['stability']['reserve_ratio']
            else:
                print("[안정성-유보율] 데이터 부족")
        return results
        
    def _evaluate_market_value(self, data: Dict) -> Dict:
        """시장가치 지표를 평가합니다. (동일업종 PER과의 상대평가 포함)"""
        results = {
            'evaluations': [],
            'score': 0.0
        }
        # PER (동일업종 평균 대비 상대평가)
        per = self._get_latest_valid(data.get('per', []))
        industry_per = self._get_latest_valid(data.get('industry_per', []))
        if per and industry_per and per['value'] is not None and industry_per['value'] is not None:
            company_per = per['value']
            avg_per = industry_per['value']
            rel_desc = ''
            if avg_per > 0 and company_per > 0:
                per_ratio = company_per / avg_per
                if per_ratio <= 0.60:
                    score = 5.0
                elif per_ratio <= 0.80:
                    score = 4.0
                elif per_ratio <= 1.00:
                    score = 3.0
                elif per_ratio <= 1.20:
                    score = 2.0
                elif per_ratio <= 1.50:
                    score = 1.0
                else:
                    score = 0.0
                # 설명
                if abs(per_ratio-1) < 0.05:
                    rel_desc = f" (동일업종 평균 {avg_per:.2f}배와 유사)"
                elif per_ratio < 1:
                    rel_desc = f" (동일업종 평균 {avg_per:.2f}배 대비 저평가)"
                else:
                    rel_desc = f" (동일업종 평균 {avg_per:.2f}배 대비 고평가)"
            else:
                score = 0.0
                rel_desc = f" (PER 계산 불가: PER={company_per}, 업종평균={avg_per})"
            grade = self._get_grade(score)
            template_key = self.GRADE_TO_TEMPLATE_KEY.get(grade, '보통')
            results['evaluations'].append({
                'metric': 'per',
                'value': company_per,
                'score': score,
                'description': self.templates['per'].get(
                    template_key,
                    self.templates['per']['보통']
                ).format(value=company_per) + rel_desc + f" (평가연도: {per['year']})"
            })
            results['score'] += score * self.weights['market_value']['per']
        else:
            print("[시장가치-PER] 데이터 부족")
        # PBR
        if 'pbr' in data and data['pbr']:
            pbr = self._get_latest_valid(data['pbr'])
            if pbr and pbr['value'] > 0:
                print(f"[시장가치-PBR] {pbr['year']}년: {pbr['value']}")
                score = self._calculate_score(pbr['value'], self.thresholds['pbr'])
                grade = self._get_grade(score)
                template_key = self.GRADE_TO_TEMPLATE_KEY.get(grade, '보통')
                results['evaluations'].append({
                    'metric': 'pbr',
                    'value': pbr['value'],
                    'score': score,
                    'description': self.templates['pbr'].get(
                        template_key,
                        self.templates['pbr']['보통']
                    ).format(value=pbr['value']) + f" (평가연도: {pbr['year']})"
                })
                results['score'] += score * self.weights['market_value']['pbr']
            else:
                print("[시장가치-PBR] 데이터 부족")
        # 배당수익률
        if 'dividend_yield' in data and data['dividend_yield']:
            dy = self._get_latest_valid(data['dividend_yield'])
            if dy:
                print(f"[시장가치-배당수익률] {dy['year']}년: {dy['value']}")
                score = self._calculate_score(dy['value'], self.thresholds['dividend_yield'])
                grade = self._get_grade(score)
                template_key = self.GRADE_TO_TEMPLATE_KEY.get(grade, '보통')
                results['evaluations'].append({
                    'metric': 'dividend_yield',
                    'value': dy['value'],
                    'score': score,
                    'description': self.templates['dividend_yield'].get(
                        template_key,
                        self.templates['dividend_yield']['보통']
                    ).format(value=dy['value']) + f" (평가연도: {dy['year']})"
                })
                results['score'] += score * self.weights['market_value']['dividend_yield']
            else:
                print("[시장가치-배당수익률] 데이터 부족")
        # 배당성향
        if 'cash_dividend' in data and 'eps' in data and data['cash_dividend'] and data['eps']:
            cd = self._get_latest_valid(data['cash_dividend'])
            eps = self._get_latest_valid(data['eps'])
            if eps and eps['value'] > 0:
                dividend_payout = (cd['value'] / eps['value']) * 100
                print(f"[시장가치-배당성향] {cd['year']}년: {cd['value']}, {eps['year']}년: {eps['value']} → {dividend_payout:.2f}%")
                score = self._calculate_score(dividend_payout, self.thresholds['dividend_payout'])
                grade = self._get_grade(score)
                template_key = self.GRADE_TO_TEMPLATE_KEY.get(grade, '보통')
                results['evaluations'].append({
                    'metric': 'dividend_payout',
                    'value': dividend_payout,
                    'score': score,
                    'description': self.templates['dividend_payout'].get(
                        template_key,
                        self.templates['dividend_payout']['보통']
                    ).format(value=dividend_payout) + f" (평가연도: {cd['year']}, {eps['year']})"
                })
                results['score'] += score * self.weights['market_value']['dividend_payout']
            else:
                print("[시장가치-배당성향] 데이터 부족")
        return results
        
    def _get_grade(self, score: float) -> str:
        """점수에 따른 등급을 반환합니다."""
        if score >= 4.5:
            return '매우 좋음'
        elif score >= 3.5:
            return '좋음'
        elif score >= 2.5:
            return '보통'
        elif score >= 1.5:
            return '나쁨'
        else:
            return '매우 나쁨'
        
    def _save_evaluation_result(self, **kwargs):
        """평가 결과를 DB에 저장합니다."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO financial_evaluation (
                    ticker, eval_date, growth_score, profitability_score,
                    stability_score, market_value_score, total_score,
                    investment_opinion, evaluation_details, summary_report
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, eval_date) DO UPDATE SET
                    growth_score = excluded.growth_score,
                    profitability_score = excluded.profitability_score,
                    stability_score = excluded.stability_score,
                    market_value_score = excluded.market_value_score,
                    total_score = excluded.total_score,
                    investment_opinion = excluded.investment_opinion,
                    evaluation_details = excluded.evaluation_details,
                    summary_report = excluded.summary_report,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                kwargs['ticker'],
                kwargs['eval_date'],
                kwargs['growth_score'],
                kwargs['profitability_score'],
                kwargs['stability_score'],
                kwargs['market_value_score'],
                kwargs['total_score'],
                kwargs['investment_opinion'],
                json.dumps(kwargs['evaluation_details'], ensure_ascii=False),
                kwargs['summary_report']
            )) 

    # EPS/BPS 성장률 등급화 예시 (데이터 있을 때만)
    def _evaluate_eps_growth(self, data: Dict) -> Dict:
        results = {'evaluations': [], 'score': 0.0}
        if 'eps' in data and len(data['eps']) >= 2:
            values = sorted(data['eps'], key=lambda x: int(x['year']))
            start, end = values[0], values[-1]
            years = int(end['year']) - int(start['year'])
            if start['value'] and end['value'] and years > 0:
                cagr = self._calculate_growth_rate([start['value'], end['value']], years)
                score = self._calculate_score(cagr, self.thresholds['revenue_growth'])
                results['evaluations'].append({
                    'metric': 'eps_growth',
                    'value': cagr,
                    'score': score,
                    'description': f"EPS 연평균 성장률: {cagr:.2f}%"
                })
                results['score'] = score
        return results 

    GRADE_TO_TEMPLATE_KEY = {
        '매우 좋음': '매우_좋음',
        '좋음': '좋음',
        '보통': '보통',
        '나쁨': '나쁨',
        '매우 나쁨': '매우_나쁨'
    } 