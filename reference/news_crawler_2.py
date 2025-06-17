import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import urllib.parse
import re
from datetime import datetime, timedelta
import sqlite3

class SeleniumNewsCrawler:
    def __init__(self, headless=True):
        from selenium import webdriver
        from selenium.webdriver.support.ui import WebDriverWait
        chrome_options = Options()
        # headless 모드 항상 강제 적용 (외부 인자 무시)
        chrome_options.headless = True  # 변경: 항상 headless
        chrome_options.add_argument('--window-size=1280,1024')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)

    def close(self):
        self.driver.quit()

    @staticmethod
    def _parse_news_date(date_str, today):
        # today: datetime.date
        if not date_str:
            return None
        date_str = date_str.strip()
        if re.search(r'(\d+)시간 전|(\d+)분 전', date_str):
            return today
        if '1일 전' in date_str:
            return today - timedelta(days=1)
        if '2일 전' in date_str:
            return today - timedelta(days=2)
        # YYYY.MM.DD, YYYY-MM-DD 등 날짜 포맷
        for fmt in ['%Y.%m.%d', '%Y-%m-%d', '%Y/%m/%d']:
            try:
                return datetime.strptime(date_str, fmt).date()
            except Exception:
                continue
        return None

    def filter_recent_news(self, articles, max_days=2):
        today = datetime.now().date()
        filtered = []
        for art in articles:
            d = self._parse_news_date(art.get('date', ''), today)
            if d is not None and (today - d).days <= max_days:
                filtered.append((d, art))
        # 당일 뉴스가 1개 이상 있으면 당일 뉴스만, 없으면 2일 이내 뉴스만
        today_news = [a for d, a in filtered if d == today]
        if today_news:
            return today_news
        return [a for d, a in filtered]

    def crawl_naver_news(self, query, max_articles=10, max_retry=3, base_sleep=1):
        """
        네이버 뉴스 크롤링: 재시도(최대 3회), 시도마다 대기시간 1초씩 증가
        """
        import time
        import urllib.parse
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        q = urllib.parse.quote_plus(query)
        url = f"https://search.naver.com/search.naver?where=news&query={q}"
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
                filtered = self.filter_recent_news(articles, max_days=2)
                return filtered[:max_articles]
            except Exception as e:
                with open('naver_news_debug.html', 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)
                print(f"[ERROR] 네이버 뉴스 {attempt+1}차 실패: {e}")
                time.sleep(base_sleep * (attempt + 1))
        print("[ERROR] 네이버 뉴스 최종 실패")
        return []

    def crawl_google_news(self, query, max_articles=10, max_retry=3, base_sleep=1):
        """
        구글 뉴스 크롤링: 재시도(최대 3회), 시도마다 대기시간 1초씩 증가
        """
        import time
        import urllib.parse
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        q = urllib.parse.quote_plus(query)
        url = f"https://www.google.com/search?q={q}&tbm=nws"
        for attempt in range(max_retry):
            self.driver.get(url)
            articles = []
            try:
                self.wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div.n0jPhd.ynAwRc.MBeuO.nDgy9d'))
                )
                headline_divs = self.driver.find_elements(By.CSS_SELECTOR, 'div.n0jPhd.ynAwRc.MBeuO.nDgy9d')
                for div in headline_divs[:max_articles*2]:
                    parent_a = div.find_element(By.XPATH, './ancestor::a[1]')
                    link = parent_a.get_attribute('href')
                    title = div.text.strip()
                    try:
                        summary_div = parent_a.find_element(By.CSS_SELECTOR, 'div.GI74Re.nDgy9d')
                        summary = summary_div.text.strip()
                    except Exception:
                        summary = ''
                    try:
                        date_div = parent_a.find_element(By.CSS_SELECTOR, 'div.OSrXXb.rbYSKb.LfVVr > span')
                        date = date_div.text.strip()
                    except Exception:
                        date = ''
                    articles.append({
                        'title': title,
                        'link': link,
                        'summary': summary,
                        'date': date
                    })
                filtered = self.filter_recent_news(articles, max_days=2)
                return filtered[:max_articles]
            except Exception as e:
                with open('google_news_debug.html', 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)
                print(f"[ERROR] 구글 뉴스 {attempt+1}차 실패: {e}")
                time.sleep(base_sleep * (attempt + 1))
        print("[ERROR] 구글 뉴스 최종 실패")
        return []

def save_news_to_db(news_list, ticker, date, db_path='db/stock_filter2.db'):
    conn = sqlite3.connect(db_path)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS stock_news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT,
            url TEXT
        )
    ''')
    for news in news_list:
        conn.execute('''
            INSERT INTO stock_news (date, ticker, title, summary, url)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            date,
            ticker,
            news.get('title', ''),
            news.get('summary', ''),
            news.get('link', '')
        ))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    import sys
    from datetime import datetime
    query = sys.argv[1] if len(sys.argv) > 1 else '삼성전자'
    ticker = sys.argv[2] if len(sys.argv) > 2 else ''
    date = sys.argv[3] if len(sys.argv) > 3 else datetime.today().strftime('%Y%m%d')
    crawler = SeleniumNewsCrawler(headless=True)
    print(f"[네이버 뉴스] {query}")
    naver_results = crawler.crawl_naver_news(query, max_articles=10)
    for art in naver_results:
        print(art)
    save_news_to_db(naver_results, ticker, date)
    # 네이버에서 10개 미만이면 구글 뉴스 백업 크롤링
    if len(naver_results) < 10:
        print(f"\n[구글 뉴스] {query}")
        google_results = crawler.crawl_google_news(query, max_articles=10-len(naver_results))
        for art in google_results:
            print(art)
        save_news_to_db(google_results, ticker, date)
    crawler.close()
# 주요 변경점: 구글뉴스 주소/쿼리 인코딩 반영, selector 오류시 HTML 저장, 네이버/구글 뉴스 모두 robust하게 개선 