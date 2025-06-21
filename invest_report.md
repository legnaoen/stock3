
# 업종/테마 모멘텀 분석 시스템 구축 계획서

## 1. 신규 데이터베이스 테이블 설계

### 1.1 모멘텀 분석 테이블
```sql
-- 테마/업종 모멘텀 분석 결과 테이블
CREATE TABLE momentum_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER,  -- theme_id 또는 industry_id
    target_type TEXT,  -- 'THEME' 또는 'INDUSTRY'
    date TEXT,
    
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
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 투자 의견 테이블
CREATE TABLE investment_opinion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER,  -- theme_id 또는 industry_id
    target_type TEXT,  -- 'THEME' 또는 'INDUSTRY'
    date TEXT,
    
    opinion_type TEXT,  -- 'STRONG_BUY', 'BUY', 'HOLD', 'SELL'
    confidence_score INTEGER,  -- 확신도 점수 (0-100)
    expected_return FLOAT,  -- 예상 수익률
    expected_period INTEGER,  -- 예상 투자 기간(일)
    
    reason_summary TEXT,  -- 투자 의견 요약
    risk_factors TEXT,  -- 주의해야 할 위험 요소
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## 2. 분석 지표 계산 방법

### 2.1 추세 강도 지표

1. **RSI (Relative Strength Index)**
```python
def calculate_rsi(price_changes, period=14):
    gains = [max(change, 0) for change in price_changes]
    losses = [-min(change, 0) for change in price_changes]
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    rs = avg_gain / avg_loss if avg_loss != 0 else 0
    rsi = 100 - (100 / (1 + rs))
    return rsi
```

2. **종합 추세 강도 점수**
```python
def calculate_trend_score(data):
    score = 0
    
    # 가격 모멘텀 (40점)
    price_score = (
        data['price_momentum_1d'] * 0.2 +
        data['price_momentum_3d'] * 0.3 +
        data['price_momentum_5d'] * 0.3 +
        data['price_momentum_10d'] * 0.2
    ) * 40
    
    # 거래대금 모멘텀 (30점)
    volume_score = (
        data['volume_momentum_1d'] * 0.3 +
        data['volume_momentum_3d'] * 0.4 +
        data['volume_momentum_5d'] * 0.3
    ) * 30
    
    # 주도주 강도 (30점)
    leader_score = (
        data['leader_momentum'] * 0.6 +
        (data['leader_count'] / 10) * 0.4
    ) * 30
    
    return price_score + volume_score + leader_score
```

### 2.2 모멘텀 생명력 지표

```python
def calculate_momentum_power(data):
    power_score = 0
    
    # 거래대금 지속성 (40점)
    volume_sustainability = analyze_volume_trend(data)
    
    # 주도주 확산도 (30점)
    leader_expansion = analyze_leader_expansion(data)
    
    # 패턴 매칭 기반 예측 (30점)
    pattern_prediction = analyze_similar_patterns(data)
    
    return power_score
```

## 3. 투자 의견 생성 로직

### 3.1 투자 의견 결정 기준

```python
def generate_investment_opinion(analysis_data):
    opinion = {
        'opinion_type': None,
        'confidence_score': 0,
        'expected_return': 0,
        'expected_period': 0,
        'reason_summary': '',
        'risk_factors': []
    }
    
    # 1. 추세 강도에 따른 기본 의견
    if analysis_data['trend_score'] >= 80:
        opinion['opinion_type'] = 'STRONG_BUY'
    elif analysis_data['trend_score'] >= 60:
        opinion['opinion_type'] = 'BUY'
    elif analysis_data['trend_score'] >= 40:
        opinion['opinion_type'] = 'HOLD'
    else:
        opinion['opinion_type'] = 'SELL'
    
    # 2. 확신도 점수 계산
    opinion['confidence_score'] = calculate_confidence(analysis_data)
    
    # 3. 예상 수익률 계산
    opinion['expected_return'] = estimate_return(analysis_data)
    
    # 4. 투자 기간 추정
    opinion['expected_period'] = estimate_duration(analysis_data)
    
    return opinion
```

### 3.2 투자 의견 템플릿

```python
def generate_opinion_text(opinion_data, analysis_data):
    template = f"""
    [{opinion_data['opinion_type']}] {analysis_data['name']}
    
    투자의견: {get_opinion_text(opinion_data['opinion_type'])}
    예상수익률: {opinion_data['expected_return']}%
    투자기간: {opinion_data['expected_period']}일
    
    핵심 포인트:
    1. 추세 강도: {analysis_data['trend_score']}/100
       - 가격 모멘텀: {format_momentum(analysis_data['price_momentum'])}
       - 거래대금 증감: {format_volume(analysis_data['volume_momentum'])}
    
    2. 모멘텀 생명력
       - 지속가능성: {analysis_data['momentum_power']}/100
       - 예상 지속기간: {analysis_data['expected_duration']}일
       - 성공확률: {analysis_data['success_probability']}%
    
    3. 주도주 동향
       - 주도주 수: {analysis_data['leader_count']}개
       - 평균 수익률: {analysis_data['leader_momentum']}%
    
    투자 전략:
    {generate_strategy_text(opinion_data, analysis_data)}
    
    위험 요인:
    {generate_risk_text(opinion_data['risk_factors'])}
    """
    return template
