import os
import requests
import pandas as pd
from datetime import datetime
import xml.etree.ElementTree as ET
import zipfile
import sqlite3
import argparse
import re
import pdfplumber
import lxml.etree as ET

# DART API KEY는 환경변수 또는 config에서 불러옴
DART_API_KEY = '875e614da4a394d738bfbf2380048d87eefb6a8d'
DART_API_URL = 'https://opendart.fss.or.kr/api/'
CORPCODE_ZIP_PATH = os.path.join(os.path.dirname(__file__), '../../data/corpCode.zip')
CORPCODE_XML_PATH = os.path.join(os.path.dirname(__file__), '../../data/CORPCODE.xml')

# 항목별 탐색 옵션 (True/False)
FIN_OPTION = {
    "부채비율": True,
    "유동비율": False,
    "유보율": False,
    "현금흐름": False,
}

_corp_code_map = None

def download_and_extract_corp_code():
    url = f"{DART_API_URL}corpCode.xml"
    params = {'crtfc_key': DART_API_KEY}
    r = requests.get(url, params=params, stream=True, timeout=20)
    with open(CORPCODE_ZIP_PATH, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    with zipfile.ZipFile(CORPCODE_ZIP_PATH, 'r') as zip_ref:
        zip_ref.extractall(os.path.dirname(CORPCODE_ZIP_PATH))

def load_corp_code_map():
    global _corp_code_map
    if _corp_code_map is not None:
        return _corp_code_map
    if not os.path.exists(CORPCODE_XML_PATH):
        download_and_extract_corp_code()
    tree = ET.parse(CORPCODE_XML_PATH)
    root = tree.getroot()
    code_map = {}
    for el in root.findall('list'):
        ticker = el.findtext('stock_code')
        corp_code = el.findtext('corp_code')
        if ticker and corp_code:
            code_map[ticker.zfill(6)] = corp_code
    _corp_code_map = code_map
    return code_map

def get_corp_code(ticker):
    code_map = load_corp_code_map()
    return code_map.get(ticker.zfill(6), None)

# DART 재무정보 실전 파이프라인 공식 가이드 (SSOT)
#
# - TopN 종목 일괄 재무정보: fetch_dart_multi_financials(ticker_list, 기준일자)
#   * DART 다중계정 API(fnlttMultiAcnt) 기반, 연결/별도/분기 fallback, 주요 계정/비율 자동 추출
#   * 결과: {ticker: {계정명:값, ...}} dict, 부채비율/유동비율/ROE 등 포함
#   * DB 저장/후처리: 실전 파이프라인에서 바로 연동
#   * 예시:
#       top_tickers = ['005930','035420',...]
#       fin_data = fetch_dart_multi_financials(top_tickers, 기준일자='20240605')
#       for t, d in fin_data.items():
#           print(t, d)
#
# - fetch_dart_financials: 단일 종목/연도 fallback용(실전에서는 multi 함수 사용 권장)
#
# - 계정명/보고서/연결/별도/분기 fallback, None 처리, 실전 파이프라인 연동 최적화
#
# - SSOT: 본 파일/주석을 공식 표준으로 관리, 변경시 ssot.md/문서 동시 업데이트

# DART 재무제표 원본조회 API 호출
# https://opendart.fss.or.kr/guide/main.do?apiGrpCd=DS001

def fetch_dart_financials(ticker, 기준일자):
    corp_code = get_corp_code(ticker)
    if not corp_code:
        print(f"[DART] corp_code not found for ticker {ticker}")
        return None
    year = 기준일자[:4]
    reprt_code = '11011'  # 사업보고서(1분기:11013, 반기:11012, 3분기:11014)
    url = f"{DART_API_URL}fnlttSinglAcntAll.json"
    params = {
        'crtfc_key': DART_API_KEY,
        'corp_code': corp_code,
        'bsns_year': year,
        'reprt_code': reprt_code,
        'fs_div': 'CFS',
    }
    r = requests.get(url, params=params, timeout=10)
    data = r.json()
    status = data.get('status')
    message = data.get('message', '')
    if status != '0001' or 'list' not in data:
        print(f"[DART] {ticker} status={status} message={message}")
        return None
    df = pd.DataFrame(data['list'])
    # 주요 재무제표 항목 추출(account_nm 기준)
    key_map = {
        '자산총계': None, '부채총계': None, '자본총계': None, '유동자산': None, '유동부채': None,
        '매출액': None, '영업이익': None, '당기순이익': None, '자본금': None
    }
    for k in key_map.keys():
        val = df[df['account_nm'] == k]
        if not val.empty:
            try:
                key_map[k] = float(val.iloc[0]['thstrm_amount'].replace(',', ''))
            except Exception:
                key_map[k] = None
        else:
            key_map[k] = None
    # 주요 재무비율 계산
    부채비율 = (key_map['부채총계'] / key_map['자본총계'] * 100) if key_map['부채총계'] and key_map['자본총계'] else None
    유동비율 = (key_map['유동자산'] / key_map['유동부채'] * 100) if key_map['유동자산'] and key_map['유동부채'] else None
    ROE = (key_map['당기순이익'] / key_map['자본총계'] * 100) if key_map['당기순이익'] and key_map['자본총계'] else None
    result = key_map.copy()
    result['부채비율'] = 부채비율
    result['유동비율'] = 유동비율
    result['ROE'] = ROE
    return result

# --- [신규] DART 다중계정/다중종목/연결/별도/분기 fallback 지원 ---
def fetch_dart_multi_financials(ticker_list, 기준일자, reprt_code='11011', fs_divs=('CFS','OFS')):
    """
    - ticker_list: 종목코드 리스트(문자열)
    - 기준일자: YYYYMMDD
    - reprt_code: 11011(사업), 11012(반기), 11013(1Q), 11014(3Q)
    - fs_divs: ('CFS','OFS') 연결/별도 우선순위
    """
    # --- 계정명 매핑(실전 표기 변형 대응) ---
    account_map = {
        '자산총계': ['자산총계'],
        '부채총계': ['부채총계'],
        '자본총계': ['자본총계'],
        '유동자산': ['유동자산'],
        '유동부채': ['유동부채'],
        '매출액': ['매출액'],
        '영업이익': ['영업이익'],
        '당기순이익': ['당기순이익', '당기순이익(손실)'],
        '자본금': ['자본금'],
    }
    year = 기준일자[:4]
    # corp_code 매핑
    code_map = load_corp_code_map()
    corp_codes = [code_map.get(t.zfill(6), None) for t in ticker_list]
    corp_codes = [c for c in corp_codes if c]
    if not corp_codes:
        print('[DART] 유효 corp_code 없음')
        return None
    url = f"{DART_API_URL}fnlttMultiAcnt.json"
    params = {
        'crtfc_key': DART_API_KEY,
        'corp_code': ','.join(corp_codes),
        'bsns_year': year,
        'reprt_code': reprt_code,
    }
    r = requests.get(url, params=params, timeout=20)
    data = r.json()
    if data.get('status') != '000' or 'list' not in data:
        print(f"[DART] status={data.get('status')} message={data.get('message','')}")
        return None
    df = pd.DataFrame(data['list'])
    # 결과 dict: {ticker: {항목:값,...}}
    result = {}
    for ticker in ticker_list:
        corp_code = code_map.get(ticker.zfill(6), None)
        if not corp_code:
            continue
        # 연결/별도/분기 fallback
        found = None
        for fs_div in fs_divs:
            sub = df[(df['corp_code']==corp_code)&(df['fs_div']==fs_div)]
            if not sub.empty:
                found = sub
                break
        if found is None or found.empty:
            result[ticker] = None
            continue
        # 계정명별 값 추출
        key_map = {}
        for k, vlist in account_map.items():
            val = None
            for v in vlist:
                row = found[found['account_nm']==v]
                if not row.empty:
                    try:
                        val = float(row.iloc[0]['thstrm_amount'].replace(',', ''))
                        break
                    except Exception:
                        val = None
            key_map[k] = val
        # 주요 재무비율 계산
        부채비율 = (key_map['부채총계']/key_map['자본총계']*100) if key_map['부채총계'] and key_map['자본총계'] else None
        유동비율 = (key_map['유동자산']/key_map['유동부채']*100) if key_map['유동자산'] and key_map['유동부채'] else None
        ROE = (key_map['당기순이익']/key_map['자본총계']*100) if key_map['당기순이익'] and key_map['자본총계'] else None
        key_map['부채비율'] = 부채비율
        key_map['유동비율'] = 유동비율
        key_map['ROE'] = ROE
        result[ticker] = key_map
    return result

# --- 실전 파이프라인 연동 예시 ---
# top_tickers = ['005930','035420',...]  # TopN 종목 리스트
# fin_data = fetch_dart_multi_financials(top_tickers, 기준일자='20240605')
# for t, d in fin_data.items():
#     print(t, d)
# DB 저장/후처리 등은 기존 파이프라인과 동일하게 연동 

# --- DART 재무비율 평가 기준 함수(실전 기준표 반영) ---
def grade_debt_ratio(val):
    if val is None:
        return None
    if val <= 100:
        return 'good'
    if val <= 200:
        return 'normal'
    return 'bad'

def grade_current_ratio(val):
    if val is None:
        return None
    if val >= 200:
        return 'good'
    if val >= 100:
        return 'normal'
    return 'bad'

def grade_roe(val):
    if val is None:
        return None
    if val >= 10:
        return 'good'
    if val >= 5:
        return 'normal'
    return 'bad'

def save_dart_financials_to_db(ticker, 기준일자, dart_row):
    """
    - ticker: 종목코드
    - 기준일자: YYYYMMDD
    - dart_row: {'부채비율': float, '유동비율': float, 'ROE': float, ...}
    - financials 테이블에 부채비율, 유동비율, ROE 및 등급 컬럼 저장(없으면 None)
    """
    DB_PATH = os.path.join(os.path.dirname(__file__), '../../db/stock_filter2.db')
    now = datetime.now().strftime('%Y%m%d')
    debt_grade = grade_debt_ratio(dart_row.get('부채비율'))
    curr_grade = grade_current_ratio(dart_row.get('유동비율'))
    roe_grade = grade_roe(dart_row.get('ROE'))
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        UPDATE financials SET 부채비율=?, 유동비율=?, ROE=?, 부채비율_등급=?, 유동비율_등급=?, ROE_등급=?, 기록일=?
        WHERE ticker=? AND 기준일자=?
    """, (
        dart_row.get('부채비율'), dart_row.get('유동비율'), dart_row.get('ROE'),
        debt_grade, curr_grade, roe_grade, now, ticker, 기준일자
    ))
    # 만약 해당 row가 없으면 insert
    if conn.total_changes == 0:
        conn.execute("""
            INSERT INTO financials (ticker, 기준일자, 부채비율, 유동비율, ROE, 부채비율_등급, 유동비율_등급, ROE_등급, 기록일)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticker, 기준일자,
            dart_row.get('부채비율'), dart_row.get('유동비율'), dart_row.get('ROE'),
            debt_grade, curr_grade, roe_grade, now
        ))
    conn.commit()
    conn.close()

