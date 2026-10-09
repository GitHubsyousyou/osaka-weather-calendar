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
    0: ("☀️", "Clear sky"),
    1: ("🌤️", "Mainly clear"),
    2: ("⛅", "Partly cloudy"),
    3: ("☁️", "Overcast"),
    45: ("🌫️", "Fog"),
    48: ("🌫️", "Depositing rime fog"),
    51: ("🌦️", "Light drizzle"),
    53: ("🌦️", "Moderate drizzle"),
    55: ("🌧️", "Dense drizzle"),
    56: ("🌧️", "Light freezing drizzle"),
    57: ("🌧️", "Dense freezing drizzle"),
    61: ("🌦️", "Slight rain"),
    63: ("🌧️", "Moderate rain"),
    65: ("🌧️", "Heavy rain"),
    66: ("🌧️", "Light freezing rain"),
    67: ("🌧️", "Heavy freezing rain"),
    71: ("🌨️", "Slight snow"),
    73: ("🌨️", "Moderate snow"),
    75: ("❄️", "Heavy snow"),
    77: ("🌨️", "Snow grains"),
    80: ("🌦️", "Slight rain showers"),
    81: ("🌧️", "Moderate rain showers"),
    82: ("⛈️", "Violent rain showers"),
    85: ("🌨️", "Slight snow showers"),
    86: ("❄️", "Heavy snow showers"),
    95: ("⛈️", "Thunderstorm"),
    96: ("⛈️", "Thunderstorm with slight hail"),
    99: ("⛈️", "Thunderstorm with heavy hail"),
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
    code, high, low, rain, humidity, sunrise, sunset = row if row else (None, None, None, None, None, None, None)
    icon, desc = weather_info(code)
    high_s = "—" if high is None else f"{round(float(high))}°C"
    low_s = "—" if low is None else f"{round(float(low))}°C"
    rain_s = "—" if rain is None else f"{round(float(rain))}%"
    humidity_s = "—" if humidity is None else f"{round(float(humidity))}%"
    sunrise_s = "—" if not sunrise else str(sunrise)[11:16]
    sunset_s = "—" if not sunset else str(sunset)[11:16]
    summary = f"{icon} {high_s}～{low_s}"
    description = (
        f"{icon} {desc}\n"
        f"🌡️ High {high_s} · Low {low_s}\n"
        f"🌧️ Precipitation chance {rain_s}\n"
        f"🌅 Sunrise {sunrise_s} · Sunset {sunset_s}\n"
        f"💧 Humidity {humidity_s}\n\n"
        f"Osaka · Data: Open-Meteo ({source})"
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
    humidity_by_day = {}
    for timestamp, humidity in zip(hourly.get("time", []), hourly.get("relative_humidity_2m", [])):
        if humidity is not None:
            humidity_by_day.setdefault(date.fromisoformat(timestamp[:10]), []).append(float(humidity))
    result = {}
    times = daily.get("time", [])
    for i, ds in enumerate(times):
        day = date.fromisoformat(ds)
        humidities = humidity_by_day.get(day, [])
        humidity = round(sum(humidities) / len(humidities)) if humidities else None
        result[day] = (
            daily.get("weather_code", [None] * len(times))[i],
            daily.get("temperature_2m_max", [None] * len(times))[i],
            daily.get("temperature_2m_min", [None] * len(times))[i],
            daily.get("precipitation_probability_max", [None] * len(times))[i],
            humidity,
            daily.get("sunrise", [None] * len(times))[i],
            daily.get("sunset", [None] * len(times))[i],
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
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
            "hourly": "relative_humidity_2m",
            "timezone": TZ, "temperature_unit": "celsius",
        }
        data_by_day.update(read_daily(get_json(api_url("https://archive-api.open-meteo.com/v1/archive", params))))
        sources.update({d: "历史再分析" for d in data_by_day})

    # Recent past and forecast, avoiding the historical archive's normal publication delay.
    params = {
        "latitude": LAT, "longitude": LON,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
        "hourly": "relative_humidity_2m",
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
