import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Optional

def parse_article_datetime(val: Any) -> Optional[datetime.datetime]:
    """
    다양한 날짜 포맷(RFC 2822, ISO 8601 등)을 안전하게 파싱하여 UTC datetime 객체로 반환합니다.
    bcrypt, database 드라이버 등 무거운 외부 의존성이 전혀 없는 순수 표준 라이브러리 기반 유틸리티입니다.
    """
    if not val or not isinstance(val, str):
        return None
    val = val.strip()

    # 1. RFC 2822 포맷 시도 (예: 'Sun, 22 Nov 2026 17:00:00 +0900')
    try:
        dt = parsedate_to_datetime(val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except Exception:
        pass

    # 2. ISO 8601 및 일반 날짜/시간 포맷 시도
    formats = (
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d',
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%S'
    )
    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(val, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt
        except Exception:
            continue

    return None
