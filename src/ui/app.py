from flask import Flask, jsonify, render_template
import sqlite3
import os
import sys

# Add src to Python path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from utils.market_time import get_market_date, is_market_open, get_market_status
from api.sector_api import sector_api

app = Flask(__name__)
app.register_blueprint(sector_api)

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../db/stock_master.db'))
THEME_INDUSTRY_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../db/theme_industry.db'))

@app.route('/')
def index():
    market_status = get_market_status()
    return render_template('index.html', market_status=market_status)

@app.route('/sector_detail')
def sector_detail():
    return render_template('sector_detail.html')

@app.route('/api/market/status')
def market_status():
    """현장 상태 반환"""
    return jsonify({
        'status': get_market_status(),
        'date': get_market_date()
    })

@app.route('/api/performance/mixed')
def get_mixed_performance():
    """업종과 테마를 통합한 상위 30개 데이터"""
    date = get_market_date()  # 08:30 기준으로 당일/전일 결정
    
    with sqlite3.connect(THEME_INDUSTRY_DB) as perf_conn:
        cursor = perf_conn.cursor()
        cursor.execute("ATTACH DATABASE ? AS master", (DB_PATH,))
        
        query = """
        WITH combined AS (
            SELECT 'industry' as type, 
                   m.industry_id as id,
                   m.industry_name as name, 
                   i.price_change_ratio,
                   (
                       SELECT COUNT(DISTINCT m2.stock_code)
                       FROM master.industry_stock_mapping m2
                       JOIN master.DailyStocks d2 ON m2.stock_code = d2.stock_code
                       WHERE m2.industry_id = m.industry_id
                       AND d2.date = ?
                       AND d2.price_change_ratio > 0
                   ) as up_stocks,
                   (
                       SELECT COUNT(DISTINCT m2.stock_code)
                       FROM master.industry_stock_mapping m2
                       JOIN master.DailyStocks d2 ON m2.stock_code = d2.stock_code
                       WHERE m2.industry_id = m.industry_id
                       AND d2.date = ?
                       AND d2.price_change_ratio < 0
                   ) as down_stocks,
                   (
                       SELECT COUNT(DISTINCT m2.stock_code)
                       FROM master.industry_stock_mapping m2
                       JOIN master.DailyStocks d2 ON m2.stock_code = d2.stock_code
                       WHERE m2.industry_id = m.industry_id
                       AND d2.date = ?
                       AND d2.price_change_ratio = 0
                   ) as unchanged_stocks,
                   i.market_cap,
                   i.trading_value,
                   i.leader_stock_codes
            FROM industry_daily_performance i
            JOIN (SELECT industry_id, industry_name FROM master.industry_master) m 
                 ON i.industry_id = m.industry_id
            WHERE i.date = ?
            
            UNION ALL
            
            SELECT 'theme' as type,
                   m.theme_id as id,
                   m.theme_name as name,
                   t.price_change_ratio,
                   (
                       SELECT COUNT(DISTINCT m2.stock_code)
                       FROM master.theme_stock_mapping m2
                       JOIN master.DailyStocks d2 ON m2.stock_code = d2.stock_code
                       WHERE m2.theme_id = m.theme_id
                       AND d2.date = ?
                       AND d2.price_change_ratio > 0
                   ) as up_stocks,
                   (
                       SELECT COUNT(DISTINCT m2.stock_code)
                       FROM master.theme_stock_mapping m2
                       JOIN master.DailyStocks d2 ON m2.stock_code = d2.stock_code
                       WHERE m2.theme_id = m.theme_id
                       AND d2.date = ?
                       AND d2.price_change_ratio < 0
                   ) as down_stocks,
                   (
                       SELECT COUNT(DISTINCT m2.stock_code)
                       FROM master.theme_stock_mapping m2
                       JOIN master.DailyStocks d2 ON m2.stock_code = d2.stock_code
                       WHERE m2.theme_id = m.theme_id
                       AND d2.date = ?
                       AND d2.price_change_ratio = 0
                   ) as unchanged_stocks,
                   t.market_cap,
                   t.trading_value,
                   t.leader_stock_codes
            FROM theme_daily_performance t
            JOIN (SELECT theme_id, theme_name FROM master.theme_master) m 
                 ON t.theme_id = m.theme_id
            WHERE t.date = ?
        )
        SELECT *
        FROM combined
        ORDER BY price_change_ratio DESC
        LIMIT 30
        """
        
        cursor.execute(query, (date, date, date, date, date, date, date, date))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'type': row[0],
                'id': row[1],
                'name': row[2],
                'change_rate': row[3],
                'up_stocks': row[4],
                'down_stocks': row[5],
                'unchanged_stocks': row[6],
                'market_cap': row[7],
                'trading_value': row[8],
                'leader_stocks': row[9].split(',') if row[9] else []
            })
        
        cursor.execute("DETACH DATABASE master")
        
        return jsonify({
            'market_status': get_market_status(),
            'date': date,
            'data': results
        })

