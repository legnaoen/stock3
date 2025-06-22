import os
import sys
import time
import sqlite3
from datetime import datetime
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

# venv 활성화 체크
if os.name != 'nt':
    if not hasattr(sys, 'base_prefix') or sys.prefix == sys.base_prefix:
        print("[ERROR] 반드시 venv(가상환경)에서 실행해야 합니다.")
        exit(1)

# 네이버 금융 업종별 리스트/소속 종목 크롤링 및 DB 저장 모듈
# - 목적: 업종별 리스트 및 소속 종목 크롤링, DB 저장
# - 사용법: get_industry_list, get_stocks_by_industry, upsert_industries 등 함수 활용

BASE_URL = "https://finance.naver.com"
INDUSTRY_URL = f"{BASE_URL}/sise/sise_group.naver?type=upjong"
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../db/stock_master.db'))
SCHEMA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../db/schema_theme_industry.sql'))

# DB 초기화(업종/매핑 테이블)
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

def get_industry_list(driver):
    driver.get(INDUSTRY_URL)
    time.sleep(1)
    soup = BeautifulSoup(driver.page_source, 'lxml')
    industry_list = []
    for a in soup.select('table.type_1 a[href*="sise_group_detail.naver"]'):
        name = a.text.strip()
        href = a['href']
        # 업종코드는 쿼리스트링에서 추출
        if 'no=' in href:
            code = href.split('no=')[1].split('&')[0]
            industry_list.append({
                'industry_code': code,
                'industry_name': name,
                'detail_url': urljoin(BASE_URL, href)
            })
    return industry_list

def get_stocks_by_industry(driver, detail_url):
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

def upsert_industries(industry_list):
    print("[LOG] DB에 저장될 업종 리스트:")
    with sqlite3.connect(DB_PATH) as conn:
        # 기존 업종 목록 가져오기
        cur = conn.cursor()
        cur.execute("SELECT industry_code, industry_name FROM industry_master")
        existing_industries = {row[0]: row[1] for row in cur.fetchall()}
        
        # 새로운 업종만 추가/업데이트
        for ind in industry_list:
            industry_code = ind['industry_code']
            if industry_code not in existing_industries:
                print(f"  - [신규] {industry_code}: {ind['industry_name']}")
                conn.execute(
                    """
                    INSERT INTO industry_master 
                    (industry_code, industry_name, level, updated_at)
                    VALUES (?, ?, 3, CURRENT_TIMESTAMP)
                    """,
                    (industry_code, ind['industry_name'])
                )
            elif existing_industries[industry_code] != ind['industry_name']:
                print(f"  - [수정] {industry_code}: {ind['industry_name']}")
                conn.execute(
                    """
                    UPDATE industry_master 
                    SET industry_name = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE industry_code = ?
                    """,
                    (ind['industry_name'], industry_code)
                )
        conn.commit()

def get_industry_id_by_code(industry_code):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT industry_id FROM industry_master WHERE industry_code=?", (industry_code,))
        row = cur.fetchone()
        return row[0] if row else None

def upsert_stock_industries(industry_code, stocks):
    industry_id = get_industry_id_by_code(industry_code)
    if not industry_id:
        print(f"[WARN] industry_code {industry_code} not found in industry_master table.")
        return
        
    print(f"[LOG] DB에 저장될 종목-업종 매핑 (industry_id: {industry_id}):")
    with sqlite3.connect(DB_PATH) as conn:
        # 기존 매핑 가져오기
        cur = conn.cursor()
        cur.execute("SELECT stock_code FROM industry_stock_mapping WHERE industry_id=?", (industry_id,))
        existing_stocks = {row[0] for row in cur.fetchall()}
        
        # 새로운 종목만 추가
        for s in stocks:
            stock_code = s['stock_code']
            if stock_code not in existing_stocks:
                print(f"  - [신규] {stock_code} <-> {industry_id}")
                conn.execute(
                    """
                    INSERT INTO industry_stock_mapping 
                    (industry_id, stock_code, created_at, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (industry_id, stock_code)
                )
            
        # 더 이상 존재하지 않는 매핑 삭제
        current_stocks = {s['stock_code'] for s in stocks}
        for old_stock in existing_stocks - current_stocks:
            print(f"  - [삭제] {old_stock} <-> {industry_id}")
            conn.execute(
                "DELETE FROM industry_stock_mapping WHERE industry_id=? AND stock_code=?",
                (industry_id, old_stock)
            )
        conn.commit()

def main():
    print("[INFO] DB 초기화 및 테이블 생성...")
    init_db()
    driver = get_driver()
    industry_stock_count = {}  # 업종별 종목수 집계용
    try:
        print("[INFO] 업종 리스트 수집 중...")
        industry_list = get_industry_list(driver)
        print(f"[INFO] 업종 수: {len(industry_list)}")
        upsert_industries(industry_list)
        for ind in industry_list:
            print(f"[INFO] 업종: {ind['industry_name']} ({ind['industry_code']}) 종목 수집 중...")
            stocks = get_stocks_by_industry(driver, ind['detail_url'])
            print(f"  - 종목 수: {len(stocks)}")
            upsert_stock_industries(ind['industry_code'], stocks)
            industry_stock_count[ind['industry_name']] = len(stocks)
            time.sleep(0.5)
        print("[SUCCESS] 모든 업종-종목 매핑 저장 완료.")
        print(f"[RESULT] 전체 업종 수: {len(industry_list)}")
        print("[RESULT] 업종별 종목 수:")
        for k, v in industry_stock_count.items():
            print(f"  - {k}: {v}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main() 