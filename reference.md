정교하고 확장성 높은 시스템을 구축하기 위한 탁월한 비전입니다! 특히 **모든 단계에서 DB를 중심으로 데이터를 주고받는 방식**은 기능 추가 및 변경이 용이한 **모듈식 구조를 위한 핵심적인 전략**이며, 이는 전문가적 견해로도 매우 바람직하다고 판단됩니다.

이러한 접근 방식을 기반으로, 커서 AI에게 전달할 **"주식 시장 데이터 기반 자동 분석·추천 시스템" 과제 계획서**를 상세하게 작성해 드리겠습니다. MVP에 집중하되, 향후 확장성을 완벽히 지원하는 구조를 목표로 합니다.

---

## 주식 시장 데이터 자동 분석·추천 시스템 (MVP & 확장형) 과제 계획서

---

### 1. 과제명
**주식 시장 데이터 자동 수집·분석·추천 시스템 (MVP)**
_(확장형 AI 기반 투자 리서치 플랫폼 기초 구축)_

### 2. 목표 및 개요

#### A. 목표
* 국내 주식 시장의 모든 종목에 대한 **가격, 거래량, 업종·테마, 재무, 뉴스 등 핵심 데이터를 자동으로 수집 및 가공**합니다.
* 가공된 데이터를 기반으로 **업종/테마 트렌드, 주도주, 주요 이슈, 투자 매력도** 등 실전 투자에 필요한 인사이트를 **자동 리포트** 형태로 제공합니다.
* 향후 **LLM(대규모 언어 모델) 등 AI 분석 연계 및 SaaS(Software as a Service) 사업화**가 가능하도록 **모듈형 데이터 인프라를 설계하고 구축**합니다.

#### B. 핵심 가치
* **실전 투자 자동화 리서치:** 시장의 흐름과 개별 종목의 특징을 자동으로 분석하여 투자 의사 결정에 필요한 정보를 신속하게 제공합니다.
* **데이터/분석 API 기반:** 구축된 데이터와 분석 결과를 외부 시스템 또는 사용자에게 API 형태로 제공할 수 있는 기반을 마련합니다.
* **유연한 확장성:** 초기 MVP 이후 단계적 기능 확장(개인화, 전략 백테스트, 외부 연동 등)에 최적화된 모듈식 구조를 구현합니다.

### 3. MVP 단계 주요 기능 및 구성

---

#### A. 데이터 수집 및 DB 구축 (핵심: DB 중심 파이프라인)

* **원칙:** 모든 수집된 데이터는 즉시 DB에 저장되며, 다음 단계의 모듈은 DB에서 데이터를 읽어 처리합니다.
* **대상 데이터:**
    * **국내 상장 종목 기본 정보:** 종목코드, 종목명, 시장 구분, 상장일 등.
    * **업종 분류:** 한국표준산업분류 기반의 업종 코드, 업종명.
    * **테마 분류 및 매핑:** 비공식 테마명, 각 테마에 속하는 종목 리스트 (최초 구축 후 정기 업데이트).
    * **일별 시세:** 종가, 시가, 고가, 저가, 거래량, 거래대금, 등락률, 시가총액 등.
    * **주요 재무 정보:** (분기/연간) 매출액, 영업이익, 당기순이익, 자산총계, 자본총계, 부채비율, ROE, EPS, PER, PBR 등.
    * **뉴스 메타 정보:** 뉴스 제목, 요약, 발행일시, 출처, 원문 URL.
* **주요 데이터 소스:**
    * **PyKRX:** 종목 기본 정보, 일별 시세, KRX 업종 지수 데이터.
    * **DART API:** 종목별 공식 업종 분류 (사업보고서 기반), 분기/연간 주요 재무 정보.
    * **Selenium (네이버 증권 크롤링):** 비공식 테마 분류 및 테마별 종목 매핑. **(주의: 웹사이트 변경에 취약, 주기적 모니터링 및 코드 유지보수 필수. 장기적으로는 대체 소스 모색 필요)**
    * **Selenium (뉴스 크롤링):** 주요 포털/언론사 뉴스 수집. **(주의: 과도한 요청 및 법적 문제 유의, 뉴스 API 전환 고려)**
* **최소 MVP용 DB 스키마 설계:** (자세한 스키마는 4. DB 계획에 명시)
    * `Stocks` (종목 마스터)
    * `Industries` (업종 마스터)
    * `Themes` (테마 마스터)
    * `StockThemes` (종목-테마 매핑)
    * `DailyStockPrices` (일별 종목 시세)
    * `FinancialStatements` (종목 재무 정보)
    * `NewsArticles` (뉴스 메타 정보)
    * `ArticleStockMap` (뉴스-종목 매핑)
    * `ArticleThemeMap` (뉴스-테마 매핑)

#### B. 1차 자동 가공 및 분석 로직