```

## 4. 구현 계획

### 4.1 Phase 1: 데이터 수집 및 저장 (1주)
- 신규 테이블 생성
- 기존 데이터 마이그레이션
- 데이터 수집/저장 프로세스 구축

### 4.2 Phase 2: 분석 엔진 구현 (2주)
- 모멘텀 지표 계산 로직 구현
- 패턴 분석 엔진 개발
- 백테스팅 및 정확도 검증

### 4.3 Phase 3: 투자 의견 생성 시스템 (1주)
- 투자 의견 생성 로직 구현
- 템플릿 시스템 개발
- 검증 및 피드백 반영

### 4.4 Phase 4: UI/UX 개발 (1주)
- 대시보드 디자인
- 차트 및 시각화 구현
- 사용자 인터페이스 개발

## 5. 예상 결과물

### 5.1 일간 모멘텀 리포트
```
[2025-06-19 업종/테마 모멘텀 리포트]

강세 지속 그룹
1. AI 반도체
   - 추세 강도: 92/100
   - 투자의견: Strong Buy
   - 예상수익률: +15%
   - 주도주: A반도체(+8%), B전자(+5%)

조정 임박 그룹
2. 2차전지
   - 추세 강도: 75/100 (고점 대비 -10)
   - 투자의견: Hold
   - 주의사항: 거래대금 감소 추세
...
```

### 5.2 모멘텀 대시보드
- 실시간 추세 강도 모니터링
- 주요 지표 시각화
- 투자 의견 및 전략 제시
- 위험 신호 알림

## 6. 성과 측정 지표

1. **예측 정확도**
   - 투자의견 적중률
   - 예상수익률 달성도
   - 지속기간 예측 정확도

2. **사용자 가치**
   - 실제 투자 적용 가능성
   - 정보의 시의성
   - 분석 깊이와 통찰력



------------------------------

# 가중치 조정 방법에대한 의견 (후속 개발 기능)

네, 투자의견 성과 분석을 통한 가중치 자동 조정 시스템을 설계해보겠습니다.

# 투자의견 성과 분석 및 가중치 자동 조정 시스템

## 1. 가중치 관리를 위한 DB 설계

```sql
-- 가중치 설정 테이블
CREATE TABLE weight_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT,  -- 'PRICE', 'VOLUME', 'LEADER', 'PATTERN' 등
    parameter_name TEXT,  -- 구체적 파라미터명
    current_weight FLOAT,
    min_weight FLOAT,
    max_weight FLOAT,
    description TEXT,
    last_updated DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 투자의견 성과 기록 테이블
CREATE TABLE opinion_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opinion_id INTEGER,  -- investment_opinion 테이블의 FK
    target_id INTEGER,  -- theme_id 또는 industry_id
    target_type TEXT,   -- 'THEME' 또는 'INDUSTRY'
    
    -- 예측 데이터
    predicted_return FLOAT,
    predicted_period INTEGER,
    opinion_type TEXT,
    
    -- 실제 결과
    actual_return FLOAT,
    actual_period INTEGER,
    success_yn BOOLEAN,
    
    -- 예측 시점의 가중치 스냅샷
    weight_snapshot TEXT,  -- JSON 형태로 저장
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (opinion_id) REFERENCES investment_opinion(id)
);

-- 가중치 조정 이력 테이블
CREATE TABLE weight_adjustment_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    weight_id INTEGER,
    old_weight FLOAT,
    new_weight FLOAT,
    adjustment_reason TEXT,
    performance_metrics TEXT,  -- JSON 형태로 성과 지표 저장
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (weight_id) REFERENCES weight_settings(id)
);
```

## 2. 성과 분석 및 가중치 조정 로직

### 2.1 성과 측정 지표

```python
class PerformanceAnalyzer:
    def calculate_performance_metrics(self, period='1M'):
        """기간별 성과 지표 계산"""
        metrics = {
            'accuracy': {
                'overall': 0.0,
                'by_opinion_type': {},
                'by_sector': {}
            },
            'return_error': {
                'mae': 0.0,  # Mean Absolute Error
                'rmse': 0.0  # Root Mean Square Error
            },
            'timing_accuracy': {
                'direction': 0.0,  # 방향성 적중률
                'peak_timing': 0.0  # 고점/저점 타이밍 적중률
            }
        }
        
        # 성과 지표 계산 로직
        return metrics

    def analyze_weight_effectiveness(self):
        """가중치별 효과성 분석"""
        effectiveness = {
            'price_momentum': {
                'correlation': 0.0,
                'importance': 0.0
            },
            'volume_momentum': {
                'correlation': 0.0,
                'importance': 0.0
            },
            'leader_momentum': {
                'correlation': 0.0,
                'importance': 0.0
            }
        }
        
        return effectiveness
