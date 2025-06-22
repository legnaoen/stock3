# 네이버 금융 테마별 리스트/소속 종목 크롤링 및 DB 저장 모듈
# - 목적: 테마별 리스트 및 소속 종목 크롤링, DB 저장
# - 사용법: get_theme_list, get_stocks_by_theme, upsert_themes 등 함수 활용
import os
import sys
import time
import sqlite3
from datetime import datetime
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

def get_today():
    return datetime.today().strftime('%Y-%m-%d')

# venv 활성화 체크
if os.name != 'nt':
    if not hasattr(sys, 'base_prefix') or sys.prefix == sys.base_prefix:
        print("[ERROR] 반드시 venv(가상환경)에서 실행해야 합니다.")
        exit(1)

BASE_URL = "https://finance.naver.com"
THEME_URL = f"{BASE_URL}/sise/theme.naver"
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../db/stock_master.db'))
SCHEMA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../db/schema_theme_industry.sql'))

# DB 초기화(테마/매핑 테이블)
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
            conn.executescript(f.read())

def get_driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=options)
    return driver

def get_theme_list(driver):
    driver.get(THEME_URL)
    time.sleep(1)
    soup = BeautifulSoup(driver.page_source, 'lxml')
    theme_list = []
    for a in soup.select('table.type_1 a[href*="sise_group_detail.naver?type=theme"]'):
        name = a.text.strip()
        href = a['href']
        if 'no=' in href:
            code = href.split('no=')[1].split('&')[0]
            theme_list.append({
                'theme_code': code,
                'theme_name': name,
                'detail_url': urljoin(BASE_URL, href)
            })
    return theme_list

def get_stocks_by_theme(driver, detail_url):
    driver.get(detail_url)
    time.sleep(1)
    soup = BeautifulSoup(driver.page_source, 'lxml')
    stocks = []
    for a in soup.select('table.type_5 a[href*="/item/main.naver?code="]'):
        name = a.text.strip()
        href = a['href']
        if 'code=' in href:
            code = href.split('code=')[1][:6]
            stocks.append({'stock_code': code, 'stock_name': name})
    return stocks

def upsert_themes(theme_list):
    print("[LOG] DB에 저장될 테마 리스트:")
    with sqlite3.connect(DB_PATH) as conn:
        # 기존 테마 목록 가져오기
        cur = conn.cursor()
        cur.execute("SELECT theme_id, theme_name FROM theme_master")
        existing_themes = {row[0]: row[1] for row in cur.fetchall()}
        
        # 새로운 테마만 추가/업데이트
        for th in theme_list:
            theme_id = th['theme_code']
            if theme_id not in existing_themes:
                print(f"  - [신규] {th['theme_code']}: {th['theme_name']}")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO theme_master 
                    (theme_id, theme_name, category, updated_at)
                    VALUES (?, ?, 'THEME', CURRENT_TIMESTAMP)
                    """,
                    (theme_id, th['theme_name'])
                )
            elif existing_themes[theme_id] != th['theme_name']:
                print(f"  - [수정] {th['theme_code']}: {th['theme_name']}")
                conn.execute(
                    """
                    UPDATE theme_master 
                    SET theme_name = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE theme_id = ?
                    """,
                    (th['theme_name'], theme_id)
                )
        conn.commit()

def get_theme_id_by_code(theme_code):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT theme_id FROM theme_master WHERE theme_id=?", (theme_code,))
        row = cur.fetchone()
        return row[0] if row else None

def upsert_stock_themes(theme_code, stocks):
    theme_id = get_theme_id_by_code(theme_code)
    if not theme_id:
        print(f"[WARN] theme_id {theme_code} not found in theme_master table.")
        return
        
    print(f"[LOG] DB에 저장될 종목-테마 매핑 (theme_id: {theme_id}):")
    with sqlite3.connect(DB_PATH) as conn:
        # 기존 매핑 가져오기
        cur = conn.cursor()
        cur.execute("SELECT stock_code FROM theme_stock_mapping WHERE theme_id=?", (theme_id,))
        existing_stocks = {row[0] for row in cur.fetchall()}
        
        # 새로운 종목만 추가
        for s in stocks:
            stock_code = s['stock_code']
            if stock_code not in existing_stocks:
                print(f"  - [신규] {stock_code} <-> {theme_id}")
                conn.execute(
                    """
                    INSERT INTO theme_stock_mapping 
                    (theme_id, stock_code, created_at, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (theme_id, stock_code)
                )
            
        # 더 이상 존재하지 않는 매핑 삭제
        current_stocks = {s['stock_code'] for s in stocks}
        for old_stock in existing_stocks - current_stocks:
            print(f"  - [삭제] {old_stock} <-> {theme_id}")
            conn.execute(
                "DELETE FROM theme_stock_mapping WHERE theme_id=? AND stock_code=?",
                (theme_id, old_stock)
            )
        conn.commit()

def main():
    print("[INFO] DB 초기화 및 테이블 생성...")
    init_db()
    driver = get_driver()
    theme_stock_count = {}  # 테마별 종목수 집계용
    try:
        print("[INFO] 테마 리스트 수집 중...")
        theme_list = get_theme_list(driver)
        print(f"[INFO] 테마 수(첫 페이지): {len(theme_list)}")
        upsert_themes(theme_list)
        for th in theme_list:
            print(f"[INFO] 테마: {th['theme_name']} ({th['theme_code']}) 종목 수집 중...")
            stocks = get_stocks_by_theme(driver, th['detail_url'])
            print(f"  - 종목 수: {len(stocks)}")
            upsert_stock_themes(th['theme_code'], stocks)
            theme_stock_count[th['theme_name']] = len(stocks)
            time.sleep(0.5)
        print("[SUCCESS] 모든 테마-종목 매핑 저장 완료.")
    finally:
        print(f"[RESULT] 전체 테마 수(첫 페이지): {len(theme_stock_count)}")
        print("[RESULT] 테마별 종목 수:")
        for k, v in theme_stock_count.items():
            print(f"  - {k}: {v}")
        driver.quit()

if __name__ == "__main__":
    main()