* **원칙:** 각 분석 로직은 독립적인 모듈로 구현되며, DB에 저장된 데이터를 읽어 처리한 후, 분석 결과 역시 DB에 저장합니다.
* **주요 분석 기능:**
    * **일간 업종/테마별 등락률 집계:** `DailyIndustryTrends`, `DailyThemeTrends` 테이블에 일별 등락률, 거래대금 등 지표 자동 업데이트.
    * **상위 상승/하락 업종·테마 자동 선별:** 일별 등락률 및 거래대금 순위 기반으로 강세/약세 섹터 도출.
    * **각 테마별·업종별 주도주 추출:** 상위 섹터 내에서 상승률, 거래대금, 시가총액 등을 기준으로 주도 종목 자동 판별.
    * **뉴스/공시 등 이슈 자동 매핑 및 요약:** 수집된 뉴스(`NewsArticles`)를 종목 및 테마(`ArticleStockMap`, `ArticleThemeMap`)에 자동으로 매핑하고, LLM을 활용하여 핵심 내용을 요약 (MVP에서는 키워드 매칭 및 간단한 요약에 집중).
    * **정량 기준 기반 투자매력도/관심도 점수화:** (MVP 범위: 일별 등락률, 거래대금, 시가총액, 주요 재무지표(PER, PBR, ROE, 부채비율) 등)을 가중치 방식으로 조합하여 종목/테마/업종의 투자 매력 점수 산출.
* **산출물 저장:** 모든 분석 결과는 DB (`DailyAnalysisResults` 또는 각 지표 테이블 내 필드)에 저장되어 다음 단계에서 활용 가능하게 합니다.
    * 예: `DailyAnalysisResults` 테이블에 '오늘의 강세 테마', '주도주 목록', '이슈 요약' 등 저장.

#### C. LLM 연계 및 질의응답 (MVP 최소 기능)

* **원칙:** LLM은 DB에 저장된 정형/비정형 데이터를 활용하여 사용자 질의에 응답합니다.
* **주요 기능:**
    * **LLM 연동 모듈 개발:** 선택된 LLM API(예: Gemini Pro)와의 효율적인 연동 모듈 구현.
    * **데이터 기반 질의응답 템플릿 설계:** DB에서 조회한 시세, 트렌드, 뉴스 요약, 재무 정보 등을 LLM의 입력 프롬프트에 효과적으로 구성하는 템플릿 개발.
    * **예시 질의 응답:**
        * "최근 한 달간 강세 섹터는?"
        * "2차전지 테마주에 최근 무슨 이슈가 있었나?"
        * "삼성전자 최근 투자매력 점수 변화와 관련 뉴스 요약"
    * **LLM 답변 로깅:** LLM의 질의(입력), 답변(출력), 사용된 데이터, 응답 시간 등을 `LLMInteractionLogs` 테이블에 저장하여 향후 분석 및 개선에 활용합니다.
* **산출물:** LLM 연동 모듈, 질의응답 API 엔드포인트, LLM 로그.

#### D. 모듈 및 파이프라인 구조화 (확장성 핵심)

* **아키텍처 원칙:**
    * **독립적인 모듈:** 각 기능(데이터 수집, 정규화, 분석, 리포팅, LLM 연동)은 독립적인 파이썬 모듈 또는 서비스로 분리합니다.
    * **DB 중심 데이터 흐름 (SSOT - Single Source of Truth):** 모든 단계의 중간 및 최종 결과는 반드시 **관계형 DB (PostgreSQL 권장)**에 저장됩니다. 다음 단계의 모듈은 이전 단계의 결과를 DB에서 읽어 시작하므로, 각 모듈은 독립적으로 실행/테스트/유지보수 가능합니다.
    * **스케줄러 기반:** Airflow 또는 Prefect와 같은 워크플로우 관리 도구를 활용하여 각 모듈의 실행 순서, 주기, 의존성을 체계적으로 관리합니다.
    * **컨테이너화 (Docker):** 각 모듈을 Docker 컨테이너로 패키징하여 개발/배포 환경의 일관성을 유지하고 확장성을 높입니다.
* **예시 파이프라인 흐름:**
    `[PyKRX/DART/Selenium_Collector] -> DB ([Stocks], [DailyStockPrices], [FinancialStatements], [NewsArticles], ...)`
    `[Data_Processor] (from DB) -> DB ([DailyIndustryTrends], [DailyThemeTrends], [ArticleStockMap], [ArticleThemeMap], ...)`
    `[Analysis_Engine] (from DB) -> DB ([DailyAnalysisResults], [InvestmentScores], ...)`
    `[LLM_Integrator] (from DB & LLM API) -> DB ([LLMInteractionLogs])`

### 4. DB 계획 (상세)

관계형 데이터베이스(PostgreSQL 권장)를 주력으로 사용하며, 비정형 데이터(뉴스 원문) 처리를 위해 Elasticsearch와 같은 NoSQL 솔루션을 보조적으로 활용하는 하이브리드 접근 방식을 제안합니다.

---

#### **A. 관계형 데이터베이스 (PostgreSQL)**