```

### 2.2 가중치 자동 조정 시스템

```python
class WeightOptimizer:
    def __init__(self):
        self.learning_rate = 0.01
        self.min_adjustment = 0.05
        self.max_adjustment = 0.20

    def optimize_weights(self, performance_metrics, current_weights):
        """성과 지표 기반 가중치 최적화"""
        adjustments = {}
        
        # 각 가중치별 조정값 계산
        for weight_name, current_value in current_weights.items():
            adjustment = self._calculate_adjustment(
                performance_metrics,
                weight_name,
                current_value
            )
            adjustments[weight_name] = adjustment
        
        return adjustments

    def _calculate_adjustment(self, metrics, weight_name, current_value):
        """개별 가중치 조정값 계산"""
        # 성과 지표 기반 조정 로직
        return adjustment_value
```

### 2.3 적응형 학습 시스템

```python
class AdaptiveLearningSystem:
    def __init__(self):
        self.performance_threshold = 0.7
        self.adjustment_period = '1M'
        self.min_samples = 100

    def evaluate_and_adjust(self):
        """정기적인 성과 평가 및 가중치 조정"""
        # 1. 성과 데이터 수집
        performance = self.performance_analyzer.calculate_performance_metrics(
            period=self.adjustment_period
        )
        
        # 2. 조정 필요성 판단
        if self._needs_adjustment(performance):
            # 3. 가중치 최적화
            new_weights = self.weight_optimizer.optimize_weights(
                performance,
                self.current_weights
            )
            
            # 4. 가중치 적용 및 기록
            self._apply_new_weights(new_weights)

    def _needs_adjustment(self, performance):
        """가중치 조정 필요성 판단"""
        if performance['accuracy']['overall'] < self.performance_threshold:
            return True
        return False
```

## 3. 구현 예시

### 3.1 투자의견 생성 시 가중치 적용

```python
def generate_investment_opinion(analysis_data):
    # 현재 가중치 설정 로드
    weights = load_current_weights()
    
    # 가중치 적용된 점수 계산
    trend_score = calculate_weighted_trend_score(analysis_data, weights)
    momentum_power = calculate_weighted_momentum_power(analysis_data, weights)
    
    # 투자의견 생성
    opinion = determine_opinion(trend_score, momentum_power, weights)
    
    # 가중치 스냅샷 저장
    save_weight_snapshot(opinion.id, weights)
    
    return opinion
```

### 3.2 정기적인 성과 분석 및 가중치 조정

```python
def periodic_weight_optimization():
    """월간 가중치 최적화 작업"""
    
    # 1. 성과 데이터 수집
    performance = analyze_monthly_performance()
    
    # 2. 가중치 효과성 분석
    weight_effectiveness = analyze_weight_effectiveness()
    
    # 3. 새로운 가중치 계산
    new_weights = calculate_optimal_weights(
        performance,
        weight_effectiveness
    )
    
    # 4. 가중치 조정 이력 저장
    save_weight_adjustment_history(new_weights)
    
    # 5. 새 가중치 적용
    apply_new_weights(new_weights)
```

## 4. 성과 리포트 예시

```python
def generate_performance_report():
    """월간 성과 분석 리포트 생성"""
    report = """
    [2025-06 투자의견 성과 분석 리포트]
    
    1. 종합 성과
       - 전체 적중률: 75.5% (전월 대비 +2.3%p)
       - 수익률 예측 정확도: 82.3%
       - 평균 기간 오차: 2.1일
    
    2. 유형별 성과
       - Strong Buy: 85.5% 적중
       - Buy: 72.3% 적중
       - Hold: 68.7% 적중
       - Sell: 77.8% 적중
    
    3. 가중치 조정 사항
       - 거래대금 모멘텀: 0.35 → 0.40 (+0.05)
       - 주도주 영향력: 0.25 → 0.30 (+0.05)
       - 패턴 매칭: 0.20 → 0.15 (-0.05)
    
    4. 조정 근거
       - 거래대금 지표의 예측력 향상
       - 주도주 모멘텀의 높은 상관관계
       - 패턴 매칭의 정확도 저하
    
    5. 다음 분석 주기: 2025-07-01
    """
    return report
```

## 5. 장점 및 기대효과

1. **데이터 기반 의사결정**
   - 객관적인 성과 측정
   - 체계적인 가중치 조정
   - 지속적인 성과 개선

2. **자동화된 학습 시스템**
   - 시장 상황 변화에 적응
   - 예측 정확도 향상
   - 운영 효율성 증가

3. **투명한 성과 관리**
   - 상세한 성과 분석
   - 조정 이력 추적
   - 개선 포인트 파악
