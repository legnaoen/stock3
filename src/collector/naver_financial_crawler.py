import os
import sys
import sqlite3
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from typing import Dict, Optional, Tuple
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.collector.dart_collector import DartCollector
from src.utils.logger import setup_logger

logger = setup_logger()

class NaverFinancialCrawler(DartCollector):
    def __init__(self, db_path: str = "db/stock_master.db"):
        super().__init__(db_path)
        self.base_url = "https://finance.naver.com/item/main.naver"
        
    def _get_company_info(self, ticker: str) -> Optional[Dict]:
        """네이버 금융에서 기업개요 정보를 크롤링합니다.
        
        Args:
            ticker (str): 종목코드
            
        Returns:
            Optional[Dict]: 기업개요 정보
        """
        try:
            url = f"{self.base_url}?code={ticker}"
            response = requests.get(url)
            response.encoding = 'euc-kr'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 기업개요 섹션 찾기
            company_info_div = soup.find('div', {'class': 'summary_info'})
            if not company_info_div:
                logger.warning(f"No company info found for {ticker}")
                return None
                
            description = company_info_div.get_text(strip=True)
            
            return {
                'ticker': ticker,
                'description': description,
                'updated_at': datetime.now().strftime('%Y-%m-%d')
            }
            
        except Exception as e:
            logger.error(f"Error fetching company info for {ticker}: {str(e)}")
            return None
            
    def _get_financial_info(self, ticker: str) -> Optional[Dict]:
        """네이버 금융에서 재무정보를 크롤링합니다.
        
        Args:
            ticker (str): 종목코드
            
        Returns:
            Optional[Dict]: 재무정보
        """
        try:
            url = f"{self.base_url}?code={ticker}"
            tables = pd.read_html(url, encoding='euc-kr')
            
            # 연간 재무정보 테이블 찾기
            financial_df = None
            for table in tables:
                if '주요재무정보' in str(table):
                    financial_df = table
                    break
                    
            if financial_df is None:
                logger.warning(f"No financial info found for {ticker}")
                return None
                
            # 최신 연도의 데이터 추출
            latest_year = str(financial_df.columns[1])  # 첫 번째 연도 컬럼
            
            # 연도 문자열에서 실제 연도만 추출 (예: '2022.12')
            year_match = re.search(r'(\d{4})\.?(\d{2})?', latest_year)
            if not year_match:
                logger.warning(f"Could not parse year from {latest_year}")
                return None
            year = year_match.group(1)  # YYYY 형식의 연도만 사용
            
            def parse_number(value):
                if pd.isna(value) or value == '-':
                    return 0
                if isinstance(value, (int, float)):
                    return float(value)
                # 문자열에서 쉼표 제거하고 숫자로 변환
                try:
                    return float(str(value).replace(',', ''))
                except:
                    return 0
            
            # 재무 데이터 찾기
            revenue = 0
            operating_profit = 0
            net_income = 0
            
            # DataFrame을 순회하면서 필요한 행 찾기
            for idx, row in financial_df.iterrows():
                if '매출액' in str(row.iloc[0]):
                    revenue = parse_number(row.iloc[1])  # 첫 번째 데이터 컬럼
                elif '영업이익' in str(row.iloc[0]):
                    operating_profit = parse_number(row.iloc[1])
                elif '당기순이익' in str(row.iloc[0]):
                    net_income = parse_number(row.iloc[1])
            
            logger.info(f"Extracted financial data for {ticker}: revenue={revenue}, op_profit={operating_profit}, net_income={net_income}")
            
            return {
                'ticker': ticker,
                'year': year,
                'revenue': revenue,
                'operating_profit': operating_profit,
                'net_income': net_income,
                'updated_at': datetime.now().strftime('%Y-%m-%d')
            }
            
        except Exception as e:
            logger.error(f"Error fetching financial info for {ticker}: {str(e)}")
            return None
            
    def _save_company_info(self, info: Dict) -> bool:
        """기업개요 정보를 DB에 저장합니다.
        
        Args:
            info (Dict): 저장할 기업개요 정보
            
        Returns:
            bool: 저장 성공 여부
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO company_info 
                    (ticker, description, updated_at)
                    VALUES (?, ?, ?)
                """, (info['ticker'], info['description'], info['updated_at']))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error saving company info: {str(e)}")
            return False
            
    def _save_financial_info(self, info: Dict) -> bool:
        """재무정보를 DB에 저장합니다.
        
        Args:
            info (Dict): 저장할 재무정보
            
        Returns:
            bool: 저장 성공 여부
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO financial_info 
                    (ticker, year, revenue, operating_profit, net_income, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    info['ticker'], 
                    info['year'],
                    info['revenue'],
                    info['operating_profit'],
                    info['net_income'],
                    info['updated_at']
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error saving financial info: {str(e)}")
            return False
            
    def collect_financial_data(self, tickers: list) -> None:
        """여러 종목의 기업개요와 재무정보를 수집합니다.
        
        Args:
            tickers (list): 종목코드 리스트
        """
        for ticker in tickers:
            try:
                if not self._check_needs_update(ticker):
                    logger.info(f"Skipping {ticker} - already updated within 30 days")
                    continue
                
                # 기업개요 수집 및 저장
                company_info = self._get_company_info(ticker)
                if company_info:
                    if self._save_company_info(company_info):
                        logger.info(f"Successfully saved company info for {ticker}")
                    else:
                        logger.error(f"Failed to save company info for {ticker}")
                
                # 재무정보 수집 및 저장
                financial_info = self._get_financial_info(ticker)
                if financial_info:
                    if self._save_financial_info(financial_info):
                        logger.info(f"Successfully saved financial info for {ticker}")
                        self._update_last_update_date(ticker)
                    else:
                        logger.error(f"Failed to save financial info for {ticker}")
                
                # 크롤링 간격 조절
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error processing {ticker}: {str(e)}")
                continue

# 테스트 실행
if __name__ == "__main__":
    crawler = NaverFinancialCrawler()
    test_tickers = ["005930", "000660"]  # 삼성전자, SK하이닉스
    crawler.collect_financial_data(test_tickers) 