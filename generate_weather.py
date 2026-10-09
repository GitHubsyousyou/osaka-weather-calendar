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
    0: ("☀️", "快晴"),
    1: ("🌤️", "晴れ"),
    2: ("⛅", "晴れ時々くもり"),
    3: ("☁️", "くもり"),
    45: ("🌫️", "霧"),
    48: ("🌫️", "霧氷"),
    51: ("🌦️", "弱い霧雨"),
    53: ("🌦️", "霧雨"),
    55: ("🌧️", "強い霧雨"),
    56: ("🌧️", "弱い着氷性の霧雨"),
    57: ("🌧️", "強い着氷性の霧雨"),
    61: ("🌦️", "弱い雨"),
    63: ("🌧️", "雨"),
    65: ("🌧️", "強い雨"),
    66: ("🌧️", "弱い着氷性の雨"),
    67: ("🌧️", "強い着氷性の雨"),
    71: ("🌨️", "弱い雪"),
    73: ("🌨️", "雪"),
    75: ("❄️", "大雪"),
    77: ("🌨️", "細かい雪"),
    80: ("🌦️", "弱いにわか雨"),
    81: ("🌧️", "にわか雨"),
    82: ("⛈️", "激しいにわか雨"),
    85: ("🌨️", "弱いにわか雪"),
    86: ("❄️", "強いにわか雪"),
    95: ("⛈️", "雷雨"),
    96: ("⛈️", "ひょうを伴う雷雨"),
    99: ("⛈️", "強いひょうを伴う雷雨"),
}

def get_json(url):
    req = Request(url, headers={"User-Agent": "OsakaWeatherCalendar/1.0"})
    with urlopen(req, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))

def api_url(base, params):
    return base + "?" + urlencode(params)

def weather_info(code):
    try:
        return WEATHER.get(int(code), ("🌡️", "天気情報"))
    except (TypeError, ValueError):
        return ("🌡️", "天気情報")

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

def moon_info(day):
    # Approximate lunar age/phase using a known new-moon epoch and mean synodic month.
    epoch = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc).date()
    age = ((day - epoch).days + 0.5) % 29.530588853
    phase = (age / 29.530588853) % 1.0
    illumination = (1 - __import__("math").cos(2 * __import__("math").pi * phase)) * 50
    if phase < 0.03 or phase >= 0.97:
        name = "新月"
    elif phase < 0.22:
        name = "三日月～上弦前"
    elif phase < 0.28:
        name = "上弦"
    elif phase < 0.47:
        name = "満ちていく月"
    elif phase < 0.53:
        name = "満月"
    elif phase < 0.72:
        name = "欠けていく月"
    elif phase < 0.78:
        name = "下弦"
    else:
        name = "有明月"
    return age, illumination, name