**가. 마스터 데이터 관리 파일 (정적 또는 주기적 업데이트)**

1.  **`Stocks` 테이블 (종목 기본 정보)**
    * **목적:** 모든 상장 종목의 기본적인 고유 정보 관리.
    * **필드:**
        * `stock_code` (VARCHAR, PK)
        * `stock_name` (VARCHAR)
        * `market_type` (VARCHAR) - `KOSPI`, `KOSDAQ`, `KONEX`
        * `industry_code` (VARCHAR, FK) - `Industries` 테이블 참조 (DART 기반)
        * `listed_date` (DATE)
        * `is_active` (BOOLEAN) - 상장 폐지/거래 정지 등 활성 상태
        * `last_updated_at` (DATETIME)
    * **인덱스:** `stock_name`, `market_type`, `industry_code`

2.  **`Industries` 테이블 (업종 분류 정보)**
    * **목적:** 한국표준산업분류 기반의 업종 정보 관리.
    * **필드:**
        * `industry_code` (VARCHAR, PK)
        * `industry_name` (VARCHAR)
        * `parent_industry_code` (VARCHAR, NULLABLE, FK) - 계층 구조 표현
        * `description` (TEXT, NULLABLE)
        * `last_updated_at` (DATETIME)
    * **인덱스:** `industry_name`

3.  **`Themes` 테이블 (테마 분류 정보)**
    * **목적:** 비공식 테마의 고유 정보 관리.
    * **필드:**
        * `theme_id` (INT, PK, AUTO_INCREMENT)
        * `theme_name` (VARCHAR, UNIQUE)
        * `description` (TEXT, NULLABLE)
        * `last_updated_at` (DATETIME)
    * **인덱스:** `theme_name`

4.  **`StockThemes` 테이블 (종목-테마 매핑)**
    * **목적:** 특정 종목이 어떤 테마에 속하는지 매핑 (다대다 관계).
    * **필드:**
        * `stock_code` (VARCHAR, PK, FK)
        * `theme_id` (INT, PK, FK)
        * `created_at` (DATETIME)
    * **복합 PK:** (`stock_code`, `theme_id`)

**나. 일별/주기별 시계열 데이터 관리 파일**

1.  **`DailyStockPrices` 테이블 (일별 종목 시세)**
    * **목적:** 매일의 종목별 시세 및 거래 정보 기록.
    * **필드:**
        * `record_date` (DATE, PK)
        * `stock_code` (VARCHAR, PK, FK)
        * `open_price` (DECIMAL)
        * `high_price` (DECIMAL)
        * `low_price` (DECIMAL)
        * `close_price` (DECIMAL)
        * `volume` (BIGINT)
        * `trading_value` (BIGINT)
        * `change_rate` (DECIMAL)
        * `market_cap` (BIGINT) - 해당일 종가 기준 시가총액
        * `created_at` (DATETIME)
    * **복합 PK:** (`record_date`, `stock_code`)
    * **인덱스:** `stock_code`

2.  **`DailyIndustryTrends` 테이블 (일별 업종 트렌드)**
    * **목적:** 매일의 업종별 등락률 및 지표 기록 (KRX 업종 지수 또는 평균 등락률).
    * **필드:**
        * `record_date` (DATE, PK)
        * `industry_code` (VARCHAR, PK, FK)
        * `daily_change_rate` (DECIMAL)
        * `total_trading_value` (BIGINT) - 해당 업종 종목들 총 거래대금 합산
        * `created_at` (DATETIME)
    * **복합 PK:** (`record_date`, `industry_code`)

3.  **`DailyThemeTrends` 테이블 (일별 테마 트렌드)**
    * **목적:** 매일의 테마별 등락률 및 지표 기록 (테마 편입 종목들의 평균 또는 가중 평균).
    * **필드:**
        * `record_date` (DATE, PK)
        * `theme_id` (INT, PK, FK)
        * `daily_change_rate` (DECIMAL)
        * `total_trading_value` (BIGINT) - 해당 테마 종목들 총 거래대금 합산
        * `created_at` (DATETIME)
    * **복합 PK:** (`record_date`, `theme_id`)

**다. 재무/분석/로그 데이터 관리 파일**

