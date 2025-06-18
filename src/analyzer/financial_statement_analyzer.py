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
                'per': 0.3,
                'pbr': 0.3,
                'dividend_yield': 0.2,
                'dividend_payout': 0.2
            }
        }
        
    def _init_thresholds(self):
        """평가 기준값 초기화"""
        self.thresholds = {
            # 성장성 지표 (높을수록 좋음)
            'revenue_growth': {
                '매우_좋음': 20.0, '좋음': 10.0, '보통': 0.0, '나쁨': -10.0
            },
            'operating_profit_growth': {
                '매우_좋음': 25.0, '좋음': 15.0, '보통': 0.0, '나쁨': -15.0
            },
            'net_profit_growth': {
                '매우_좋음': 25.0, '좋음': 15.0, '보통': 0.0, '나쁨': -15.0
            },
            
            # 수익성 지표 (높을수록 좋음)
            'operating_margin': {
                '매우_좋음': 15.0, '좋음': 10.0, '보통': 5.0, '나쁨': 2.0
            },
            'net_margin': {
                '매우_좋음': 10.0, '좋음': 7.0, '보통': 4.0, '나쁨': 1.0
            },
            'roe': {
                '매우_좋음': 20.0, '좋음': 15.0, '보통': 10.0, '나쁨': 5.0
            },
            
            # 안정성 지표 (낮을수록 좋음)
            'debt_ratio': {
                '매우_좋음': 50.0, '좋음': 100.0, '보통': 150.0, '나쁨': 200.0
            },
            'quick_ratio': {
                '매우_좋음': 150.0, '좋음': 100.0, '보통': 70.0, '나쁨': 50.0
            },
            'reserve_ratio': {
                '매우_좋음': 500.0, '좋음': 300.0, '보통': 200.0, '나쁨': 100.0
            },
            
            # 시장가치 지표 (PER, PBR은 낮을수록 좋음, 배당지표는 높을수록 좋음)
            'per': {
                '매우_좋음': 5.0, '좋음': 10.0, '보통': 15.0, '나쁨': 20.0
            },
            'pbr': {
                '매우_좋음': 0.5, '좋음': 1.0, '보통': 1.5, '나쁨': 2.0
            },
            'dividend_yield': {
                '매우_좋음': 5.0, '좋음': 3.0, '보통': 2.0, '나쁨': 1.0
            },
            'dividend_payout': {
                '매우_좋음': 50.0, '좋음': 30.0, '보통': 20.0, '나쁨': 10.0
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
            '나쁨': '{company_name}은(는) 성장성 둔화, 수익성 저하 또는 재무 안정성 측면에서 주의가 필요합니다. 투자 결정 시 신중한 검토가 요구되며, 관망 의견을 제시합니다.',
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
            
            # 투자 의견 결정
            if final_score >= 4.0:
                investment_opinion = '매수'
                evaluation_grade = '매우_좋음'
            elif final_score >= 3.0:
                investment_opinion = '보유'
                evaluation_grade = '좋음'
            elif final_score >= 2.0:
                investment_opinion = '관망'
                evaluation_grade = '보통'
            else:
                investment_opinion = '매도'
                evaluation_grade = '나쁨'
                
            # 평가 결과 저장
            evaluation_details = {
                'growth': growth_result,
                'profitability': profitability_result,
                'stability': stability_result,
                'market_value': market_value_result
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
                evaluation_details=evaluation_details
            )
            
            return {
                'success': True,
                'ticker': ticker,
                'eval_date': eval_date,
                'growth_score': growth_score,
                'profitability_score': profitability_score,
                'stability_score': stability_score,
                'market_value_score': market_value_score,
                'total_score': final_score,
                'investment_opinion': investment_opinion,
                'evaluation_details': evaluation_details,
                'summary': self.final_templates[evaluation_grade].format(
                    company_name=self._get_company_name(ticker)
                )
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'평가 중 오류가 발생했습니다: {str(e)}'
            }
            
    def _get_financial_data(self, ticker: str) -> Dict:
        """DB에서 재무 데이터를 조회합니다."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 최근 3년간의 재무 데이터 조회
            cursor.execute("""
                SELECT *
                FROM financial_info
                WHERE ticker = ?
                ORDER BY period DESC
                LIMIT 3
            """, (ticker,))
            
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            
            if not rows:
                return {}
                
            # 데이터 구조화
            data = {}
            for col_idx, column in enumerate(columns):
                data[column] = [row[col_idx] for row in rows]
                
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
            
    def _calculate_growth_rate(self, values: List[float]) -> Optional[float]:
        """성장률을 계산합니다."""
        if len(values) < 2 or not all(isinstance(x, (int, float)) for x in values[:2]):
            return None
            
        try:
            return ((values[0] / values[1]) - 1) * 100
        except (ZeroDivisionError, TypeError):
            return None
            
    def _calculate_score(self, value: float, thresholds: Dict[str, float]) -> float:
        """주어진 값에 대한 점수를 계산합니다."""
        # PER, PBR은 낮을수록 좋음
        if thresholds.get('매우_좋음', 0) > thresholds.get('나쁨', 0):  # 높을수록 좋은 지표
            if value >= thresholds['매우_좋음']:
                return 5.0
            elif value >= thresholds['좋음']:
                return 4.0
            elif value >= thresholds['보통']:
                return 3.0
            elif value >= thresholds['나쁨']:
                return 2.0
            else:
                return 1.0
        else:  # 낮을수록 좋은 지표 (PER, PBR, 부채비율 등)
            if value <= thresholds['매우_좋음']:
                return 5.0
            elif value <= thresholds['좋음']:
                return 4.0
            elif value <= thresholds['보통']:
                return 3.0
            elif value <= thresholds['나쁨']:
                return 2.0
            else:
                return 1.0
            
    def _evaluate_growth(self, data: Dict) -> Dict:
        """성장성 지표를 평가합니다."""
        results = {
            'evaluations': [],
            'score': 0.0
        }
        
        # 매출액 성장률
        if 'revenue' in data:
            growth_rate = self._calculate_growth_rate(data['revenue'])
            if growth_rate is not None:
                score = self._calculate_score(growth_rate, self.thresholds['revenue_growth'])
                results['evaluations'].append({
                    'metric': 'revenue_growth',
                    'value': growth_rate,
                    'score': score,
                    'description': self.templates['revenue_growth'].get(
                        self._get_grade(score),
                        self.templates['revenue_growth']['보통']
                    ).format(value=growth_rate)
                })
                results['score'] += score * self.weights['growth']['revenue_growth']
                
        # 영업이익 성장률
        if 'operating_profit' in data:
            growth_rate = self._calculate_growth_rate(data['operating_profit'])
            if growth_rate is not None:
                score = self._calculate_score(growth_rate, self.thresholds['operating_profit_growth'])
                results['evaluations'].append({
                    'metric': 'operating_profit_growth',
                    'value': growth_rate,
                    'score': score,
                    'description': self.templates['operating_profit_growth'].get(
                        self._get_grade(score),
                        self.templates['operating_profit_growth']['보통']
                    ).format(value=growth_rate)
                })
                results['score'] += score * self.weights['growth']['operating_profit_growth']
                
        # 순이익 성장률
        if 'net_profit' in data:
            growth_rate = self._calculate_growth_rate(data['net_profit'])
            if growth_rate is not None:
                score = self._calculate_score(growth_rate, self.thresholds['net_profit_growth'])
                results['evaluations'].append({
                    'metric': 'net_profit_growth',
                    'value': growth_rate,
                    'score': score,
                    'description': self.templates['net_profit_growth'].get(
                        self._get_grade(score),
                        self.templates['net_profit_growth']['보통']
                    ).format(value=growth_rate)
                })
                results['score'] += score * self.weights['growth']['net_profit_growth']
                
        # 평균 점수 계산
        if results['evaluations']:
            results['score'] = results['score'] / len(results['evaluations'])
        
        return results
        
    def _evaluate_profitability(self, data: Dict) -> Dict:
        """수익성 지표를 평가합니다."""
        results = {
            'evaluations': [],
            'score': 0.0
        }
        
        # 영업이익률
        if all(key in data for key in ['operating_profit', 'revenue']):
            try:
                operating_margin = (data['operating_profit'][0] / data['revenue'][0]) * 100
                score = self._calculate_score(operating_margin, self.thresholds['operating_margin'])
                results['evaluations'].append({
                    'metric': 'operating_margin',
                    'value': operating_margin,
                    'score': score,
                    'description': self.templates['operating_margin'].get(
                        self._get_grade(score),
                        self.templates['operating_margin']['보통']
                    ).format(value=operating_margin)
                })
                results['score'] += score * self.weights['profitability']['operating_margin']
            except (ZeroDivisionError, TypeError):
                pass
                
        # 순이익률
        if all(key in data for key in ['net_profit', 'revenue']):
            try:
                net_margin = (data['net_profit'][0] / data['revenue'][0]) * 100
                score = self._calculate_score(net_margin, self.thresholds['net_margin'])
                results['evaluations'].append({
                    'metric': 'net_margin',
                    'value': net_margin,
                    'score': score,
                    'description': self.templates['net_margin'].get(
                        self._get_grade(score),
                        self.templates['net_margin']['보통']
                    ).format(value=net_margin)
                })
                results['score'] += score * self.weights['profitability']['net_margin']
            except (ZeroDivisionError, TypeError):
                pass
                
        # ROE
        if all(key in data for key in ['net_profit', 'equity']):
            try:
                roe = (data['net_profit'][0] / data['equity'][0]) * 100
                score = self._calculate_score(roe, self.thresholds['roe'])
                results['evaluations'].append({
                    'metric': 'roe',
                    'value': roe,
                    'score': score,
                    'description': self.templates['roe'].get(
                        self._get_grade(score),
                        self.templates['roe']['보통']
                    ).format(value=roe)
                })
                results['score'] += score * self.weights['profitability']['roe']
            except (ZeroDivisionError, TypeError):
                pass
                
        # 평균 점수 계산
        if results['evaluations']:
            results['score'] = results['score'] / len(results['evaluations'])
            
        return results
        
    def _evaluate_stability(self, data: Dict) -> Dict:
        """안정성 지표를 평가합니다."""
        results = {
            'evaluations': [],
            'score': 0.0
        }
        
        # 부채비율
        if 'debt_ratio' in data:
            debt_ratio = data['debt_ratio'][0]
            if debt_ratio is not None:
                score = self._calculate_score(debt_ratio, self.thresholds['debt_ratio'])
                results['evaluations'].append({
                    'metric': 'debt_ratio',
                    'value': debt_ratio,
                    'score': score,
                    'description': self.templates['debt_ratio'].get(
                        self._get_grade(score),
                        self.templates['debt_ratio']['보통']
                    ).format(value=debt_ratio)
                })
                results['score'] += score * self.weights['stability']['debt_ratio']
                
        # 당좌비율
        if 'quick_ratio' in data:
            quick_ratio = data['quick_ratio'][0]
            if quick_ratio is not None:
                score = self._calculate_score(quick_ratio, self.thresholds['quick_ratio'])
                results['evaluations'].append({
                    'metric': 'quick_ratio',
                    'value': quick_ratio,
                    'score': score,
                    'description': self.templates['quick_ratio'].get(
                        self._get_grade(score),
                        self.templates['quick_ratio']['보통']
                    ).format(value=quick_ratio)
                })
                results['score'] += score * self.weights['stability']['quick_ratio']
                
        # 유보율
        if 'reserve_ratio' in data:
            reserve_ratio = data['reserve_ratio'][0]
            if reserve_ratio is not None:
                score = self._calculate_score(reserve_ratio, self.thresholds['reserve_ratio'])
                results['evaluations'].append({
                    'metric': 'reserve_ratio',
                    'value': reserve_ratio,
                    'score': score,
                    'description': self.templates['reserve_ratio'].get(
                        self._get_grade(score),
                        self.templates['reserve_ratio']['보통']
                    ).format(value=reserve_ratio)
                })
                results['score'] += score * self.weights['stability']['reserve_ratio']
                
        # 평균 점수 계산
        if results['evaluations']:
            total_weight = sum(self.weights['stability'][eval_item['metric']] for eval_item in results['evaluations'])
            if total_weight > 0:
                results['score'] = results['score'] / total_weight
            
        return results
        
    def _evaluate_market_value(self, data: Dict) -> Dict:
        """시장가치 지표를 평가합니다."""
        results = {
            'evaluations': [],
            'score': 0.0
        }
        
        # PER
        if 'per' in data:
            per = data['per'][0]
            if per is not None and per > 0:  # 적자 기업 제외
                score = self._calculate_score(per, self.thresholds['per'])
                results['evaluations'].append({
                    'metric': 'per',
                    'value': per,
                    'score': score,
                    'description': self.templates['per'].get(
                        self._get_grade(score),
                        self.templates['per']['보통']
                    ).format(value=per)
                })
                results['score'] += score * self.weights['market_value']['per']
                
        # PBR
        if 'pbr' in data:
            pbr = data['pbr'][0]
            if pbr is not None and pbr > 0:
                score = self._calculate_score(pbr, self.thresholds['pbr'])
                results['evaluations'].append({
                    'metric': 'pbr',
                    'value': pbr,
                    'score': score,
                    'description': self.templates['pbr'].get(
                        self._get_grade(score),
                        self.templates['pbr']['보통']
                    ).format(value=pbr)
                })
                results['score'] += score * self.weights['market_value']['pbr']
                
        # 배당수익률
        if 'dividend_yield' in data:
            dividend_yield = data['dividend_yield'][0]
            if dividend_yield is not None:
                score = self._calculate_score(dividend_yield, self.thresholds['dividend_yield'])
                results['evaluations'].append({
                    'metric': 'dividend_yield',
                    'value': dividend_yield,
                    'score': score,
                    'description': self.templates['dividend_yield'].get(
                        self._get_grade(score),
                        self.templates['dividend_yield']['보통']
                    ).format(value=dividend_yield)
                })
                results['score'] += score * self.weights['market_value']['dividend_yield']
                
        # 배당성향
        if all(key in data for key in ['cash_dividend', 'eps']):
            try:
                if data['eps'][0] > 0:  # 적자 기업 제외
                    dividend_payout = (data['cash_dividend'][0] / data['eps'][0]) * 100
                    score = self._calculate_score(dividend_payout, self.thresholds['dividend_payout'])
                    results['evaluations'].append({
                        'metric': 'dividend_payout',
                        'value': dividend_payout,
                        'score': score,
                        'description': self.templates['dividend_payout'].get(
                            self._get_grade(score),
                            self.templates['dividend_payout']['보통']
                        ).format(value=dividend_payout)
                    })
                    results['score'] += score * self.weights['market_value']['dividend_payout']
            except (ZeroDivisionError, TypeError):
                pass
                
        # 평균 점수 계산
        if results['evaluations']:
            results['score'] = results['score'] / len(results['evaluations'])
            
        return results
        
    def _get_grade(self, score: float) -> str:
        """점수에 따른 등급을 반환합니다."""
        if score >= 4.5:
            return '매우_좋음'
        elif score >= 3.5:
            return '좋음'
        elif score >= 2.5:
            return '보통'
        elif score >= 1.5:
            return '나쁨'
        else:
            return '매우_나쁨'
        
    def _save_evaluation_result(self, **kwargs):
        """평가 결과를 DB에 저장합니다."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO financial_evaluation (
                    ticker, eval_date, growth_score, profitability_score,
                    stability_score, market_value_score, total_score,
                    investment_opinion, evaluation_details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, eval_date) DO UPDATE SET
                    growth_score = excluded.growth_score,
                    profitability_score = excluded.profitability_score,
                    stability_score = excluded.stability_score,
                    market_value_score = excluded.market_value_score,
                    total_score = excluded.total_score,
                    investment_opinion = excluded.investment_opinion,
                    evaluation_details = excluded.evaluation_details,
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
                json.dumps(kwargs['evaluation_details'], ensure_ascii=False)
            )) 