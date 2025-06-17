import os
import pandas as pd
from datetime import datetime, timedelta
import sqlite3
import argparse
import sys

# venv 활성화 체크
if hasattr(sys, 'base_prefix') and sys.prefix == sys.base_prefix:
    print("ERROR: venv(가상환경) 미활성화 상태입니다. 반드시 'source venv/bin/activate' 후 실행하세요.")
    sys.exit(1)

# pykrx 설치 필요: pip install pykrx
from pykrx import stock

RAW_DIR = os.path.join(os.path.dirname(__file__), '../../data/raw')
os.makedirs(RAW_DIR, exist_ok=True)

# --- 필터 기준값 변수 선언(유연하게 변경 가능) ---
SURGE_RATE = 20  # 급등주 등락률 기준(%)
TOP_TRADING_N = 10  # 거래대금 상위 N위(변경: 10)
REBOUND_TOP_N = 30  # 저점반등 거래대금 상위 N위(변경: 30)
REBOUND_RATE = 30   # 저점반등 반등률 기준(%)(변경: 30)
VOLUME_SPIKE_RATIO = 2  # 거래대금폭증주: 5일 평균 대비 배수 기준
THEME_TOP_N = 3  # 테마(ETF/업종지수) 상위 N개

# --- 주요 ETF 테마/코드 리스트 (유연 확장 가능) ---
MAJOR_ETF_LIST = [
    {"theme": "2차전지", "name": "KODEX 2차전지산업", "code": "305720"},
    {"theme": "AI/반도체", "name": "KODEX AI반도체산업", "code": "473460"},
    {"theme": "로봇", "name": "KODEX 로봇", "code": "409820"},
    {"theme": "인터넷/플랫폼", "name": "TIGER 인터넷", "code": "139260"},
    {"theme": "엔터/콘텐츠", "name": "TIGER K-콘텐츠", "code": "433700"},
    {"theme": "게임", "name": "TIGER 게임플랫폼", "code": "410470"},
    {"theme": "바이오/헬스케어", "name": "KODEX 바이오", "code": "266370"},
    {"theme": "전기차/친환경차", "name": "TIGER 전기차&친환경차", "code": "447460"},
    {"theme": "신재생/수소", "name": "KODEX 수소경제", "code": "397410"},
    {"theme": "리튬/소재", "name": "TIGER 리튬&2차전지소재", "code": "456440"},
    {"theme": "BBIG/4차산업", "name": "TIGER KRX BBIG K-뉴딜", "code": "367760"},
    {"theme": "ESG", "name": "KODEX ESG리더스", "code": "322130"},
    {"theme": "5G/통신", "name": "TIGER 5G통신", "code": "367740"},
    {"theme": "철강/소재", "name": "TIGER 철강소재", "code": "131390"},
    {"theme": "유통/소비재", "name": "KODEX 유통", "code": "123310"},
    {"theme": "건설/인프라", "name": "KODEX 건설", "code": "266360"},
    {"theme": "운송/해운", "name": "TIGER KRX 운송", "code": "395160"},
    {"theme": "은행/금융", "name": "KODEX 은행", "code": "091170"},
    {"theme": "증권", "name": "TIGER 증권", "code": "157490"},
    {"theme": "미디어/광고", "name": "TIGER 미디어컨텐츠", "code": "407760"},
]

# 1. 시세(OHLCV) 수집 함수
def collect_ohlcv(ticker, start, end):
    df = stock.get_market_ohlcv_by_date(start, end, ticker)
    df.reset_index(inplace=True)
    return df

# 2. 투자자별 수급 수집 함수
def collect_investor_trading(ticker, start, end):
    df = stock.get_market_trading_value_by_date(start, end, ticker, detail=True)
    df.reset_index(inplace=True)
    return df

# 3. 업종지수 수집 함수
def collect_industry_index(industry_code, start, end):
    df = stock.get_index_ohlcv_by_date(start, end, industry_code)
    df.reset_index(inplace=True)
    return df

# --- 필터 기준/함수 분리 구조 추가 ---
# 각 조건별 필터 함수 정의

def filter_surge(df, threshold=SURGE_RATE):
    return df[df['등락률'] >= threshold][['ticker', '종목명']].values.tolist()

def filter_top_trading(df, top_n=TOP_TRADING_N):
    return df.nlargest(top_n, '거래대금')[['ticker', '종목명']].values.tolist()