1.  **`FinancialStatements` 테이블 (종목 재무 정보)**
    * **목적:** 종목별, 보고서별 핵심 재무 지표 저장 (온디맨드/분기 업데이트).
    * **필드:**
        * `financial_id` (BIGINT, PK, AUTO_INCREMENT)
        * `stock_code` (VARCHAR, FK)
        * `report_type` (VARCHAR) - `분기`, `반기`, `사업`
        * `report_year` (INT)
        * `report_quarter` (INT) - 1, 2, 3, 4 (사업보고서는 4분기에 해당)
        * `report_date` (DATE) - 보고서 기준 일자 (예: 3월 31일, 6월 30일)
        * `receipt_date` (DATE) - 보고서 접수 일자 (DART 공시일)
        * `sales` (BIGINT)
        * `operating_profit` (BIGINT)
        * `net_profit` (BIGINT)
        * `total_assets` (BIGINT)
        * `total_equity` (BIGINT)
        * `debt_ratio` (DECIMAL) - 부채비율
        * `eps` (BIGINT) - 주당순이익
        * `per` (DECIMAL, NULLABLE) - 주가수익비율 (재무 데이터 기반 계산)
        * `pbr` (DECIMAL, NULLABLE) - 주가순자산비율 (재무 데이터 기반 계산)
        * `roe` (DECIMAL) - 자기자본이익률
        * `last_updated_at` (DATETIME)
        * `raw_json_data` (JSONB, NULLABLE) - DART 원본 데이터 (확장성 고려)
    * **복합 인덱스:** (`stock_code`, `report_year`, `report_quarter`), `receipt_date`

2.  **`DailyAnalysisResults` 테이블 (일별 분석 결과)**
    * **목적:** 매일 실행되는 자동 분석 로직의 주요 결과 요약 저장.
    * **필드:**
        * `record_date` (DATE, PK)
        * `analysis_type` (VARCHAR, PK) - `top_gainers_sector`, `top_gainers_theme`, `leading_stocks_by_theme`, `low_valuation_stocks` 등
        * `result_data` (JSONB) - 분석 결과 (예: `[{"sector_name": "반도체", "change_rate": 3.5}, ...]`)
        * `summary_text` (TEXT, NULLABLE) - LLM 또는 요약 로직으로 생성된 텍스트 리포트
        * `created_at` (DATETIME)
    * **복합 PK:** (`record_date`, `analysis_type`)

3.  **`LLMInteractionLogs` 테이블 (LLM 상호작용 로그)**
    * **목적:** LLM 질의응답 내역 및 성능 분석을 위한 로그.
    * **필드:**
        * `log_id` (BIGINT, PK, AUTO_INCREMENT)
        * `query_text` (TEXT) - 사용자 질문
        * `response_text` (TEXT) - LLM 답변
        * `model_name` (VARCHAR) - 사용된 LLM 모델명
        * `input_tokens` (INT)
        * `output_tokens` (INT)
        * `response_time_ms` (INT)
        * `related_data_snapshot` (JSONB, NULLABLE) - LLM 입력에 사용된 주요 데이터 스냅샷 (예: 뉴스 ID, 종목 코드)
        * `created_at` (DATETIME)
    * **인덱스:** `created_at`

#### **B. NoSQL 데이터베이스 (Elasticsearch)**

1.  **`NewsArticles` 인덱스 (뉴스 기사 원문 및 요약)**
    * **목적:** 대량의 뉴스 기사 원문, LLM 요약, 키워드 등을 저장하여 빠른 전문 검색 및 분석 지원.
    * **필드 (JSON 문서):**
        * `article_id` (KEYWORD, PK) - 고유 ID (UUID 또는 SHA256 해시)
        * `title` (TEXT)
        * `url` (KEYWORD)
        * `published_at` (DATE)
        * `source` (KEYWORD)
        * `content_raw` (TEXT) - 기사 원문 (검색용, 대용량)
        * `content_summary` (TEXT, NULLABLE) - LLM으로 요약된 기사 내용
        * `keywords` (KEYWORD ARRAY, NULLABLE) - 추출된 핵심 키워드
        * `related_stock_codes` (KEYWORD ARRAY, NULLABLE) - 관련 종목 코드 (매핑 테이블 대신 직접 포함)
        * `related_theme_ids` (INTEGER ARRAY, NULLABLE) - 관련 테마 ID (매핑 테이블 대신 직접 포함)
        * `sentiment` (KEYWORD, NULLABLE) - 긍정/부정/중립 (LLM 분석 기반)
        * `issue_tags` (KEYWORD ARRAY, NULLABLE) - 특정 이슈 분류 태그 (예: '정부정책', '실적발표', '기술혁신')
        * `created_at` (DATE)
    * **매핑:** `content_raw`, `title`, `content_summary` 필드에 Full-text search 인덱스 적용. `published_at`에 Range Query 인덱스 적용.
    * **활용:** 특정 키워드/종목/테마 관련 뉴스 검색, LLM 입력 데이터 제공.

---

### 5. 로드맵별 DB 활용 및 리포트 생산

**가. MVP 단계:**

* **데이터 흐름:** `Stocks`, `Industries`, `Themes`, `StockThemes` (마스터 데이터) -> `DailyStockPrices`, `DailyIndustryTrends`, `DailyThemeTrends` (시계열 데이터) -> `FinancialStatements` (온디맨드) -> `NewsArticles` (Elasticsearch).
* **리포트 생성:**
    * **"오늘의 강세 테마/주도주" 리포트 (시나리오 2):** `DailyAnalysisResults` 테이블의 `result_data`와 `summary_text`를 통해 생성.
    * **기초 LLM 질의응답 (시나리오 7):** `DailyStockPrices`, `DailyIndustryTrends`, `DailyThemeTrends`, `FinancialStatements`, `NewsArticles` (Elasticsearch)에서 데이터를 조회하여 LLM에 전달, LLM의 답변을 리포트.

