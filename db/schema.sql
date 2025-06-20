-- Stocks: 전체 상장 종목 마스터 테이블
CREATE TABLE IF NOT EXISTS Stocks (
    stock_code VARCHAR(10) PRIMARY KEY, -- 종목코드
    stock_name VARCHAR(100) NOT NULL,   -- 종목명
    market_type VARCHAR(10) NOT NULL,   -- 시장구분(KOSPI/KOSDAQ)
    listed_date DATE,                   -- 상장일(선택)
    is_active BOOLEAN DEFAULT TRUE,     -- 상장/거래정지 여부
    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스(검색 최적화)
CREATE INDEX IF NOT EXISTS idx_stocks_name ON Stocks(stock_name);
CREATE INDEX IF NOT EXISTS idx_stocks_market ON Stocks(market_type);

-- Industries: 업종 마스터 테이블
CREATE TABLE IF NOT EXISTS Industries (
    industry_code VARCHAR(20) PRIMARY KEY, -- 업종코드
    industry_name VARCHAR(100) NOT NULL,   -- 업종명
    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Themes: 테마 마스터 테이블
CREATE TABLE IF NOT EXISTS Themes (
    theme_id INTEGER PRIMARY KEY AUTOINCREMENT, -- 테마ID
    theme_name VARCHAR(100) UNIQUE NOT NULL,    -- 테마명
    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- StockIndustries: 종목-업종 매핑 (다대다)
CREATE TABLE IF NOT EXISTS StockIndustries (
    stock_code VARCHAR(10) NOT NULL,
    industry_code VARCHAR(20) NOT NULL,
    PRIMARY KEY (stock_code, industry_code),
    FOREIGN KEY (stock_code) REFERENCES Stocks(stock_code),
    FOREIGN KEY (industry_code) REFERENCES Industries(industry_code)
);

-- StockThemes: 종목-테마 매핑 (다대다, 수집일 포함)
CREATE TABLE IF NOT EXISTS StockThemes (
    stock_code VARCHAR(10) NOT NULL,
    theme_id INTEGER NOT NULL,
    collected_at DATE NOT NULL, -- 수집일
    PRIMARY KEY (stock_code, theme_id, collected_at),
    FOREIGN KEY (stock_code) REFERENCES Stocks(stock_code),
    FOREIGN KEY (theme_id) REFERENCES Themes(theme_id)
);

-- 테마 마스터 테이블
CREATE TABLE IF NOT EXISTS theme_master (
    theme_id INTEGER PRIMARY KEY AUTOINCREMENT,
    theme_name TEXT NOT NULL,
    category TEXT DEFAULT 'THEME',  -- THEME or INDUSTRY
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(theme_name)
);

-- 테마-종목 매핑 테이블
CREATE TABLE IF NOT EXISTS theme_stock_mapping (
    theme_id INTEGER,
    stock_code TEXT,
    is_leader BOOLEAN DEFAULT FALSE,  -- 해당 테마의 주도주 여부
    weight FLOAT DEFAULT 0,  -- 테마 내 비중
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (theme_id, stock_code),
    FOREIGN KEY (theme_id) REFERENCES theme_master(theme_id),
    FOREIGN KEY (stock_code) REFERENCES stock_master(stock_code)
);

-- 테마 일별 성과 테이블
CREATE TABLE IF NOT EXISTS theme_daily_performance (
    theme_id INTEGER,
    date TEXT,
    price_change_ratio FLOAT,  -- 시가총액 가중 등락률
    volume INTEGER,  -- 테마 전체 거래량
    market_cap BIGINT,  -- 테마 전체 시가총액
    trading_value BIGINT,  -- 테마 전체 거래대금
    leader_stock_codes TEXT,  -- 주도주 종목코드들 (콤마로 구분)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (theme_id, date),
    FOREIGN KEY (theme_id) REFERENCES theme_master(theme_id)
);

-- 업종 마스터 테이블 (KRX/WICS 기준)
CREATE TABLE IF NOT EXISTS industry_master (
    industry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    industry_code TEXT UNIQUE,  -- KRX/WICS 업종코드
    industry_name TEXT NOT NULL,
    level INTEGER,  -- 업종 분류 레벨 (1: 대분류, 2: 중분류, 3: 소분류)
    parent_id INTEGER,  -- 상위 업종 ID
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES industry_master(industry_id)
);

-- 업종-종목 매핑 테이블
CREATE TABLE IF NOT EXISTS industry_stock_mapping (
    industry_id INTEGER,
    stock_code TEXT,
    weight FLOAT DEFAULT 0,  -- 업종 내 비중
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (industry_id, stock_code),
    FOREIGN KEY (industry_id) REFERENCES industry_master(industry_id),
    FOREIGN KEY (stock_code) REFERENCES stock_master(stock_code)
);

-- 업종 일별 성과 테이블
CREATE TABLE IF NOT EXISTS industry_daily_performance (
    industry_id INTEGER,
    date TEXT,
    price_change_ratio FLOAT,  -- 시가총액 가중 등락률
    volume INTEGER,  -- 업종 전체 거래량
    market_cap BIGINT,  -- 업종 전체 시가총액
    trading_value BIGINT,  -- 업종 전체 거래대금
    leader_stock_codes TEXT,  -- 시가총액 상위 종목코드들 (콤마로 구분)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (industry_id, date),
    FOREIGN KEY (industry_id) REFERENCES industry_master(industry_id)
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_theme_daily_date ON theme_daily_performance(date);
CREATE INDEX IF NOT EXISTS idx_industry_daily_date ON industry_daily_performance(date);
CREATE INDEX IF NOT EXISTS idx_theme_stock_theme_id ON theme_stock_mapping(theme_id);
CREATE INDEX IF NOT EXISTS idx_industry_stock_industry_id ON industry_stock_mapping(industry_id);

-- DailyStocks: 일별 주가 데이터
CREATE TABLE IF NOT EXISTS DailyStocks (
    stock_code VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    open_price INTEGER,  -- 시가
    high_price INTEGER,  -- 고가
    low_price INTEGER,   -- 저가
    close_price INTEGER, -- 종가
    volume INTEGER,      -- 거래량
    trading_value BIGINT,  -- 거래대금
    market_cap BIGINT,    -- 시가총액
    price_change_ratio FLOAT,  -- 전일 대비 등락률
    PRIMARY KEY (stock_code, date),
    FOREIGN KEY (stock_code) REFERENCES Stocks(stock_code)
);

-- 인덱스 추가
CREATE INDEX IF NOT EXISTS idx_daily_stocks_date ON DailyStocks(date);
CREATE INDEX IF NOT EXISTS idx_daily_stocks_code_date ON DailyStocks(stock_code, date);