def filter_rebound(df, top_n=REBOUND_TOP_N, rebound_rate=REBOUND_RATE, target_date=None):
    topN = df.nlargest(top_n, '거래대금')['ticker'].tolist()
    rebound = []
    for ticker in topN:
        try:
            hist = stock.get_market_ohlcv_by_date((datetime.strptime(target_date, '%Y%m%d') - timedelta(days=70)).strftime('%Y%m%d'), target_date, ticker)
            if len(hist) < 10:
                continue
            min_low = hist['저가'].min()
            today_close = hist.iloc[-1]['종가']
            rate = (today_close - min_low) / min_low * 100 if min_low > 0 else 0
            if rate >= rebound_rate:
                name = df[df['ticker'] == ticker]['종목명'].values[0]
                rebound.append([ticker, name])
        except Exception as e:
            continue
    return rebound

def filter_volume_spike_top_trading(df, target_date, top_n=TOP_TRADING_N, ratio=VOLUME_SPIKE_RATIO):
    top_tickers = df.nlargest(top_n, '거래대금')['ticker'].tolist()
    result = []
    for ticker in top_tickers:
        try:
            hist = stock.get_market_ohlcv_by_date(
                (datetime.strptime(target_date, '%Y%m%d') - timedelta(days=10)).strftime('%Y%m%d'),
                target_date, ticker
            )
            if len(hist) < 6:
                continue
            hist = hist.tail(6)
            today_vol = hist.iloc[-1]['거래대금']
            avg_vol = hist.iloc[:-1]['거래대금'].mean()
            ratio_val = today_vol / avg_vol if avg_vol > 0 else 0
            name = df[df['ticker'] == ticker]['종목명'].values[0]
            print(f"[디버그] {ticker} {name} | 오늘: {today_vol:,.0f} | 5일평균: {avg_vol:,.0f} | 비율: {ratio_val:.2f}")
            if avg_vol > 0 and ratio_val >= ratio:
                result.append([ticker, name])
        except Exception:
            continue
    return result

def filter_theme_top_etf(df, target_date, top_n=THEME_TOP_N):
    etf_list = stock.get_etf_ticker_list(target_date)
    etf_info = []
    for code in etf_list:
        try:
            ohlcv = stock.get_etf_ohlcv_by_date((datetime.strptime(target_date, '%Y%m%d') - timedelta(days=1)).strftime('%Y%m%d'), target_date, code)
            if len(ohlcv) < 2:
                continue
            today = ohlcv.iloc[-1]
            prev = ohlcv.iloc[-2]
            change = (today['종가'] - prev['종가']) / prev['종가'] * 100 if prev['종가'] > 0 else 0
            etf_info.append({'code': code, 'name': stock.get_etf_ticker_name(code), 'change': change, 'trading': today['거래대금']})
        except Exception:
            continue
    etf_info = sorted(etf_info, key=lambda x: (x['change'], x['trading']), reverse=True)[:top_n]
    result = []
    for etf in etf_info:
        try:
            comp = stock.get_index_portfolio_deposit_file(etf['code'], target_date)
            for ticker in comp:
                if ticker in df['ticker'].values:
                    name = df[df['ticker'] == ticker]['종목명'].values[0]
                    result.append([ticker, name, etf['name'], etf['change']])
        except Exception:
            continue
    return result

def filter_top5_etf(df, target_date, top_n=5):
    etf_info = []
    for item in MAJOR_ETF_LIST:
        code = item['code']
        name = item['name']
        try:
            ohlcv = stock.get_etf_ohlcv_by_date((datetime.strptime(target_date, '%Y%m%d') - timedelta(days=1)).strftime('%Y%m%d'), target_date, code)
            if len(ohlcv) < 2:
                continue
            today = ohlcv.iloc[-1]
            prev = ohlcv.iloc[-2]
            change = (today['종가'] - prev['종가']) / prev['종가'] * 100 if prev['종가'] > 0 else 0
            etf_info.append([code, name, change, today['거래대금']])
        except Exception:
            continue
    etf_info = sorted(etf_info, key=lambda x: (x[2], x[3]), reverse=True)[:top_n]
    return etf_info

def filter_major_etf(df, target_date):
    result = []
    for item in MAJOR_ETF_LIST:
        code = item['code']
        theme = item['theme']
        name = item['name']
        try:
            ohlcv = stock.get_etf_ohlcv_by_date((datetime.strptime(target_date, '%Y%m%d') - timedelta(days=1)).strftime('%Y%m%d'), target_date, code)
            if len(ohlcv) < 2:
                continue
            today = ohlcv.iloc[-1]
            prev = ohlcv.iloc[-2]
            change = (today['종가'] - prev['종가']) / prev['종가'] * 100 if prev['종가'] > 0 else 0
            result.append([theme, name, code, today['종가'], change, today['거래대금']])
        except Exception as e:
            print(f"[ERR] {theme} {name}({code}) 조회 실패: {e}")
            continue
    return result