**나. 1차 확장 단계 (시나리오 3, 4, 5, 6, 8, 11, 12, 13, 15)**

* **DB 확장 (추가 테이블):**
    * `DailySupplyDemand` (일별 수급 정보: 외국인/기관/개인 순매수/도)
    * `ETFs` (ETF 마스터 정보)
    * `DailyETFPrices` (일별 ETF 시세)
    * `GlobalEvents` (글로벌 경제/정치 이벤트: 날짜, 설명, 관련 섹터)
    * `UserInterests` (사용자 관심 종목/테마/섹터 등록)
    * `PortfolioHistory` (사용자 포트폴리오 스냅샷)
    * `Alerts` (자동 알림 로그)
* **리포트 생성:**
    * **"신규 강세 섹터 트렌드 분석" (시나리오 3):** `DailyThemeTrends`, `DailyIndustryTrends`를 기반으로 추세 분석, `NewsArticles`에서 관련 이슈 요약 후 LLM 연동.
    * **"조정중인 섹터 매수전략" (시나리오 4):** `DailyStockPrices`, `DailyIndustryTrends`, `DailyThemeTrends`의 변동폭 감지, `FinancialStatements`, `DailySupplyDemand`를 활용한 수급/재무 분석, LLM 기반 전략 코멘트.
    * **"저평가·소외 섹터 발굴" (시나리오 6):** `FinancialStatements`의 재무 지표, `DailyStockPrices`의 주가 지표를 이용한 정량 스크리닝 리포트.
    * **"뉴스/이슈-종목/테마 매핑 영향 분석" (시나리오 12):** `NewsArticles`의 `related_stock_codes`, `related_theme_ids`, `sentiment`, `issue_tags` 필드를 활용하여 특정 이슈가 특정 종목/테마에 미친 영향 분석 리포트.
    * **"맞춤형 섹터/종목 이상변동 알림" (시나리오 8, 15):** `UserInterests`와 `DailyStockPrices`, `DailySupplyDemand`의 실시간/일별 변화 감지 후 `Alerts` 테이블에 알림 기록 및 전송.

**다. 2차 확장 단계 (시나리오 9, 10, 14, 16)**

* **DB 확장 (추가 테이블):**
    * `StrategyBacktests` (자동화 전략 백테스트 결과)
    * `NetworkGraphs` (종목/섹터 네트워크 분석 결과 시각화 데이터)
* **리포트 생성:**
    * **"자동 포트폴리오 최적화·전략 추천" (시나리오 9):** `DailyStockPrices`, `FinancialStatements`, `DailySupplyDemand` 등 종합 데이터를 기반으로 최적화 알고리즘 실행, `PortfolioHistory` 업데이트 및 추천 리포트.
    * **"백테스트/자동화 전략 성과검증" (시나리오 10):** `DailyStockPrices` 등 과거 시계열 데이터와 `StrategyBacktests` 테이블을 활용하여 시뮬레이션 리포트.
    * **"종목/섹터 네트워크 영향관계 시각화" (시나리오 14):** `NewsArticles`, `StockThemes`, `ArticleStockMap` 등에서 관계를 추출하여 `NetworkGraphs` 테이블에 저장된 데이터를 시각화 리포트.
    * **"LLM 기반 AI 투자비서 (챗봇)" (시나리오 16):** 모든 DB 데이터를 LLM의 컨텍스트로 활용하여 실시간 대화형 투자 리서치 제공.

---

### 6. 핵심 주의사항 및 관리 포인트

* **데이터 신뢰도:** 각 수집 단계에서 데이터 누락, 오류, 중복을 체크하는 **자동화된 검증 로직**을 반드시 포함하고, 문제가 발생 시 알림 시스템을 구축합니다.
* **API 사용량 관리:** PyKRX, DART API 및 외부 LLM API의 **호출 제한 및 비용 정책**을 철저히 준수하고, 효율적인 캐싱 전략을 적용합니다.
* **크롤링 의존성 관리:** Selenium 기반 크롤링은 웹사이트 변경에 매우 취약하므로, **정기적인 모니터링 및 유지보수** 계획을 수립하고, 장기적으로는 **안정적인 대체 소스(유료 API 등)로 전환할 로드맵**을 반드시 고려합니다.
* **모듈 간 인터페이스 명확화:** 각 모듈은 DB 스키마를 통해 명확하게 정의된 데이터를 주고받도록 설계하여, 특정 모듈 변경 시 다른 모듈에 미치는 영향을 최소화합니다.
* **테이블/인덱스 최적화:** 대량의 시계열 데이터(`DailyStockPrices` 등) 처리를 위해 DB 인덱싱 전략, 파티셔닝 등을 고려하여 쿼리 성능을 최적화합니다.
* **확장성 유지보수:** MVP 완료 후에도 지속적으로 DB 스키마와 모듈 구조를 검토하고 문서화하여 향후 기능 추가 및 개선이 용이하도록 관리합니다.

