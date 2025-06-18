from flask import Flask, jsonify, render_template, request
import sqlite3
import os
import sys
from datetime import datetime, timedelta
import threading
import re

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
    """
    상위 20개 급등주 데이터
    """
    date = get_market_date()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        query = '''
        WITH stock_industries AS (
            SELECT ism.stock_code, im.industry_name
            FROM industry_stock_mapping ism
            JOIN industry_master im ON ism.industry_id = im.industry_id
        )
        SELECT s.stock_code, s.stock_name, d.price_change_ratio, si.industry_name
        FROM DailyStocks d
        JOIN Stocks s ON d.stock_code = s.stock_code
        LEFT JOIN stock_industries si ON d.stock_code = si.stock_code
        WHERE d.date = ?
        ORDER BY d.price_change_ratio DESC
        LIMIT 20
        '''
        cursor.execute(query, (date,))
        rows = cursor.fetchall()
        results = []
        for row in rows:
            stock_code = row[0]
            results.append({
                'code': stock_code,
                'name': row[1],
                'change_rate': row[2],
                'industry': row[3] if row[3] else '',
                'theme': ','.join([t['theme_name'] for t in get_themes_for_stock(stock_code)])
            })
        return jsonify({'market_status': get_market_status(), 'date': date, 'data': results})

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
               i.industry_name
        FROM ranked r
        LEFT JOIN (
            SELECT ism.stock_code, im.industry_name
            FROM industry_stock_mapping ism
            JOIN industry_master im ON ism.industry_id = im.industry_id
        ) i ON r.stock_code = i.stock_code
        WHERE r.rank <= 30
        ORDER BY r.rebound_rate DESC, r.avg_trading_value_5d DESC
        '''
        params = (date, date, date, date, date)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        results = []
        for row in rows:
            stock_code = row[0]
            results.append({
                'code': stock_code,
                'name': row[1],
                'close_price': row[2],
                'change_rate': row[3],
                'rebound_rate': row[4],
                'avg_trading_value_5d': row[5],
                'industry': row[6] if row[6] else '',
                'theme': ','.join([t['theme_name'] for t in get_themes_for_stock(stock_code)])
            })
        return jsonify({'market_status': get_market_status(), 'date': date, 'data': results})

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

@app.route('/api/refresh/theme', methods=['POST'])
def refresh_theme():
    today = datetime.now().strftime('%Y-%m-%d')
    def job():
        os.system('python3 -m src.collector.theme_crawler')
        os.system('python3 -m src.analyzer.sector_theme_analyzer')
    threading.Thread(target=job).start()
    return jsonify({'last_theme_refresh': today})

@app.route('/api/refresh/industry', methods=['POST'])
def refresh_industry():
    today = datetime.now().strftime('%Y-%m-%d')
    def job():
        os.system('python3 -m src.collector.industry_crawler')
        os.system('python3 -m src.analyzer.sector_theme_analyzer')
    threading.Thread(target=job).start()
    return jsonify({'last_industry_refresh': today})

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

def extract_common_stock_name(stock_name):
    """
    우선주 종목명에서 본주명 추출 (예: '삼성전자우' -> '삼성전자')
    다양한 우선주 표기(우, 우B, 우(전환), 1우, 2우B 등) 대응
    """
    # 대표적 우선주 패턴: 우, 우B, 우C, 우(전환), 1우, 2우B 등
    # 공백, 괄호, 숫자, 영문자 등 변형 포함
    return re.sub(r'( ?[0-9]*우([A-Z]|\([^)]+\))?)$', '', stock_name)

def get_themes_for_stock(stock_code):
    """
    종목코드에 해당하는 테마 리스트 반환. 우선주면 본주 테마를 공유.
    theme_stock_mapping + theme_master 기준으로 조회
    """
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # 1. 우선주 여부 판별 및 본주명 추출
        cursor.execute("SELECT stock_name FROM Stocks WHERE stock_code = ?", (stock_code,))
        row = cursor.fetchone()
        if not row:
            return []
        stock_name = row[0]
        common_name = extract_common_stock_name(stock_name)
        # 2. 본주 코드 찾기(동일한 본주명, is_active=True, 우선주 아님)
        cursor.execute("SELECT stock_code FROM Stocks WHERE stock_name = ? AND is_active = 1", (common_name,))
        main_row = cursor.fetchone()
        main_code = main_row[0] if main_row else stock_code
        # 3. 테마 매핑(theme_stock_mapping + theme_master)
        cursor.execute("""
            SELECT t.theme_id, m.theme_name
            FROM theme_stock_mapping t
            JOIN theme_master m ON t.theme_id = m.theme_id
            WHERE t.stock_code = ?
        """, (main_code,))
        return [dict(theme_id=r[0], theme_name=r[1]) for r in cursor.fetchall()]

@app.route('/stock_detail')
def stock_detail():
    code = request.args.get('code', '')
    stock_info = {}
    price_info = {}
    industry = ''
    theme = ''
    news_list = []
    market_cap = ''
    market_type = ''
    listed_date = ''
    rebound_rate = None
    # DB에서 종목 정보/시세/업종/테마/뉴스 쿼리
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # 기본정보
        cursor.execute("SELECT stock_name, market_type, listed_date FROM Stocks WHERE stock_code = ?", (code,))
        row = cursor.fetchone()
        if row:
            stock_info = {'name': row[0], 'code': code}
            market_type = row[1]
            listed_date = row[2] or ''
        # 최근 시세
        cursor.execute("SELECT close_price, price_change_ratio, volume, trading_value, market_cap FROM DailyStocks WHERE stock_code = ? ORDER BY date DESC LIMIT 1", (code,))
        row = cursor.fetchone()
        if row:
            price_info = {
                'close_price': row[0],
                'change_rate': row[1],
                'volume': row[2],
                'trading_value': row[3],
                'market_cap': row[4]
            }
            market_cap = row[4]
        # 60일 저점 반등률 계산
        cursor.execute("SELECT MIN(low_price) FROM DailyStocks WHERE stock_code = ? AND date >= date('now', '-59 day')", (code,))
        min_low_60d = cursor.fetchone()[0]
        close_price = price_info.get('close_price') if price_info else None
        if min_low_60d and close_price and min_low_60d > 0:
            rebound_rate = round((close_price - min_low_60d) / min_low_60d * 100, 2)
        # 업종
        cursor.execute("SELECT im.industry_name FROM industry_stock_mapping ism JOIN industry_master im ON ism.industry_id = im.industry_id WHERE ism.stock_code = ? LIMIT 1", (code,))
        row = cursor.fetchone()
        if row:
            industry = row[0]
        # 테마
        cursor.execute("SELECT tm.theme_name FROM theme_stock_mapping tsm JOIN theme_master tm ON tsm.theme_id = tm.theme_id WHERE tsm.stock_code = ? LIMIT 1", (code,))
        row = cursor.fetchone()
        if row:
            theme = row[0]
        # 뉴스(최신 5개)
        cursor.execute("SELECT title, url FROM stock_news WHERE stock_code = ? ORDER BY date DESC, id DESC LIMIT 5", (code,))
        news_list = [{'title': r[0], 'url': r[1]} for r in cursor.fetchall()]
    return render_template('stock_detail.html',
        stock_name=stock_info.get('name', '정보 없음'),
        stock_code=code,
        industry=industry or '정보 없음',
        theme=theme or '정보 없음',
        market_cap=market_cap or '정보 없음',
        market_type=market_type or '정보 없음',
        listed_date=listed_date or '정보 없음',
        close_price=price_info.get('close_price', '정보 없음'),
        change_rate=price_info.get('change_rate', '정보 없음'),
        volume=price_info.get('volume', '정보 없음'),
        trading_value=price_info.get('trading_value', '정보 없음'),
        news_list=news_list,
        rebound_rate=rebound_rate
    )

@app.route('/api/stock/<code>/ohlcv')
def get_stock_ohlcv(code):
    days = int(request.args.get('days', 60))
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date, open_price, high_price, low_price, close_price, volume
            FROM DailyStocks
            WHERE stock_code = ?
            ORDER BY date DESC LIMIT ?
        """, (code, days))
        rows = cursor.fetchall()[::-1]  # 날짜 오름차순
    return jsonify({
        'dates': [r[0] for r in rows],
        'open': [r[1] for r in rows],
        'high': [r[2] for r in rows],
        'low': [r[3] for r in rows],
        'close': [r[4] for r in rows],
        'volume': [r[5] for r in rows]
    })

if __name__ == '__main__':
    app.run(debug=True, port=5001) 