#!/usr/bin/env python3
"""Generate a rolling 31-day Osaka weather calendar (ICS).

Older past days use Open-Meteo Historical Weather (reanalysis).
The most recent five past days use Open-Meteo's recent forecast archive,
because the historical reanalysis endpoint can have a several-day delay.
These are model/reanalysis products, not raw JMA station observations.
"""
from datetime import date, timedelta, datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json

LAT = 34.6937
LON = 135.5023
TZ = "Asia/Tokyo"
OUT = "osaka-weather.ics"

WEATHER = {
    0: ("☀️", "晴朗"), 1: ("🌤️", "大致晴朗"), 2: ("⛅", "局部多云"),
    3: ("☁️", "阴天"), 45: ("🌫️", "雾"), 48: ("🌫️", "雾凇"),
    51: ("🌦️", "毛毛雨"), 53: ("🌦️", "中等毛毛雨"), 55: ("🌧️", "强毛毛雨"),
    56: ("🌧️", "冻毛毛雨"), 57: ("🌧️", "强冻毛毛雨"),
    61: ("🌦️", "小雨"), 63: ("🌧️", "中雨"), 65: ("🌧️", "大雨"),
    66: ("🌧️", "冻雨"), 67: ("🌧️", "强冻雨"),
    71: ("🌨️", "小雪"), 73: ("🌨️", "中雪"), 75: ("❄️", "大雪"),
    77: ("🌨️", "雪粒"), 80: ("🌦️", "小阵雨"), 81: ("🌧️", "阵雨"),
    82: ("⛈️", "强阵雨"), 85: ("🌨️", "小阵雪"), 86: ("❄️", "强阵雪"),
    95: ("⛈️", "雷暴"), 96: ("⛈️", "雷暴伴小冰雹"), 99: ("⛈️", "雷暴伴大冰雹"),
}

def get_json(url):
    req = Request(url, headers={"User-Agent": "OsakaWeatherCalendar/1.0"})
    with urlopen(req, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))

def api_url(base, params):
    return base + "?" + urlencode(params)

def weather_info(code):
    try:
        return WEATHER.get(int(code), ("🌡️", "天气状况"))
    except (TypeError, ValueError):
        return ("🌡️", "天气状况")

def escape_ics(s):
    return str(s).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

def fold_line(line, limit=70):
    out, current, count = [], "", 0
    for ch in line:
        n = len(ch.encode("utf-8"))
        if count + n > limit:
            out.append(current)
            current, count = " " + ch, 1 + n
        else:
            current += ch
            count += n
    out.append(current)
    return "\r\n".join(out)

def event(day, row, source):
    code, high, low = row if row else (None, None, None)
    icon, desc = weather_info(code)
    high_s = "—" if high is None else f"{round(float(high))}°C"
    low_s = "—" if low is None else f"{round(float(low))}°C"
    summary = f"{icon} 大阪天气｜{desc}｜最高 {high_s} / 最低 {low_s}"
    description = (
        f"地区：大阪市\\n天气：{desc}\\n最高气温：{high_s}\\n最低气温：{low_s}\\n"
        f"数据来源：Open-Meteo（{source}）\\n"
        "说明：历史值为再分析/模型估算，不是气象台观测站原始实测记录。"
        if day < today_jst() else
        f"地区：大阪市\\n天气：{desc}\\n最高气温：{high_s}\\n最低气温：{low_s}\\n"
        "数据来源：Open-Meteo 天气预报"
    )
    uid = f"osaka-weather-{day.isoformat()}@osaka-weather-calendar"
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return [
        "BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{dtstamp}",
        f"DTSTART;VALUE=DATE:{day.strftime('%Y%m%d')}",
        f"DTEND;VALUE=DATE:{(day + timedelta(days=1)).strftime('%Y%m%d')}",
        f"SUMMARY:{escape_ics(summary)}", f"DESCRIPTION:{escape_ics(description)}",
        "TRANSP:TRANSPARENT", "END:VEVENT",
    ]

def today_jst():
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo(TZ)).date()

def read_daily(data):
    daily = data.get("daily", {})
    result = {}
    times = daily.get("time", [])
    for i, ds in enumerate(times):
        result[date.fromisoformat(ds)] = (
            daily.get("weather_code", [None] * len(times))[i],
            daily.get("temperature_2m_max", [None] * len(times))[i],
            daily.get("temperature_2m_min", [None] * len(times))[i],
        )
    return result

def main():
    today = today_jst()
    past_start, past_end, future_end = today - timedelta(days=15), today - timedelta(days=1), today + timedelta(days=15)
    data_by_day = {}
    sources = {}

    # Older past dates (ending six days ago) from the historical reanalysis archive.
    older_end = today - timedelta(days=6)
    if past_start <= older_end:
        params = {
            "latitude": LAT, "longitude": LON,
            "start_date": past_start.isoformat(), "end_date": older_end.isoformat(),
            "daily": "weather_code,temperature_2m_max,temperature_2m_min",
            "timezone": TZ, "temperature_unit": "celsius",
        }
        data_by_day.update(read_daily(get_json(api_url("https://archive-api.open-meteo.com/v1/archive", params))))
        sources.update({d: "历史再分析" for d in data_by_day})

    # Recent past and forecast, avoiding the historical archive's normal publication delay.
    params = {
        "latitude": LAT, "longitude": LON,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min",
        "timezone": TZ, "temperature_unit": "celsius",
        "past_days": 5, "forecast_days": 16,
    }
    recent_and_forecast = read_daily(get_json(api_url("https://api.open-meteo.com/v1/forecast", params)))
    for d, row in recent_and_forecast.items():
        if today - timedelta(days=5) <= d <= future_end:
            data_by_day[d] = row
            sources[d] = "近期模型数据" if d < today else "天气预报"

    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0",
        "PRODID:-//Osaka Weather Calendar//ZH", "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH", "X-WR-CALNAME:大阪天气",
        "X-WR-TIMEZONE:Asia/Tokyo", "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
    ]
    day = past_start
    while day <= future_end:
        lines.extend(event(day, data_by_day.get(day), sources.get(day, "数据暂缺")))
        day += timedelta(days=1)
    lines.append("END:VCALENDAR")
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        f.write("\r\n".join(fold_line(line) for line in lines) + "\r\n")
    print(f"Created {OUT}: {past_start} through {future_end}; events={(future_end-past_start).days+1}")

if __name__ == "__main__":
    main()

# Workflow trigger refresh: regenerate the feed after initial repository setup.
