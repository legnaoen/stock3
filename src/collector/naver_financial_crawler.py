import os
import sys
import sqlite3
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from typing import Dict, Optional, Tuple, List
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.utils.logger import setup_logger

logger = setup_logger()

class NaverFinancialCrawler:
    def __init__(self, db_path: str = "db/stock_master.db"):
        self.db_path = db_path
        self.base_url = "https://finance.naver.com/item/main.naver"
        
    def _get_connection(self):
        """SQLite DB 연결을 반환합니다."""
        return sqlite3.connect(self.db_path)
        
    def _check_needs_update(self, ticker: str) -> bool:
        """주어진 종목의 업데이트 필요 여부를 확인합니다.
        
        Args:
            ticker (str): 종목코드
            
        Returns:
            bool: 업데이트 필요 여부
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # financial_info 테이블에서 최근 업데이트 날짜 확인
                cursor.execute("""
                    SELECT updated_at FROM financial_info 
                    WHERE ticker = ? 
                    ORDER BY updated_at DESC 
                    LIMIT 1
                """, (ticker,))
                
                result = cursor.fetchone()
                
                if not result:
                    return True
                    
                last_update = datetime.strptime(result[0], '%Y-%m-%d')
                days_since_update = (datetime.now() - last_update).days
                
                return days_since_update >= 30  # 30일 이상 지났으면 업데이트 필요
                
        except Exception as e:
            logger.error(f"Error checking update status: {str(e)}")
            return True
        
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
            
    def _parse_number(self, value) -> Optional[float]:
        """숫자 형식의 문자열을 파싱합니다."""
        if pd.isna(value) or value == '-':
            return None
        if isinstance(value, (int, float)):
            return float(value)
        try:
            # 쉼표 제거 후 숫자로 변환
            return float(str(value).replace(',', ''))
        except (ValueError, TypeError):
            return None

    def _get_financial_info(self, ticker: str) -> List[Dict]:
        """네이버 금융에서 재무정보를 크롤링합니다.
        
        Args:
            ticker (str): 종목코드
            
        Returns:
            List[Dict]: 재무정보 리스트
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
                return []

            logger.info(f"\nFinancial table:\n{financial_df.to_string()}")
            
            # 결과를 저장할 리스트
            results = []
            
            # 컬럼 정보 분석
            annual_columns = []
            quarterly_columns = []
            
            # 연간/분기 데이터 구분
            for col in financial_df.columns:
                if not isinstance(col, tuple) or len(col) < 2:
                    continue
                    
                section_type = col[0]  # '최근 연간 실적' or '최근 분기 실적'
                period_info = col[1]  # '2024.12' or '2025.12(E)'
                
                if not period_info or period_info == '주요재무정보':
                    continue
                    
                match = re.match(r'(\d{4})\.(\d{2})(?:\(E\))?', period_info)
                if not match:
                    continue
                    
                if '연간' in section_type:
                    annual_columns.append(col)
                elif '분기' in section_type:
                    quarterly_columns.append(col)
            
            if not annual_columns:
                logger.warning("Could not find annual data section")
                return []
                
            # 데이터 추출 함수
            def extract_data(col, is_quarterly: bool):
                period_info = col[1]  # '2024.12' or '2025.12(E)'
                match = re.match(r'(\d{4})\.(\d{2})(?:\(E\))?', period_info)
                if not match:
                    return None
                    
                year = match.group(1)
                month = match.group(2)
                is_estimate = '(E)' in period_info
                period = 'Q' if is_quarterly else 'Y'
                
                data = {
                    'ticker': ticker,
                    'year': year,
                    'period': period,
                    'is_estimate': is_estimate,
                    'updated_at': datetime.now().strftime('%Y-%m-%d')
                }
                
                # 각 지표 추출
                metrics = {
                    '매출액': ('revenue', self._parse_number),
                    '영업이익': ('operating_profit', self._parse_number),
                    '당기순이익': ('net_profit', self._parse_number),
                    '영업이익률': ('operating_margin', self._parse_number),
                    '순이익률': ('net_margin', self._parse_number),
                    'ROE(지배주주)': ('roe', self._parse_number),
                    '부채비율': ('debt_ratio', self._parse_number),
                    '당좌비율': ('quick_ratio', self._parse_number),
                    '유보율': ('reserve_ratio', self._parse_number),
                    'EPS(원)': ('eps', self._parse_number),
                    'PER(배)': ('per', self._parse_number),
                    'BPS(원)': ('bps', self._parse_number),
                    'PBR(배)': ('pbr', self._parse_number),
                    '주당배당금(원)': ('cash_dividend', self._parse_number),
                    '시가배당률(%)': ('dividend_yield', self._parse_number),
                    '배당성향(%)': ('dividend_payout', self._parse_number)
                }
                
                for row_name, (col_name, parser) in metrics.items():
                    try:
                        value = financial_df.loc[financial_df.iloc[:, 0] == row_name, col].iloc[0]
                        parsed_value = parser(value)
                        data[col_name] = parsed_value
                        if parsed_value is not None:
                            logger.info(f"Found {col_name} ({period}): {parsed_value}")
                    except (IndexError, KeyError):
                        data[col_name] = None
                
                return data
            
            # 연간 데이터 추출
            for col in annual_columns:
                data = extract_data(col, False)
                if data:
                    results.append(data)
                    
            # 분기 데이터 추출
            for col in quarterly_columns:
                data = extract_data(col, True)
                if data:
                    results.append(data)
                
            return results
            
        except Exception as e:
            logger.error(f"Error getting financial info for {ticker}: {str(e)}")
            return []

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
            
    def _save_financial_info(self, data_list: List[Dict]) -> bool:
        """재무정보를 DB에 저장합니다."""
        if not data_list:
            return False
            
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            for data in data_list:
                columns = ', '.join(data.keys())
                placeholders = ', '.join(['?' for _ in data])
                values = tuple(data.values())
                
                query = f"""
                INSERT OR REPLACE INTO financial_info ({columns})
                VALUES ({placeholders})
                """
                
                cursor.execute(query, values)
            
            conn.commit()
            logger.info(f"Successfully saved financial info")
            return True
            
        except Exception as e:
            logger.error(f"Error saving financial info: {str(e)}")
            return False
        finally:
            if conn:
                conn.close()

    def collect_financial_data(self, tickers: List[str]) -> bool:
        """주어진 종목들의 재무정보를 수집합니다."""
        try:
            for ticker in tickers:
                # 재무정보 수집
                financial_data = self._get_financial_info(ticker)
                if financial_data:
                    self._save_financial_info(financial_data)
                    
            return True
        except Exception as e:
            logger.error(f"Error processing {ticker}: {str(e)}")
            return False

# 테스트 실행
if __name__ == "__main__":
    crawler = NaverFinancialCrawler()
    test_tickers = ["005930", "000660"]  # 삼성전자, SK하이닉스
    crawler.collect_financial_data(test_tickers) 