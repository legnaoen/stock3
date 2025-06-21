from flask import Blueprint, jsonify
import sys
import os
import sqlite3

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analyzer.sector_detail_analyzer import get_sector_info, get_sector_stocks

THEME_INDUSTRY_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../db/theme_industry.db'))

sector_api = Blueprint('sector_api', __name__)

@sector_api.route('/api/sector/<sector_type>/<int:sector_id>')
def get_sector_details(sector_type, sector_id):
    """테마/업종의 상세 정보와 종목 리스트를 반환하는 API"""
    try:
        # 기본 정보 조회
        sector_info = get_sector_info(sector_type, sector_id)
        if not sector_info:
            return jsonify({'error': f'{sector_type} {sector_id} not found'}), 404
        # 최신 등락률(차트와 동일) 추가
        table = 'industry_daily_performance' if sector_type == 'industry' else 'theme_daily_performance'
        id_col = 'industry_id' if sector_type == 'industry' else 'theme_id'
        with sqlite3.connect(THEME_INDUSTRY_DB) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT price_change_ratio FROM {table} WHERE {id_col} = ? ORDER BY date DESC LIMIT 1", (sector_id,))
            row = cursor.fetchone()
            if row and row[0] is not None:
                sector_info['latest_change_rate'] = row[0]
            else:
                sector_info['latest_change_rate'] = 0.0
        # 모멘텀/시세지표 분석 결과 추가
        try:
            import pandas as pd
            momentum_fields = [
                'price_momentum_1d', 'price_momentum_3d', 'price_momentum_5d', 'price_momentum_10d',
                'volume_momentum_1d', 'volume_momentum_3d', 'volume_momentum_5d',
                'rsi_value', 'leader_count', 'leader_momentum', 'trend_score'
            ]
            with sqlite3.connect(THEME_INDUSTRY_DB) as conn:
                query = f"""
                SELECT {', '.join(momentum_fields)}
                FROM momentum_analysis
                WHERE target_id = ? AND target_type = ?
                ORDER BY date DESC LIMIT 1
                """
                cursor = conn.cursor()
                cursor.execute(query, (sector_id, sector_type.upper()))
                row = cursor.fetchone()
                if row:
                    sector_info['momentum_analysis'] = dict(zip(momentum_fields, row))
                    # [추가] 해석 코멘트 생성
                    m = sector_info['momentum_analysis']
                    comments = []
                    # 1일 가격모멘텀
                    v = m.get('price_momentum_1d')
                    if v is not None:
                        if v >= 3:
                            comments.append('1일 가격모멘텀: 단기 급등 신호')
                        elif v <= -3:
                            comments.append('1일 가격모멘텀: 단기 급락 신호')
                        else:
                            comments.append('1일 가격모멘텀: 단기 변동성 약함')
                    # 3일 가격모멘텀
                    v = m.get('price_momentum_3d')
                    if v is not None:
                        if v >= 5:
                            comments.append('3일 가격모멘텀: 강한 상승 모멘텀')
                        elif v <= -5:
                            comments.append('3일 가격모멘텀: 하락 전환 신호')
                        else:
                            comments.append('3일 가격모멘텀: 변동성 약함')
                    # 5일 가격모멘텀
                    v = m.get('price_momentum_5d')
                    if v is not None:
                        if v >= 5:
                            comments.append('5일 가격모멘텀: 강한 상승 모멘텀')
                        elif v <= -5:
                            comments.append('5일 가격모멘텀: 하락 전환 신호')
                        else:
                            comments.append('5일 가격모멘텀: 변동성 약함')
                    # 10일 가격모멘텀
                    v = m.get('price_momentum_10d')
                    if v is not None:
                        if v >= 5:
                            comments.append('10일 가격모멘텀: 강한 상승 모멘텀')
                        elif v <= -5:
                            comments.append('10일 가격모멘텀: 하락 전환 신호')
                        else:
                            comments.append('10일 가격모멘텀: 변동성 약함')
                    # 1일 거래대금모멘텀
                    v = m.get('volume_momentum_1d')
                    if v is not None:
                        if v >= 30:
                            comments.append('1일 거래대금모멘텀: 거래 급증')
                        elif v <= -30:
                            comments.append('1일 거래대금모멘텀: 거래 급감')
                        else:
                            comments.append('1일 거래대금모멘텀: 평이한 거래')
                    # 3일 거래대금모멘텀
                    v = m.get('volume_momentum_3d')
                    if v is not None:
                        if v >= 30:
                            comments.append('3일 거래대금모멘텀: 거래 증가세')
                        elif v <= -30:
                            comments.append('3일 거래대금모멘텀: 거래 감소세')
                        else:
                            comments.append('3일 거래대금모멘텀: 평이한 거래')
                    # 5일 거래대금모멘텀
                    v = m.get('volume_momentum_5d')
                    if v is not None:
                        if v >= 30:
                            comments.append('5일 거래대금모멘텀: 거래 증가세')
                        elif v <= -30:
                            comments.append('5일 거래대금모멘텀: 거래 감소세')
                        else:
                            comments.append('5일 거래대금모멘텀: 평이한 거래')
                    # RSI
                    v = m.get('rsi_value')
                    if v is not None:
                        if v >= 70:
                            comments.append('RSI: 과매수 구간, 단기 조정 주의')
                        elif v <= 30:
                            comments.append('RSI: 과매도 구간, 반등 가능성')
                        else:
                            comments.append('RSI: 중립 구간')
                    # 주도주 모멘텀
                    v = m.get('leader_momentum')
                    if v is not None:
                        if v >= 3:
                            comments.append('주도주 모멘텀: 주도주가 강하게 상승 중')
                        elif v <= 0:
                            comments.append('주도주 모멘텀: 주도주가 약세')
                        else:
                            comments.append('주도주 모멘텀: 보통')
                    # 종합 추세점수
                    v = m.get('trend_score')
                    if v is not None:
                        if v >= 80:
                            comments.append('종합 추세점수: 매우 강한 추세')
                        elif v >= 60:
                            comments.append('종합 추세점수: 상승 추세')
                        elif v >= 40:
                            comments.append('종합 추세점수: 중립')
                        else:
                            comments.append('종합 추세점수: 약세 추세')
                    sector_info['momentum_analysis_comment'] = comments
                else:
                    sector_info['momentum_analysis'] = None
                    sector_info['momentum_analysis_comment'] = []
        except Exception as e:
            sector_info['momentum_analysis'] = None
            sector_info['momentum_analysis_comment'] = []
        # 종목 리스트 조회
        stocks = get_sector_stocks(sector_type, sector_id)
        return jsonify({
            'sector_info': sector_info,
            'stocks': stocks
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500 