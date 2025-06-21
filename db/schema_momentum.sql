-- 테마/업종 모멘텀 분석 결과 테이블
CREATE TABLE IF NOT EXISTS momentum_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL,  -- theme_id 또는 industry_id
    target_type TEXT NOT NULL,  -- 'THEME' 또는 'INDUSTRY'
    date TEXT NOT NULL,
    
    -- 가격 모멘텀
    price_momentum_1d FLOAT,  -- 1일 수익률
    price_momentum_3d FLOAT,  -- 3일 수익률
    price_momentum_5d FLOAT,  -- 5일 수익률
    price_momentum_10d FLOAT, -- 10일 수익률
    
    -- 거래대금 모멘텀
    volume_momentum_1d FLOAT,  -- 1일 거래대금 증감률
    volume_momentum_3d FLOAT,  -- 3일 평균 거래대금 증감률
    volume_momentum_5d FLOAT,  -- 5일 평균 거래대금 증감률
    
    -- 추세 강도
    rsi_value FLOAT,  -- RSI (14일)
    trend_score INTEGER,  -- 종합 추세 강도 점수 (0-100)
    
    -- 주도주 분석
    leader_count INTEGER,  -- 주도주 수
    leader_momentum FLOAT, -- 주도주 평균 수익률
    
    -- 생명력 지표
    momentum_power INTEGER,  -- 모멘텀 생명력 점수 (0-100)
    expected_duration INTEGER,  -- 예상 지속 기간(일)
    success_probability FLOAT,  -- 추가 상승 확률
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(target_id, target_type, date)
);

-- 투자 의견 테이블
CREATE TABLE IF NOT EXISTS investment_opinion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL,  -- theme_id 또는 industry_id
    target_type TEXT NOT NULL,  -- 'THEME' 또는 'INDUSTRY'
    date TEXT NOT NULL,
    
    opinion_type TEXT,  -- 'STRONG_BUY', 'BUY', 'HOLD', 'SELL'
    confidence_score INTEGER,  -- 확신도 점수 (0-100)
    expected_return FLOAT,  -- 예상 수익률
    expected_period INTEGER,  -- 예상 투자 기간(일)
    
    reason_summary TEXT,  -- 투자 의견 요약
    risk_factors TEXT,  -- 주의해야 할 위험 요소
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(target_id, target_type, date)
); 