def load_candidates(path):
    return pd.read_csv(path)

def get_latest_report_info(target_date):
    """
    target_date: YYYYMMDD
    반환: (bsns_year, reprt_code)
    - 3~4월: 전년도 사업보고서(11011)
    - 5~8월: 당해 1분기(11013)
    - 8~10월: 당해 반기(11012)
    - 11~12월: 당해 3분기(11014)
    """
    dt = datetime.strptime(target_date, '%Y%m%d')
    year = dt.year
    month = dt.month
    # 사업보고서: 3~4월(전년도)
    if month <= 4:
        return str(year-1), '11011'  # 전년도 사업보고서
    # 1분기: 5~7월
    elif 5 <= month <= 7:
        return str(year), '11013'    # 당해 1분기
    # 반기: 8~10월
    elif 8 <= month <= 10:
        return str(year), '11012'    # 당해 반기
    # 3분기: 11~12월
    else:
        return str(year), '11014'    # 당해 3분기

# =============================
# [사업보고서 PDF 추출 파이프라인] (기존 기능 영향 없음)
# =============================
def get_rcp_no(ticker, year, report_code='A001'):
    """
    DART 공시검색 API로 rcpNo(접수번호) 조회
    - ticker: 종목코드(문자열)
    - year: 연도(문자열)
    - report_code: 보고서종류(A001: 사업보고서)
    반환: rcept_no(문자열) 또는 None
    """
    corp_code = get_corp_code(ticker)
    if not corp_code:
        print(f"[DART] corp_code not found for ticker {ticker}")
        return None
    url = f"{DART_API_URL}list.json"
    params = {
        'crtfc_key': DART_API_KEY,
        'corp_code': corp_code,
        'bgn_de': f'{year}0101',
        'end_de': f'{year}1231',
        'pblntf_ty': 'A',  # 정기공시(사업보고서)
        'pblntf_detail_ty': report_code,
        'page_count': 10
    }
    r = requests.get(url, params=params, timeout=10)
    data = r.json()
    if data.get('status') == '013' or 'list' not in data:
        print(f"[DART] No report found for {ticker} {year}")
        return None
    # 'rcept_no'가 있는 항목만 대상으로 처리
    for item in data['list']:
        if 'rcept_no' in item and item.get('report_nm','').startswith('사업보고서'):
            return item['rcept_no']
    for item in data['list']:
        if 'rcept_no' in item:
            return item['rcept_no']
    return None