---

네, 요청하신 기능 개발 순서를 작성해 드리겠습니다.

---

## 기능 개발 순서 (MVP & 확장성 고려)

이 시스템은 **데이터 파이프라인의 안정성**을 최우선으로 하여, **핵심 데이터 수집 -> 데이터 가공 및 분석 -> LLM 연동** 순으로 개발을 진행하는 것이 가장 효율적입니다. 각 단계는 이전 단계의 결과물에 의존하므로, 아래 제시된 순서를 따르는 것이 안정적이고 확장성 높은 시스템 구축에 유리합니다.

---

### 1단계: 핵심 데이터 파이프라인 구축 (기반 다지기)

이 단계에서는 시스템의 **근간이 되는 데이터를 안정적으로 수집하고 DB에 저장**하는 것에 집중합니다. 이후 모든 기능은 이 DB에 저장된 데이터를 활용하게 됩니다.

1.  **DB 스키마 정의 및 초기화:**
    * **내용:** `Stocks`, `Industries`, `Themes`, `StockThemes`, `DailyStockPrices`, `FinancialStatements`, `NewsArticles` (NoSQL 포함), `ArticleStockMap`, `ArticleThemeMap` 등 모든 핵심 테이블의 스키마를 확정하고 DB에 생성합니다. 이 과정에서 `database/models` 폴더의 ORM 모델을 정의하고 `database/connection.py`, `database/crud.py`의 기본 골격을 완성합니다.
    * **중요성:** 모든 모듈이 바라볼 단일 정보 소스(SSOT)를 정의하는 가장 중요한 첫 단계입니다.
    * **예상 소요 시간:** 1주

2.  **PyKRX 데이터 수집 모듈 개발:**
    * **내용:** `collectors/pykrx_collector.py`를 개발하여 **전체 상장 종목 목록 (`Stocks` 테이블), 일별 시세 (`DailyStockPrices` 테이블)**를 수집하고 DB에 저장하는 기능을 구현합니다. 일별 자동 업데이트 스크립트도 포함합니다.
    * **중요성:** 주식 시세 데이터는 모든 분석의 기본입니다.
    * **예상 소요 시간:** 1주

3.  **DART API 데이터 수집 모듈 개발 (업종/재무):**
    * **내용:** `collectors/dart_collector.py`를 개발하여 **종목별 공식 업종 분류 (`Industries` 테이블 및 `Stocks` 테이블 업데이트), 주요 재무 정보 (`FinancialStatements` 테이블)**를 수집하고 DB에 저장하는 기능을 구현합니다. 재무 정보는 '필요 시점 호출 및 분기 업데이트' 로직을 초기부터 반영합니다.
    * **중요성:** 정확한 업종 분류와 재무 데이터는 깊이 있는 분석의 기반이 됩니다.
    * **예상 소요 시간:** 1주

4.  **Selenium 기반 테마 및 뉴스 데이터 수집 모듈 개발:**
    * **내용:** `collectors/naver_stock_crawler.py` (테마) 및 `collectors/news_crawler.py` (뉴스 메타)를 개발합니다. 네이버 증권에서 **테마명, 테마별 종목 매핑 (`Themes`, `StockThemes` 테이블)**을 크롤링하고, 뉴스 메타 정보(`NewsArticles` - NoSQL)를 수집하여 DB에 저장합니다.
    * **중요성:** 비공식 테마와 뉴스 데이터는 LLM 분석 및 실제 투자 흐름 파악에 필수적입니다. 크롤링의 불안정성에 대비하여 최소한의 기능으로 시작합니다.
    * **예상 소요 시간:** 1.5주

---

### 2단계: 핵심 분석 로직 및 자동 리포트 생성 (가치 창출)

수집된 데이터를 기반으로 기본적인 분석을 수행하고, 투자 인사이트를 제공하는 리포트를 자동 생성합니다.

1.  **데이터 검증 및 전처리 모듈 개발:**
    * **내용:** `processors/data_validator.py`를 개발하여 수집된 데이터의 누락, 중복, 형식 오류 등을 체크하고, 필요시 정규화하는 로직을 구현합니다.
    * **중요성:** 분석 결과의 신뢰도를 높이는 데 필수적입니다.
    * **예상 소요 시간:** 0.5주

2.  **업종/테마 트렌드 분석 모듈 개발:**
    * **내용:** `processors/theme_industry_trend_analyzer.py`를 개발하여 일별 시세 데이터를 바탕으로 **업종별/테마별 등락률 및 총 거래대금을 집계 (`DailyIndustryTrends`, `DailyThemeTrends` 테이블)**하고 DB에 저장합니다.
    * **중요성:** 시장 흐름을 파악하는 핵심 지표를 제공합니다.
    * **예상 소요 시간:** 1주

