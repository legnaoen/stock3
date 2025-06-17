from flask import Blueprint, jsonify
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analyzer.sector_detail_analyzer import get_sector_info, get_sector_stocks

sector_api = Blueprint('sector_api', __name__)

@sector_api.route('/api/sector/<sector_type>/<int:sector_id>')
def get_sector_details(sector_type, sector_id):
    """테마/업종의 상세 정보와 종목 리스트를 반환하는 API"""
    try:
        # 기본 정보 조회
        sector_info = get_sector_info(sector_type, sector_id)
        if not sector_info:
            return jsonify({'error': f'{sector_type} {sector_id} not found'}), 404
            
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