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
    FOREIGN KEY (theme_id) REFERENCES theme_master(theme_id)
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
    FOREIGN KEY (industry_id) REFERENCES industry_master(industry_id)
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