3.  **주도주/이슈 매핑 분석 모듈 개발:**
    * **내용:** `processors/leader_selector.py`를 개발하여 등락률과 거래대금 기준으로 **상위 상승/하락 업종/테마를 선별하고 주도주를 추출**합니다. `processors/news_mapper.py`를 개발하여 수집된 뉴스를 관련 종목/테마에 매핑(`ArticleStockMap`, `ArticleThemeMap` 테이블)합니다.
    * **중요성:** 핵심 투자 기회를 포착하고, 시장 이슈를 종목/테마와 연결합니다.
    * **예상 소요 시간:** 1주

4.  **투자 매력도 점수화 모듈 개발:**
    * **내용:** `processors/investment_score_calculator.py`를 개발하여 일별 시세, 거래대금, 재무 지표 등을 기반으로 **종목/테마/업종의 투자 매력 점수를 산출**하고 `DailyAnalysisResults` 테이블에 저장합니다. (MVP에서는 복잡한 수급 분석 제외)
    * **중요성:** 객관적인 지표를 통해 투자 대상의 매력도를 정량화합니다.
    * **예상 소요 시간:** 1주

---

### 3단계: LLM 연동 및 초기 서비스 구현 (인사이트 제공)

분석된 데이터를 LLM에 연동하여 사용자 친화적인 정보를 제공하고, 시스템의 기본적인 구동 환경을 마련합니다.

1.  **LLM 연동 모듈 개발:**
    * **내용:** `llm_integrator/llm_api_client.py`를 개발하여 선택된 LLM(예: Gemini Pro)과의 API 연동 기능을 구현합니다. `llm_integrator/prompt_manager.py`를 개발하여 동적으로 데이터를 삽입할 수 있는 질의응답 프롬프트 템플릿을 정의합니다.
    * **중요성:** AI를 통해 복잡한 데이터를 이해하기 쉬운 형태로 변환하는 핵심입니다.
    * **예상 소요 시간:** 1주

2.  **LLM 기반 질의응답 기능 개발:**
    * **내용:** `llm_integrator/llm_analyzer.py` 및 `llm_integrator/llm_query_handler.py`를 개발하여 DB에서 조회된 분석 결과, 뉴스 요약 등을 LLM에 전달하여 **사용자 자연어 질의에 답변을 생성**하도록 합니다. LLM의 모든 상호작용은 `LLMInteractionLogs` 테이블에 기록합니다.
    * **중요성:** 사용자가 시스템과 소통하고 인사이트를 얻는 주요 창구입니다.
    * **예상 소요 시간:** 1주

3.  **시스템 스케줄러 및 배포 환경 설정:**
    * **내용:** Airflow 또는 Prefect와 같은 **스케줄러를 설정**하고, 각 수집 및 분석 모듈이 정해진 시간에 자동 실행되도록 워크플로우(DAG)를 정의합니다. Docker를 활용한 컨테이너화 및 최소한의 배포 환경(예: 클라우드 VM)을 구축합니다.
    * **중요성:** 시스템이 독립적으로 동작하고 지속적으로 업데이트되도록 합니다.
    * **예상 소요 시간:** 1주

4.  **통합 테스트 및 초기 시연 준비:**
    * **내용:** 개발된 모든 모듈이 정상적으로 연동되는지 **엔드-투-엔드 테스트**를 수행합니다. 데이터 흐름, 분석 결과, LLM 응답의 정확성을 검증하고, 초기 시연을 위한 최소한의 데이터와 리포트 생성 환경을 준비합니다.
    * **중요성:** MVP의 완성도를 검증하고 사용자에게 첫 선을 보입니다.
    * **예상 소요 시간:** 1주

---

### 단계별 총 소요 시간 (대략적)

* **1단계: 핵심 데이터 파이프라인 구축** - 약 4.5주
* **2단계: 핵심 분석 로직 및 자동 리포트 생성** - 약 3.5주
* **3단계: LLM 연동 및 초기 서비스 구현** - 약 4주

이 순서는 유기적으로 연결되어 있으며, 각 단계의 완료 여부가 다음 단계의 시작 조건이 됩니다. 실제 개발 시에는 병렬적으로 진행할 수 있는 부분도 있겠지만, 핵심 의존성을 고려한 순서입니다.


----

아래는 **실전 자동화 투자 시스템(MVP + 확장성 고려)** 기준
**주요 파일/폴더 구조 계획서** 예시입니다.
(파이썬 기반, 모듈 독립, 컨테이너/스케줄러/테스트/문서화 대응)

---

## **1. 프로젝트 폴더 구조 (예시)**

