import time
import sqlite3
import re
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

DB_PATH = 'db/stock_master.db'

class NaverNewsCrawler:
    def __init__(self, headless=True):
        chrome_options = Options()
        chrome_options.headless = headless
        chrome_options.add_argument('--window-size=1280,1024')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)

    def close(self):
        self.driver.quit()

    def _parse_news_date(self, date_str, today):
        if not date_str:
            return None
        date_str = date_str.strip()
        if re.search(r'(\d+)시간 전|(\d+)분 전', date_str):
            return today
        if '1일 전' in date_str:
            return today - timedelta(days=1)
        if '2일 전' in date_str:
            return today - timedelta(days=2)
        for fmt in ['%Y.%m.%d', '%Y-%m-%d', '%Y/%m/%d']:
            try:
                return datetime.strptime(date_str, fmt).date()
            except Exception:
                continue
        return None

    def crawl_naver_news(self, query, max_articles=10, max_retry=3, base_sleep=1):
        import urllib.parse
        q = urllib.parse.quote_plus(query)
        url = f"https://search.naver.com/search.naver?where=news&query={q}"
        today = datetime.now().date()
        for attempt in range(max_retry):
            self.driver.get(url)
            articles = []
            try:
                self.wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'span.sds-comps-text.sds-comps-text-ellipsis-1.sds-comps-text-type-headline1'))
                )
                headline_spans = self.driver.find_elements(By.CSS_SELECTOR, 'span.sds-comps-text.sds-comps-text-ellipsis-1.sds-comps-text-type-headline1')
                for span in headline_spans[:max_articles*2]:
                    parent_a = span.find_element(By.XPATH, './ancestor::a[1]')
                    link = parent_a.get_attribute('href')
                    title = span.text.strip()
                    try:
                        summary_span = parent_a.find_element(By.CSS_SELECTOR, 'span.sds-comps-text.sds-comps-text-ellipsis-3.sds-comps-text-type-body1')
                        summary = summary_span.text.strip()
                    except Exception:
                        summary = ''
                    date = ''
                    for up in range(1, 4):
                        try:
                            ancestor_div = span.find_element(By.XPATH, f'./ancestor::div[{up}]')
                            time_spans = ancestor_div.find_elements(By.CSS_SELECTOR, 'span.sds-comps-text.sds-comps-text-type-body2.sds-comps-text-weight-sm')
                            for tspan in time_spans:
                                ttext = tspan.text.strip()
                                if re.search(r'(\d+)(시간|분|일) 전', ttext):
                                    date = ttext
                                    break
                            if date:
                                break
                        except Exception:
                            continue
                    articles.append({
                        'title': title,
                        'link': link,
                        'summary': summary,
                        'date': date
                    })
                # 날짜 파싱 및 최신순 정렬
                for art in articles:
                    art['parsed_date'] = self._parse_news_date(art.get('date', ''), today)
                articles = [a for a in articles if a['parsed_date'] is not None]
                articles.sort(key=lambda x: (x['parsed_date'], x['title']), reverse=True)
                return articles[:max_articles]
            except Exception as e:
                time.sleep(base_sleep * (attempt + 1))
        return []

def save_news_to_db(news_list, stock_code, date, db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS stock_news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            stock_code TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT,
            url TEXT,
            UNIQUE(date, stock_code, title, url)
        )
    ''')
    # 기존 뉴스 개수 확인
    cur = conn.cursor()
    cur.execute("SELECT id, title, url FROM stock_news WHERE date=? AND stock_code=? ORDER BY id DESC", (date, stock_code))
    existing = cur.fetchall()
    existing_set = set((row[1], row[2]) for row in existing)
    # 최신 뉴스만 5개 제한
    count = 0
    for news in news_list:
        if count >= 5:
            break
        key = (news.get('title', ''), news.get('link', ''))
        if key in existing_set:
            continue
        conn.execute('''
            INSERT OR IGNORE INTO stock_news (date, stock_code, title, summary, url)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            date,
            stock_code,
            news.get('title', ''),
            news.get('summary', ''),
            news.get('link', '')
        ))
        count += 1
    conn.commit()
    # 5개 초과시 오래된 뉴스 삭제
    cur.execute("SELECT id FROM stock_news WHERE date=? AND stock_code=? ORDER BY id DESC", (date, stock_code))
    ids = [row[0] for row in cur.fetchall()]
    if len(ids) > 5:
        for del_id in ids[5:]:
            conn.execute("DELETE FROM stock_news WHERE id=?", (del_id,))
        conn.commit()
    conn.close()

def crawl_naver_news_for_stock(stock_code, stock_name, date, db_path=DB_PATH):
    crawler = NaverNewsCrawler(headless=True)
    try:
        news_list = crawler.crawl_naver_news(stock_name, max_articles=10)
        save_news_to_db(news_list, stock_code, date, db_path)
        return len(news_list)
    finally:
        crawler.close()