# --- 수급주 필터 기능 완전 제외 (속도/실전성/pykrx 구조상 비효율로 인한 삭제) ---
# 기존 수급주 관련 함수/딕셔너리/출력 모두 삭제
# 조건별 필터 기준 dict (수시 변경/확장 가능)
FILTER_CONFIG = {
    '급등주': lambda df, date: filter_surge(df, threshold=SURGE_RATE),
    '거래대금상위': lambda df, date: filter_top_trading(df, top_n=TOP_TRADING_N),
    '저점반등주': lambda df, date: filter_rebound(df, top_n=REBOUND_TOP_N, rebound_rate=REBOUND_RATE, target_date=date),
    '거래대금폭증주': lambda df, date: filter_volume_spike_top_trading(df, date, top_n=TOP_TRADING_N, ratio=VOLUME_SPIKE_RATIO),
    'etf상승률상위5': lambda df, date: filter_top5_etf(df, date, top_n=5),
    '주요ETF': lambda df, date: filter_major_etf(df, date),
    # '테마강세주': lambda df, date: filter_theme_top_etf(df, date, top_n=THEME_TOP_N),  # 전체 자동실행 제외(비활성화)
}

# --- 수급주 필터 기능 제외 사유 ---
# 1. pykrx 구조상 종목별 반복 조회만 가능해 전체 시장 수급 데이터 일괄 추출이 매우 느림
# 2. 실전 자동화/운영시 속도 병목, 서버 부하, KRX 차단 위험 등 실효성 낮음
# 3. 실전에서는 거래대금/등락률/저점반등 등 빠른 필터만 우선 적용, 수급주는 별도 실험/분석에서만 활용 권장

ETF_DB_PATH = os.path.join(os.path.dirname(__file__), '../../db/etf_performance.db')

