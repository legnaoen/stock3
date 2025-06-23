# [기능변경 2025-06-22] 최적화 결과(optimized_momentum_weights.csv의 best_row)를 실전 가중치(momentum_weights_active.csv)에 반영하는 스크립트
# - 실전 분석 파이프라인은 momentum_weights_active.csv만 참조
# - 실험/리포트/백테스트는 optimized_momentum_weights.csv 등 별도 파일만 참조

import pandas as pd
from datetime import datetime

def apply_recommended_weights(active_path='results/momentum_weights_active.csv', opt_path='results/optimized_momentum_weights.csv'):
    """
    optimized_momentum_weights.csv의 best_row를 실전 가중치(momentum_weights_active.csv)에 반영하고,
    반영된 최신 row(dict)를 반환한다.
    """
    # 파일 읽기
    try:
        df = pd.read_csv(active_path)
    except FileNotFoundError:
        # 파일이 없으면 헤더만 생성
        df = pd.DataFrame(columns=[
            'timestamp','tag','is_active','comment',
            'price_momentum_1d','price_momentum_3d','price_momentum_5d','price_momentum_10d',
            'volume_momentum_1d','volume_momentum_3d','volume_momentum_5d',
            'leader_momentum','leader_count','rsi_value'
        ])

    df2 = pd.read_csv(opt_path)

    # 모든 is_active=0 처리
    if not df.empty:
        df['is_active'] = 0

    # best_row 추출(최고 성과 기준)
    best_row = df2.iloc[0]

    # 메타 필드 준비
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    tag = '추천'
    comment = '최적화 추천 가중치'

    # 가중치 필드만 추출(순서 맞춤)
    fields = [
        'price_momentum_1d','price_momentum_3d','price_momentum_5d','price_momentum_10d',
        'volume_momentum_1d','volume_momentum_3d','volume_momentum_5d',
        'leader_momentum','leader_count','rsi_value'
    ]
    row = [timestamp, tag, 1, comment] + [best_row.get(f, 0.0) for f in fields]

    # 새 row 추가
    df.loc[len(df)] = row

    # 저장
    df.to_csv(active_path, index=False)

    # 최신 row 반환(dict)
    latest_row = df.iloc[-1].to_dict()
    return latest_row

if __name__ == "__main__":
    latest_row = apply_recommended_weights()
    print('최적화 추천 가중치가 momentum_weights_active.csv에 반영되었습니다.')
    print('반영된 가중치:', latest_row) 