def download_dart_pdf(rcp_no, save_dir='data/dart_pdfs'):
    """
    DART PDF 원문 다운로드(이미 있으면 skip)
    - rcp_no: 접수번호
    - save_dir: 저장 폴더
    반환: 저장된 파일 경로
    """
    os.makedirs(save_dir, exist_ok=True)
    pdf_path = os.path.join(save_dir, f'{rcp_no}.pdf')
    if os.path.exists(pdf_path):
        return pdf_path
    # DART PDF 다운로드 URL
    url = f"https://dart.fss.or.kr/pdf/download/pdf.do?rcp_no={rcp_no}"
    r = requests.get(url, stream=True, timeout=30)
    if r.status_code == 200:
        with open(pdf_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return pdf_path
    else:
        print(f"[DART] PDF download failed: {rcp_no}")
        return None

def extract_text_from_pdf(pdf_path, maxpages=30):
    """
    PDF에서 텍스트 추출(처음 maxpages 페이지만)
    반환: 전체 텍스트 문자열
    """
    text = ''
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            if i >= maxpages:
                break
            text += page.extract_text() or ''
    return text

def extract_section_from_text(text, section_name='사업의 내용'):
    """
    텍스트에서 '사업의 내용' 섹션만 추출(정규표현식)
    반환: 섹션 텍스트 또는 None
    """
    # 예시: 'II. 사업의 내용' ~ 다음 'III.' 또는 끝까지
    m = re.search(r'(II[\.|\s]+사업의 내용[\s\S]+?)(III[\.|\s]+|$)', text)
    if m:
        return m.group(1).strip()
    return None

def extract_subsection_from_text(text, subsection_name='사업의 개요'):
    """
    '사업의 내용' 등에서 subsection_name(예: '1. 사업의 개요') ~ 다음 번호 소제목 또는 끝까지 추출
    반환: 소제목 텍스트 또는 None
    """
    # 예: '1. 사업의 개요' ~ '2.' 또는 끝까지
    m = re.search(r'(1[\.|\s]+%s[\s\S]+?)(2[\.|\s]+|$)' % re.escape(subsection_name), text)
    if m:
        return m.group(1).strip()
    # fallback: subsection_name부터 끝까지
    idx = text.find(subsection_name)
    if idx >= 0:
        return text[idx:].strip()
    return None

def extract_company_overview_from_text(text):
    """
    '회사 개요' 섹션(여러 패턴 지원) ~ '사업의 내용' 등 다음 대제목/소제목 또는 끝까지 추출
    """
    # 패턴1: I. 회사의 개요 ~ II. 사업의 내용
    m = re.search(
        r'(I[\.|\s]*회사[의\s]*개요[\s\S]+?)(II[\.|\s]*사업[의\s]*내용|2[\.|\s]*사업[의\s]*내용|사업[의\s]*내용|$)',
        text)
    if not m:
        # 패턴2: 1. 회사의 개요 ~ 2. 사업의 내용
        m = re.search(
            r'(1[\.|\s]*회사[의\s]*개요[\s\S]+?)(2[\.|\s]*사업[의\s]*내용|사업[의\s]*내용|$)',
            text)
    if not m:
        # 패턴3: 회사의 개요 ~ 사업의 내용
        m = re.search(
            r'(회사[의\s]*개요[\s\S]+?)(사업[의\s]*내용|$)',
            text)
    if m:
        return m.group(1).strip()
    return None

# =============================
# [사업보고서 PDF 추출 파이프라인] 끝
# =============================

# =============================
# [사업보고서 document.xml 기반 본문 자동 추출 기능 주석]
# =============================
# - 사업보고서 document.xml에서 회사 개요/사업의 내용 등 본문을 자동 추출하는 기능은
#   실제 XML 구조가 회사/보고서마다 다르고, 목차/본문/구분선/페이지번호 등이 섞여 있어 완전 자동화가 쉽지 않음.
# - 본문은 <P>, <Text>, <N>, <TD> 등 다양한 태그/위치에 분산되어 있음.
# - 목차/구분선/페이지번호 등 노이즈가 많고, 본문이 한 덩어리로 이어지는 경우도 많음.
# - 현재 코드는 실전 파싱 실험/확장용으로 유지하며, 실제 운영/자동화 적용시에는
#   (1) zip 내부 XML을 직접 열어 구조를 확인하고,
#   (2) 회사/연도별로 본문 위치/태그/패턴을 맞춰 커스텀 파싱 로직을 추가해야 함.
# - 완전 자동화가 필요하다면 LLM(대용량 언어모델) 기반 요약/구조화, 수작업 패턴 추가 등 병행 필요.
# - 본 기능은 실전 실험/확장/테스트용으로 유지하며, 주요 한계/운영 팁/주의사항을 반드시 참고할 것.
# =============================
# ... existing code ...

def download_dart_document_xml(rcept_no, save_dir='data/dart_xmls'):
    """
    DART document.xml API로 zip 파일 다운로드(이미 있으면 skip)
    - rcept_no: 접수번호
    - save_dir: 저장 폴더
    반환: 저장된 zip 파일 경로
    """
    os.makedirs(save_dir, exist_ok=True)
    zip_path = os.path.join(save_dir, f'{rcept_no}.zip')
    if os.path.exists(zip_path):
        return zip_path
    url = f"https://opendart.fss.or.kr/api/document.xml"
    params = {
        'crtfc_key': DART_API_KEY,
        'rcept_no': rcept_no
    }
    r = requests.get(url, params=params, timeout=30)
    if r.status_code == 200 and r.content[:2] == b'PK':  # zip signature
        with open(zip_path, 'wb') as f:
            f.write(r.content)
        return zip_path
    else:
        print(f"[DART] document.xml zip download failed: {rcept_no}")
        return None

def extract_section_from_document_xml(zip_path, section_name='사업의 내용'):
    """
    zip 파일 내부 XML에서 section_name(예: '사업의 내용') 포함 텍스트 추출
    반환: 섹션 텍스트 또는 None
    """
    if not zip_path or not os.path.exists(zip_path):
        return None
    with zipfile.ZipFile(zip_path, 'r') as zf:
        xml_files = [f for f in zf.namelist() if f.endswith('.xml')]
        if not xml_files:
            print(f"[DART] No XML in zip: {zip_path}")
            return None
        with zf.open(xml_files[0]) as xmlf:
            try:
                tree = ET.parse(xmlf, ET.XMLParser(recover=True))
                root = tree.getroot()
                all_text = ET.tostring(root, encoding='utf-8', method='text').decode('utf-8', errors='ignore')
            except Exception as e:
                print(f"[DART] lxml parse error: {e}")
                # fallback: 텍스트로 읽어서 정규표현식
                xmlf.seek(0)
                all_text = xmlf.read().decode('utf-8', errors='ignore')
            m = re.search(r'(II[\.|\s]+사업의 내용[\s\S]+?)(III[\.|\s]+|$)', all_text)
            if m:
                return m.group(1).strip()
            return None

def extract_subsection_from_document_xml(zip_path, subsection_name='사업의 개요'):
    """
    zip 파일 내부 XML에서 subsection_name(예: '사업의 개요')가 포함된 노드 이하의 텍스트만 추출
    반환: 소제목 텍스트 또는 None
    """
    if not zip_path or not os.path.exists(zip_path):
        return None
    with zipfile.ZipFile(zip_path, 'r') as zf:
        xml_files = [f for f in zf.namelist() if f.endswith('.xml')]
        if not xml_files:
            print(f"[DART] No XML in zip: {zip_path}")
            return None
        with zf.open(xml_files[0]) as xmlf:
            try:
                tree = ET.parse(xmlf, ET.XMLParser(recover=True))
                root = tree.getroot()
                # 트리 전체를 순회하며 subsection_name이 포함된 노드 탐색
                for elem in root.iter():
                    text = (elem.text or '').strip()
                    if subsection_name in text:
                        # 해당 노드 이하의 모든 텍스트 합치기
                        parts = [text]
                        for sub in elem.iterdescendants():
                            t = (sub.text or '').strip()
                            if t:
                                parts.append(t)
                        return '\n'.join(parts)
            except Exception as e:
                print(f"[DART] lxml parse error: {e}")
                return None
    return None

# =============================
# [사업보고서 document.xml 추출 파이프라인] 끝
# =============================

if __name__ == "__main__":
    # [2025-06-11] --tickers 인자 추가: TopN 종목 직접 지정 가능(메인 파이프라인 연동)
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', type=str, required=True)
    parser.add_argument('--tickers', type=str, default=None, help='콤마(,)로 구분된 종목코드 리스트(예: 005930,035420)')
    args = parser.parse_args()
    date_str = args.date

    bsns_year, reprt_code = get_latest_report_info(date_str)

    # --tickers가 있으면 해당 종목만, 없으면 기존 candidates_날짜.csv 사용
    if args.tickers:
        top_tickers = [t.strip() for t in args.tickers.split(',') if t.strip()]
    else:
        candidates = load_candidates(f'data/processed/candidates_{date_str}.csv')
        top_tickers = candidates['ticker'].astype(str).tolist()

    fin_data = fetch_dart_multi_financials(top_tickers, 기준일자=bsns_year, reprt_code=reprt_code)
    if fin_data is None:
        print(f"[DART] {date_str} 기준 데이터 없음 (year={bsns_year}, reprt_code={reprt_code})")
    else:
        for t, d in fin_data.items():
            if d is not None:
                save_dart_financials_to_db(t, date_str, d) 