def save_etf_performance(date_str):
    conn = sqlite3.connect(ETF_DB_PATH)
    etf_rows = []
    for item in MAJOR_ETF_LIST:
        code = item['code']
        name = item['name']
        try:
            ohlcv = stock.get_etf_ohlcv_by_date((datetime.strptime(date_str, '%Y%m%d') - timedelta(days=1)).strftime('%Y%m%d'), date_str, code)
            if len(ohlcv) < 2:
                continue
            today = ohlcv.iloc[-1]
            prev = ohlcv.iloc[-2]
            change = (today['종가'] - prev['종가']) / prev['종가'] * 100 if prev['종가'] > 0 else 0
            etf_rows.append({
                'date': date_str,
                'etf_code': code,
                'etf_name': name,
                'change': change,
                '거래대금': today['거래대금']
            })
        except Exception:
            continue
    if etf_rows:
        df = pd.DataFrame(etf_rows)
        df.to_sql('etf_daily', conn, if_exists='append', index=False)
        print(f"[OK] etf_performance.db {len(df)} rows 저장 완료")
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', type=str, default=None, help='기준일자(YYYYMMDD), 미입력시 오늘 날짜')
    parser.add_argument('--filter', type=str, default=None, help='실행할 필터명(예: 급등주, 거래대금상위, 저점반등주, 거래대금폭증주, 테마강세주, etf상승률상위5, 주요ETF)')
    args = parser.parse_args()
    if args.date:
        target_date = args.date
    else:
        target_date = datetime.today().strftime('%Y%m%d')
    today_str = datetime.today().strftime('%Y%m%d')
    print(f"[INFO] 오늘 날짜: {today_str}")
    print(f"[INFO] 기준일(분석 대상): {target_date}")
    # ETF 성과 DB 저장
    save_etf_performance(target_date)
    start = (datetime.strptime(target_date, '%Y%m%d') - timedelta(days=70)).strftime('%Y%m%d')
    end = target_date
    db_path = os.path.join(os.path.dirname(__file__), '../../db/stock_filter1.db')
    conn = sqlite3.connect(db_path)
    ohlcv_df = stock.get_market_ohlcv_by_ticker(target_date, market='ALL')
    ohlcv_df = ohlcv_df.reset_index().rename(columns={'티커': 'ticker'})
    ohlcv_df['거래대금'] = ohlcv_df['종가'] * ohlcv_df['거래량']
    ticker_list = stock.get_market_ticker_list(target_date, market='ALL')
    ticker_name_map = {t: stock.get_market_ticker_name(t) for t in ticker_list}
    ohlcv_df['종목명'] = ohlcv_df['ticker'].map(ticker_name_map)
    candidates = {}
    if args.filter:
        if args.filter not in FILTER_CONFIG:
            print(f"[ERR] 지원하지 않는 필터명: {args.filter}")
            print(f"사용 가능 필터: {list(FILTER_CONFIG.keys())}")
            exit(1)
        tickers = FILTER_CONFIG[args.filter](ohlcv_df, target_date)
        candidates[args.filter] = tickers
        print(f"[{args.filter}] {len(tickers)}종: {tickers}")
    else:
        for tag, func in FILTER_CONFIG.items():
            tickers = func(ohlcv_df, target_date)
            candidates[tag] = tickers
            print(f"[{tag}] {len(tickers)}종: {tickers}")
    all_candidates = set()
    for v in candidates.values():
        all_candidates.update(tuple(x) for x in v)
    print(f"[통합 후보군] {len(all_candidates)}종: {list(all_candidates)}")
    # 후보군 DB 저장용 리스트
    candidates_db_rows = []
    for tag, tickers in candidates.items():
        for row in tickers:
            # ETF 등 종목이 아닌 row(길이 2가 아님)는 OHLCV 저장/DB 적재에서 제외
            if len(row) != 2:
                continue
            ticker, name = row[0], row[1]
            try:
                ohlcv = collect_ohlcv(ticker, start, end)
                ohlcv.to_csv(os.path.join(RAW_DIR, f'ohlcv_{ticker}.csv'), index=False)
                ohlcv_db = ohlcv.rename(columns={
                    '날짜': 'date', '시가': 'open', '고가': 'high', '저가': 'low', '종가': 'close', '거래량': 'volume', '등락률': 'change_rate'
                })
                ohlcv_db['ticker'] = ticker
                ohlcv_db = ohlcv_db[['ticker', 'date', 'open', 'high', 'low', 'close', 'volume', 'change_rate']]
                ohlcv_db.to_sql('ohlcv_daily', conn, if_exists='append', index=False)
                # 후보군 DB 저장용 row 추가
                candidates_db_rows.append({
                    'date': target_date,
                    'ticker': ticker,
                    'name': name,
                    'filter_tag': tag,
                    '거래대금': ohlcv.iloc[-1]['거래량'] * ohlcv.iloc[-1]['종가'] if len(ohlcv) > 0 else 0,
                    '등락률': ohlcv.iloc[-1]['등락률'] if len(ohlcv) > 0 and '등락률' in ohlcv.columns else 0
                })
                print(f"[OK] OHLCV 저장: {ticker} {name}")
            except Exception as e:
                print(f"[ERR] {ticker} {name} OHLCV 저장 실패: {e}")
    # 후보군 DB 저장
    if candidates_db_rows:
        candidates_df = pd.DataFrame(candidates_db_rows)
        candidates_df.to_sql('candidates_daily', conn, if_exists='append', index=False)
        print(f"[OK] candidates_daily {len(candidates_df)} rows 저장 완료")
        # === wide format CSV 저장 ===
        # 피벗: ticker, name, 거래대금, 등락률, 각 필터별 1/0 컬럼
        wide = candidates_df.copy()
        wide['value'] = 1
        wide_pivot = wide.pivot_table(index=['ticker','name','거래대금','등락률'], columns='filter_tag', values='value', fill_value=0).reset_index()
        # 컬럼 순서 정렬(필터별 컬럼은 기존 FILTER_CONFIG 순서대로)
        filter_cols = [k for k in FILTER_CONFIG.keys() if k in wide_pivot.columns]
        cols = ['ticker','name','거래대금','등락률'] + filter_cols
        wide_pivot = wide_pivot.reindex(columns=cols)
        csv_dir = os.path.join(os.path.dirname(__file__), '../../data/processed')
        os.makedirs(csv_dir, exist_ok=True)
        csv_path = os.path.join(csv_dir, f'candidates_{target_date}.csv')
        wide_pivot.to_csv(csv_path, index=False)
        print(f"[OK] {csv_path} 저장 완료 ({len(wide_pivot)} rows)")
    # 사용법 예시:
    # python collect_krx.py --filter 급등주
    # python collect_krx.py --filter 테마강세주 --date 20250605
    # python collect_krx.py --filter 주요ETF --date 20250607
    conn.close()

# 주석: 실전 운영시 ticker/industry_code/기간 등 파라미터화, 반복/병렬 수집 확장 가능 

# 사용법 예시:
# python collect_krx.py --date 20240611
# python collect_krx.py (오늘 날짜 기준) 