def event(day, row, source):
    values = row if row else (None,) * 11
    code, high, low, rain, humidity, sunrise, sunset, feels_high, feels_low, wind, uv, pressure = values
    icon, desc = weather_info(code)
    high_s = "—" if high is None else f"{round(float(high))}°C"
    low_s = "—" if low is None else f"{round(float(low))}°C"
    rain_s = "—" if rain is None else f"{round(float(rain))}%"
    humidity_s = "—" if humidity is None else f"{round(float(humidity))}%"
    sunrise_s = "—" if not sunrise else str(sunrise)[11:16]
    sunset_s = "—" if not sunset else str(sunset)[11:16]
    feel_s = "—" if feels_high is None or feels_low is None else f"{round(float(feels_high))}°C～{round(float(feels_low))}°C"
    wind_s = "—" if wind is None else f"{round(float(wind))} km/h"
    uv_s = "—" if uv is None else f"{float(uv):.1f}"
    pressure_s = "—" if pressure is None else f"{round(float(pressure))} hPa"
    moon_age, moon_light, moon_name = moon_info(day)
    summary = f"{icon} {high_s}～{low_s}"
    description = (
        f"{icon} {desc}（大阪市）\\n"
        f"🌡️ 気温：最高 {high_s} ／ 最低 {low_s}\\n"
        f"🧍 体感温度：{feel_s}\\n"
        f"🌧️ 降水確率：{rain_s}\\n"
        f"💧 湿度（日平均）：{humidity_s}\\n"
        f"💨 最大風速：{wind_s}\\n"
        f"☀️ UV指数（最大）：{uv_s}\\n"
        f"🌅 日の出：{sunrise_s} ／ 日の入り：{sunset_s}\\n"
        f"🌓 月相：{moon_name} ／ 月齢：約 {moon_age:.1f} 日 ／ 照明率：約 {moon_light:.0f}%\\n"
        f"🌡️ 気圧（海面更正・日平均）：{pressure_s}\\n\\n"
        f"データ：Open-Meteo（{source}）"
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
    hourly = data.get("hourly", {})
    grouped = {}
    for field in ("relative_humidity_2m", "pressure_msl"):
        for timestamp, value in zip(hourly.get("time", []), hourly.get(field, [])):
            if value is not None:
                grouped.setdefault((date.fromisoformat(timestamp[:10]), field), []).append(float(value))
    def daily_value(field, i):
        values = daily.get(field, [])
        return values[i] if i < len(values) else None
    result = {}
    times = daily.get("time", [])
    for i, ds in enumerate(times):
        day = date.fromisoformat(ds)
        humidities = grouped.get((day, "relative_humidity_2m"), [])
        pressures = grouped.get((day, "pressure_msl"), [])
        humidity = round(sum(humidities) / len(humidities)) if humidities else None
        pressure = sum(pressures) / len(pressures) if pressures else None
        result[day] = (
            daily_value("weather_code", i),
            daily_value("temperature_2m_max", i),
            daily_value("temperature_2m_min", i),
            daily_value("precipitation_probability_max", i),
            humidity,
            daily_value("sunrise", i),
            daily_value("sunset", i),
            daily_value("apparent_temperature_max", i),
            daily_value("apparent_temperature_min", i),
            daily_value("wind_speed_10m_max", i),
            daily_value("uv_index_max", i),
            pressure,
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
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min,precipitation_probability_max,wind_speed_10m_max,uv_index_max,sunrise,sunset",
            "hourly": "relative_humidity_2m,pressure_msl",
            "timezone": TZ, "temperature_unit": "celsius",
        }
        data_by_day.update(read_daily(get_json(api_url("https://archive-api.open-meteo.com/v1/archive", params))))
        sources.update({d: "過去の再解析データ" for d in data_by_day})

    # Recent past and forecast, avoiding the historical archive's normal publication delay.
    params = {
        "latitude": LAT, "longitude": LON,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min,precipitation_probability_max,wind_speed_10m_max,uv_index_max,sunrise,sunset",
        "hourly": "relative_humidity_2m,pressure_msl",
        "timezone": TZ, "temperature_unit": "celsius",
        "past_days": 5, "forecast_days": 16,
    }
    recent_and_forecast = read_daily(get_json(api_url("https://api.open-meteo.com/v1/forecast", params)))
    for d, row in recent_and_forecast.items():
        if today - timedelta(days=5) <= d <= future_end:
            data_by_day[d] = row
            sources[d] = "直近のモデルデータ" if d < today else "天気予報"

    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0",
        "PRODID:-//Osaka Weather Calendar//JA", "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH", "X-WR-CALNAME:大阪の天気",
        "X-WR-TIMEZONE:Asia/Tokyo", "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
    ]
    day = past_start
    while day <= future_end:
        lines.extend(event(day, data_by_day.get(day), sources.get(day, "データなし")))
        day += timedelta(days=1)
    lines.append("END:VCALENDAR")
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        f.write("\r\n".join(fold_line(line) for line in lines) + "\r\n")
    print(f"Created {OUT}: {past_start} through {future_end}; events={(future_end-past_start).days+1}")

if __name__ == "__main__":
    main()

# Workflow trigger refresh: regenerate the feed after initial repository setup.