@app.route('/api/performance/industry')
def get_industry_performance():
    """업종별 상위 30개 데이터"""
    date = get_market_date()
    
    with sqlite3.connect(THEME_INDUSTRY_DB) as perf_conn:
        cursor = perf_conn.cursor()
        cursor.execute("ATTACH DATABASE ? AS master", (DB_PATH,))
        
        query = """
        SELECT 'industry' as type,
               m.industry_id as id,
               m.industry_name as name,
               i.price_change_ratio,
               (
                   SELECT COUNT(DISTINCT m2.stock_code)
                   FROM master.industry_stock_mapping m2
                   JOIN master.DailyStocks d2 ON m2.stock_code = d2.stock_code
                   WHERE m2.industry_id = m.industry_id
                   AND d2.date = ?
                   AND d2.price_change_ratio > 0
               ) as up_stocks,
               (
                   SELECT COUNT(DISTINCT m2.stock_code)
                   FROM master.industry_stock_mapping m2
                   JOIN master.DailyStocks d2 ON m2.stock_code = d2.stock_code
                   WHERE m2.industry_id = m.industry_id
                   AND d2.date = ?
                   AND d2.price_change_ratio < 0
               ) as down_stocks,
               (
                   SELECT COUNT(DISTINCT m2.stock_code)
                   FROM master.industry_stock_mapping m2
                   JOIN master.DailyStocks d2 ON m2.stock_code = d2.stock_code
                   WHERE m2.industry_id = m.industry_id
                   AND d2.date = ?
                   AND d2.price_change_ratio = 0
               ) as unchanged_stocks,
               i.market_cap,
               i.trading_value,
               i.leader_stock_codes
        FROM industry_daily_performance i
        JOIN (SELECT industry_id, industry_name FROM master.industry_master) m 
             ON i.industry_id = m.industry_id
        WHERE i.date = ?
        ORDER BY i.price_change_ratio DESC
        LIMIT 30
        """
        
        cursor.execute(query, (date, date, date, date))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'type': row[0],
                'id': row[1],
                'name': row[2],
                'change_rate': row[3],
                'up_stocks': row[4],
                'down_stocks': row[5],
                'unchanged_stocks': row[6],
                'market_cap': row[7],
                'trading_value': row[8],
                'leader_stocks': row[9].split(',') if row[9] else []
            })
        
        cursor.execute("DETACH DATABASE master")
        
        return jsonify({
            'market_status': get_market_status(),
            'date': date,
            'data': results
        })

@app.route('/api/performance/theme')
def get_theme_performance():
    """테마별 상위 30개 데이터"""
    date = get_market_date()
    
    with sqlite3.connect(THEME_INDUSTRY_DB) as perf_conn:
        cursor = perf_conn.cursor()
        cursor.execute("ATTACH DATABASE ? AS master", (DB_PATH,))
        
        query = """
        SELECT 'theme' as type,
               m.theme_id as id,
               m.theme_name as name,
               t.price_change_ratio,
               (
                   SELECT COUNT(DISTINCT m2.stock_code)
                   FROM master.theme_stock_mapping m2
                   JOIN master.DailyStocks d2 ON m2.stock_code = d2.stock_code
                   WHERE m2.theme_id = m.theme_id
                   AND d2.date = ?
                   AND d2.price_change_ratio > 0
               ) as up_stocks,
               (
                   SELECT COUNT(DISTINCT m2.stock_code)
                   FROM master.theme_stock_mapping m2
                   JOIN master.DailyStocks d2 ON m2.stock_code = d2.stock_code
                   WHERE m2.theme_id = m.theme_id
                   AND d2.date = ?
                   AND d2.price_change_ratio < 0
               ) as down_stocks,
               (
                   SELECT COUNT(DISTINCT m2.stock_code)
                   FROM master.theme_stock_mapping m2
                   JOIN master.DailyStocks d2 ON m2.stock_code = d2.stock_code
                   WHERE m2.theme_id = m.theme_id
                   AND d2.date = ?
                   AND d2.price_change_ratio = 0
               ) as unchanged_stocks,
               t.market_cap,
               t.trading_value,
               t.leader_stock_codes
        FROM theme_daily_performance t
        JOIN (SELECT theme_id, theme_name FROM master.theme_master) m 
             ON t.theme_id = m.theme_id
        WHERE t.date = ?
        ORDER BY t.price_change_ratio DESC
        LIMIT 30
        """
        
        cursor.execute(query, (date, date, date, date))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'type': row[0],
                'id': row[1],
                'name': row[2],
                'change_rate': row[3],
                'up_stocks': row[4],
                'down_stocks': row[5],
                'unchanged_stocks': row[6],
                'market_cap': row[7],
                'trading_value': row[8],
                'leader_stocks': row[9].split(',') if row[9] else []
            })
        
        cursor.execute("DETACH DATABASE master")
        
        return jsonify({
            'market_status': get_market_status(),
            'date': date,
            'data': results
        })

@app.route('/api/performance/surge')
def get_surge_performance():
    """상위 20개 급등주 데이터"""
    date = get_market_date()
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        query = """
        WITH stock_themes AS (
            SELECT 
                tsm.stock_code,
                GROUP_CONCAT(tm.theme_name) as themes
            FROM theme_stock_mapping tsm
            JOIN theme_master tm ON tsm.theme_id = tm.theme_id
            GROUP BY tsm.stock_code
        ), stock_industries AS (
            SELECT 
                ism.stock_code,
                im.industry_name
            FROM industry_stock_mapping ism
            JOIN industry_master im ON ism.industry_id = im.industry_id
        )
        SELECT 
            s.stock_name,
            d.price_change_ratio,
            si.industry_name,
            st.themes
        FROM DailyStocks d
        JOIN Stocks s ON d.stock_code = s.stock_code
        LEFT JOIN stock_industries si ON d.stock_code = si.stock_code
        LEFT JOIN stock_themes st ON d.stock_code = st.stock_code
        WHERE d.date = ?
        ORDER BY d.price_change_ratio DESC
        LIMIT 20
        """
        
        cursor.execute(query, (date,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'name': row[0],
                'change_rate': row[1],
                'industry': row[2] if row[2] else '',
                'theme': row[3] if row[3] else ''
            })
        
        return jsonify({
            'market_status': get_market_status(),
            'date': date,
            'data': results
        })

if __name__ == '__main__':
    app.run(debug=True, port=5001) 