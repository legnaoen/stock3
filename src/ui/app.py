from flask import Flask, jsonify, render_template, request
import sqlite3
import os
import sys
from datetime import datetime, timedelta
import threading

# Add src to Python path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from utils.market_time import get_market_date, is_market_open, get_market_status
from api.sector_api import sector_api

app = Flask(__name__)
app.register_blueprint(sector_api)

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../db/stock_master.db'))
THEME_INDUSTRY_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../db/theme_industry.db'))

# 전체 데이터 갱신 마지막 실행일 저장 (메모리, 운영시 DB/파일로 대체 가능)
last_full_refresh = {'date': None}
last_industry_refresh = {'date': None}

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

@app.route('/api/performance/rebound')
def get_rebound_performance():
    """
    최근 60일 저점 대비 30% 이상 반등 + 5일 평균 거래대금 상위 30위 종목 추출
    종목명, 등락률, 업종, 테마, 5일평균 거래대금 등 반환
    """
    date = get_market_date()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # 1. 60일 저점, 5일 평균 거래대금, 현재가, 등락률 계산
        # 2. 60일 저점 대비 30% 이상 반등 종목 추출
        # 3. 반등률 내림차순 정렬, 상위 30위
        query = '''
        WITH recent_prices AS (
            SELECT stock_code, MIN(low_price) AS min_low_60d
            FROM DailyStocks
            WHERE date >= date(?, '-59 day') AND date <= ?
            GROUP BY stock_code
        ),
        avg_trading_value AS (
            SELECT stock_code, AVG(trading_value) AS avg_trading_value_5d
            FROM DailyStocks
            WHERE date >= date(?, '-4 day') AND date <= ?
            GROUP BY stock_code
        ),
        today_price AS (
            SELECT stock_code, close_price, low_price, price_change_ratio
            FROM DailyStocks
            WHERE date = ?
        ),
        joined AS (
            SELECT s.stock_code, s.stock_name, t.close_price, t.price_change_ratio, r.min_low_60d, a.avg_trading_value_5d
            FROM Stocks s
            JOIN today_price t ON s.stock_code = t.stock_code
            JOIN recent_prices r ON s.stock_code = r.stock_code
            JOIN avg_trading_value a ON s.stock_code = a.stock_code
            WHERE r.min_low_60d > 0 AND t.close_price IS NOT NULL AND t.close_price > 0
        ),
        rebound AS (
            SELECT *,
                ROUND((CAST(close_price AS FLOAT) - CAST(min_low_60d AS FLOAT)) / CAST(min_low_60d AS FLOAT) * 100, 2) AS rebound_rate
            FROM joined
            WHERE close_price >= min_low_60d * 1.3
        ),
        ranked AS (
            SELECT *, ROW_NUMBER() OVER (ORDER BY rebound_rate DESC, avg_trading_value_5d DESC) AS rank
            FROM rebound
        )
        SELECT r.stock_code, r.stock_name, r.close_price, r.price_change_ratio, r.rebound_rate, r.avg_trading_value_5d,
               i.industry_name, IFNULL(t.themes, '')
        FROM ranked r
        LEFT JOIN (
            SELECT ism.stock_code, im.industry_name
            FROM industry_stock_mapping ism
            JOIN industry_master im ON ism.industry_id = im.industry_id
        ) i ON r.stock_code = i.stock_code
        LEFT JOIN (
            SELECT tsm.stock_code, GROUP_CONCAT(tm.theme_name) as themes
            FROM theme_stock_mapping tsm
            JOIN theme_master tm ON tsm.theme_id = tm.theme_id
            GROUP BY tsm.stock_code
        ) t ON r.stock_code = t.stock_code
        WHERE r.rank <= 30
        ORDER BY r.rebound_rate DESC, r.avg_trading_value_5d DESC
        '''
        cursor.execute(query, (date, date, date, date, date))
        results = []
        for row in cursor.fetchall():
            results.append({
                'stock_code': row[0],
                'name': row[1],
                'close_price': row[2],
                'change_rate': row[3],
                'rebound_rate': row[4],
                'avg_trading_value_5d': row[5],
                'industry': row[6] if row[6] else '',
                'theme': row[7] if row[7] else ''
            })
        return jsonify({
            'market_status': get_market_status(),
            'date': date,
            'data': results
        })

# 빠른 새로고침: krx_collector + analyzer
@app.route('/api/refresh/quick', methods=['POST'])
def refresh_quick():
    def job():
        os.system('python3 -m src.collector.krx_collector')
        os.system('python3 -m src.analyzer.sector_theme_analyzer')
    threading.Thread(target=job).start()
    return '', 204

# 전체 데이터 갱신: theme/industry/krx_collector + analyzer
@app.route('/api/refresh/full', methods=['POST'])
def refresh_full():
    today = datetime.now().strftime('%Y-%m-%d')
    now = datetime.now()
    # 업종 갱신 제한 (한달 이내면 스킵)
    do_industry = True
    if last_industry_refresh['date']:
        last = datetime.strptime(last_industry_refresh['date'], '%Y-%m-%d')
        if (now - last).days < 30:
            do_industry = False
    def job():
        os.system('python3 -m src.collector.theme_crawler')
        if do_industry:
            os.system('python3 -m src.collector.industry_crawler')
            last_industry_refresh['date'] = today
        os.system('python3 -m src.collector.krx_collector')
        os.system('python3 -m src.analyzer.sector_theme_analyzer')
        last_full_refresh['date'] = today
    threading.Thread(target=job).start()
    # 반환: 마지막 전체갱신일
    return jsonify({'last_full_refresh': last_full_refresh['date'] or '-'})

@app.route('/api/sector/<sector_type>/<int:sector_id>/chart')
def get_sector_chart(sector_type, sector_id):
    days = int(request.args.get('days', 60))
    metric = request.args.get('metric', 'market_cap')
    metric_map = {
        'market_cap': ('market_cap', '시가총액', '원'),
        'trading_value': ('trading_value', '거래대금', '원'),
        'price_change_ratio': ('price_change_ratio', '등락률', '%')
    }
    if metric not in metric_map:
        return jsonify({'error': 'Invalid metric'}), 400
    col, label, unit = metric_map[metric]
    table = 'industry_daily_performance' if sector_type == 'industry' else 'theme_daily_performance'
    id_col = 'industry_id' if sector_type == 'industry' else 'theme_id'
    with sqlite3.connect(THEME_INDUSTRY_DB) as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT date, {col} FROM {table}
            WHERE {id_col} = ?
            ORDER BY date DESC LIMIT ?
        """, (sector_id, days))
        rows = cursor.fetchall()[::-1]  # 날짜 오름차순
    return jsonify({
        'dates': [r[0] for r in rows],
        'values': [r[1] for r in rows],
        'metric': metric,
        'label': label,
        'unit': unit
    })

if __name__ == '__main__':
    app.run(debug=True, port=5001) 