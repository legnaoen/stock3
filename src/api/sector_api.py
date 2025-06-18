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