```
stock-analytics/
│
├── config/                  # 환경설정(토큰/API/DB 등)
│   ├── settings.yaml
│   └── logger.yaml
│
├── data/                    # 원본 데이터/샘플/임시 저장(엑셀, csv 등)
│   ├── seed/
│   ├── temp/
│   └── export/
│
├── db/                      # DB 스키마, 마이그레이션, 쿼리 스크립트
│   ├── schema.sql
│   ├── migration/
│   └── queries/
│
├── scripts/                 # 단독 실행형 유틸리티/테스트/임시 스크립트
│   ├── manual_update.py
│   └── db_check.py
│
├── src/                     # 실질적 기능 모듈(각 단계별로 독립화)
│   ├── __init__.py
│   ├── main.py              # (메인 파이프라인 실행/오케스트레이터)
│   ├── collector/           # 데이터 수집/크롤러/ETL
│   │   ├── __init__.py
│   │   ├── krx_collector.py
│   │   ├── dart_collector.py
│   │   ├── theme_crawler.py
│   │   ├── news_crawler.py
│   │   └── etf_collector.py
│   ├── processor/           # 데이터 정제/가공/매핑
│   │   ├── __init__.py
│   │   ├── theme_mapper.py
│   │   ├── industry_mapper.py
│   │   └── financial_parser.py
│   ├── analyzer/            # 정량/정성 분석, 점수화, 랭킹
│   │   ├── __init__.py
│   │   ├── trend_analyzer.py
│   │   ├── scoring.py
│   │   ├── leader_selector.py
│   │   └── issue_analyzer.py
│   ├── llm/                 # LLM(질의응답/자동 리포트/프롬프트 등)
│   │   ├── __init__.py
│   │   ├── llm_connector.py
│   │   ├── prompt_templates.py
│   │   └── llm_reporter.py
│   ├── api/                 # API 서버(내부/외부, FastAPI 등)
│   │   ├── __init__.py
│   │   └── app.py
│   └── utils/               # 공통 함수/로깅/유틸
│       ├── __init__.py
│       ├── logger.py
│       ├── db_utils.py
│       └── scheduler.py
│
├── tests/                   # 유닛/통합 테스트
│   ├── test_collector.py
│   ├── test_analyzer.py
│   ├── test_llm.py
│   └── ...
│
├── docker/                  # 컨테이너/배포 관련(Dockerfile, Compose 등)
│   ├── Dockerfile
│   └── docker-compose.yaml
│
├── airflow/                 # (선택) 워크플로/스케줄러 관리
│   ├── dags/
│   └── plugins/
│
├── docs/                    # 문서(ERD, API 명세, 알고리즘, 운영가이드)
│   ├── erd.png
│   ├── db_schema.md
│   ├── workflow.md
│   ├── api_spec.md
│   └── README.md
│
├── .env                     # 환경변수 (DB/API 키 등)
├── requirements.txt         # 의존성 패키지 목록
└── README.md                # 최상위 프로젝트 설명서
```

---

## **2. 주요 파일 역할 설명**

| 폴더/파일                 | 역할/설명                                      |
| --------------------- | ------------------------------------------ |
| `config/`             | 환경설정/로그 설정 등 프로젝트 전역설정                     |
| `data/`               | 원본/임시/내보내기 데이터 폴더                          |
| `db/schema.sql`       | 전체 DB 테이블·인덱스·관계 정의                        |
| `scripts/`            | 단일 실행/테스트/긴급 유틸/수동관리 스크립트                  |
| `src/collector/`      | 각종 데이터 수집/크롤링/ETL(증권, DART, 뉴스, 테마 등)      |
| `src/processor/`      | 정제, 업종·테마·종목 매핑, 재무 파싱 등                   |
| `src/analyzer/`       | 트렌드/점수화/주도주 분석, 이슈 랭킹, 정량·정성 스코어           |
| `src/llm/`            | LLM 연동, 프롬프트, 자동 리포트, 요약/해설                |
| `src/api/`            | REST API/FastAPI 등 (내부/외부 연동, 질의응답, 통합API) |
| `src/utils/`          | DB연결, 로깅, 공통 유틸, 작업 스케줄러 등                 |
| `tests/`              | 유닛테스트/통합테스트 코드                             |
| `docker/`, `airflow/` | 컨테이너/워크플로 관리(배포 자동화, 스케줄링)                 |
| `docs/`               | 설계/운영 문서, ERD, API, 알고리즘 설명 등              |
| `.env`                | 환경변수(비밀키/API키/DB패스 등)                      |
| `requirements.txt`    | 파이썬 패키지 의존성 목록                             |
| `README.md`           | 전체 프로젝트 설명서                                |

---

## **3. 확장성/유지보수 고려 팁**

* 각 **핵심 기능별 하위 폴더 분리**(수집/정제/분석/LLM/API)
* **테스트 폴더 분리**(실행환경 변경/유닛/통합 테스트 대응)
* **설계문서/ERD/API/알고리즘 구조** 별도 보관 → 협업/유지보수/개선 용이
* **스케줄러, 도커, 환경설정, DB마이그레이션 등** 분리 → 개발/배포/운영 일관성

---

**이렇게 구성하면, 개발/운영/확장/테스트/문서화 모두
최소 시행착오로 효율적인 실전 파이프라인을 구축할 수 있습니다.**
