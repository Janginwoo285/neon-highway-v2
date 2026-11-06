"""Explainable statistics-based forecast. Not an AI/ML model."""
from datetime import date


def next_month(period: str) -> str:
    year, month = map(int, period.split('-'))
    return f'{year+1}-01' if month == 12 else f'{year}-{month+1:02d}'


def forecast(records: list[dict], method: str = 'weighted') -> tuple[int, dict]:
    if len(records) < 3:
        raise ValueError('최소 3개월의 데이터가 필요합니다.')
    records = sorted(records, key=lambda r: r['period'])
    # Demand signal = 0.4 sales + 0.6 dealer orders. This is a demonstration assumption.
    vals = [0.4 * r['sales'] + 0.6 * r['dealer_orders'] for r in records]
    if method == 'weighted':
        tail = vals[-3:]
        predicted = 0.2 * tail[0] + 0.3 * tail[1] + 0.5 * tail[2]
        notes = '최근 3개월 가중평균(20% / 30% / 50%)과 판매 40%·딜러 주문 60% 합성 — 실습용 가정'
    elif method == 'trend':
        v = vals[-min(6,len(vals)):]
        n = len(v)
        xs = list(range(n))
        xm = sum(xs)/n
        ym = sum(v)/n
        denom = sum((x-xm)**2 for x in xs)
        slope = sum((x-xm)*(y-ym) for x,y in zip(xs,v))/denom if denom else 0
        predicted = ym + slope * (n-xm)
        notes = '최근 최대 6개월 선형추세(단순 회귀) — 실습용 통계 모델, AI 아님'
    else:
        raise ValueError('지원하지 않는 예측 방법입니다.')
    return max(0, round(predicted)), {'method':method,'description':notes,'observations':len(records)}
