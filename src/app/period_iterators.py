from datetime import datetime, timedelta
from typing import Iterable


class PeriodIterators:
    @staticmethod
    def month_iter(start_dt: datetime, end_dt: datetime) -> Iterable[datetime]:
        cur = start_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        while cur <= end_dt:
            yield cur
            year = cur.year + (1 if cur.month == 12 else 0)
            month = 1 if cur.month == 12 else cur.month + 1
            cur = cur.replace(year=year, month=month)

    @staticmethod
    def week_iter(start_dt: datetime, end_dt: datetime) -> Iterable[datetime]:
        cur = (start_dt - timedelta(days=start_dt.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        while cur <= end_dt:
            yield cur
            cur = cur + timedelta(weeks=1)

    @staticmethod
    def day_iter(start_dt: datetime, end_dt: datetime) -> Iterable[datetime]:
        cur = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        while cur <= end_dt:
            yield cur
            cur = cur + timedelta(days=1)

    @staticmethod
    def hour_iter(start_dt: datetime, end_dt: datetime) -> Iterable[datetime]:
        cur = start_dt.replace(minute=0, second=0, microsecond=0)
        while cur <= end_dt:
            yield cur
            cur = cur + timedelta(hours=1)
