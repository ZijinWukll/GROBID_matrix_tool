from datetime import datetime, timezone, timedelta


BEIJING_TZ = timezone(timedelta(hours=8))


def now_beijing_iso_no_tz():
    """
    返回不带时区的北京时间 ISO 字符串。
    例如：20260604_173059
    """
    return datetime.now(BEIJING_TZ).strftime("%Y%m%d_%H%M%S")

if __name__ == '__main__':
    print(now_beijing_iso_no_tz())
