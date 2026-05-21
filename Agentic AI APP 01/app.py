"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          WEATHERMIND AI v2.0 — Agentic AI System                           ║
║          ReAct Pattern · Multi-Tool · Premium UI · UV · AQI · 7-Day        ║
║          Stack: Streamlit · Open-Meteo · Anthropic / Gemini                ║
╚══════════════════════════════════════════════════════════════════════════════╝

ReAct Loop:  THOUGHT → ACTION → OBSERVATION → (repeat) → FINAL ANSWER

New in v2.0:
  • UV Index awareness per activity
  • Air Quality Index (AQI) from Open-Meteo Air Quality API
  • Humidity, wind gusts & visibility data
  • 7-day forecast tab with visual day cards
  • Scrollable hourly timeline with active-hour highlight
  • Clothing recommendation engine
  • Health advisories (heat, cold, UV, air quality)
  • Premium dark glassmorphism UI  (Syne + Plus Jakarta Sans)
  • Live sidebar weather widget
  • 3-strategy location parser (fixes Pakistan/lowercase issue)

FIX v2.1:
  • Sidebar now visible — fixed CSS overrides hiding Streamlit's sidebar toggle
  • Restored [data-testid="collapsedControl"] and sidebar button visibility
  • Scoped header/footer hiding to avoid collateral damage
"""

import re
import json
import datetime
import requests
import streamlit as st

# ── Optional LLM providers ────────────────────────────────────────────────────
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 1 — LOOKUP TABLES
# ══════════════════════════════════════════════════════════════════════════════

WMO_LABELS = {
    0:"Clear sky",1:"Mainly clear",2:"Partly cloudy",3:"Overcast",
    45:"Foggy",48:"Icy fog",
    51:"Light drizzle",53:"Moderate drizzle",55:"Dense drizzle",
    61:"Slight rain",63:"Moderate rain",65:"Heavy rain",
    66:"Freezing rain",67:"Heavy freezing rain",
    71:"Slight snow",73:"Moderate snow",75:"Heavy snow",77:"Snow grains",
    80:"Slight showers",81:"Moderate showers",82:"Violent showers",
    85:"Snow showers",86:"Heavy snow showers",
    95:"Thunderstorm",96:"Thunderstorm + hail",99:"Thunderstorm + heavy hail",
}

WMO_EMOJI = {
    0:"☀️",1:"🌤️",2:"⛅",3:"☁️",
    45:"🌫️",48:"🌫️",
    51:"🌦️",53:"🌦️",55:"🌧️",56:"🌧️",57:"🌧️",
    61:"🌧️",63:"🌧️",65:"🌧️",66:"❄️",67:"❄️",
    71:"🌨️",73:"🌨️",75:"🌨️",77:"🌨️",
    80:"🌦️",81:"🌧️",82:"⛈️",
    85:"🌨️",86:"🌨️",
    95:"⛈️",96:"⛈️",99:"⛈️",
}

# (temp_min_ideal, temp_max_ideal, rain_tolerance_mm, wind_tolerance_kmh, uv_concern)
ACTIVITY_PROFILES = {
    "running":   (8,  24, 1.0, 25, True),
    "jogging":   (8,  24, 1.0, 25, True),
    "cycling":   (10, 26, 0.5, 30, True),
    "biking":    (10, 26, 0.5, 30, True),
    "hiking":    (5,  25, 2.0, 35, True),
    "trekking":  (5,  25, 2.0, 35, True),
    "walking":   (5,  30, 3.0, 40, False),
    "strolling": (5,  30, 3.0, 40, False),
    "tennis":    (12, 28, 0.0, 20, True),
    "golf":      (10, 30, 0.5, 25, True),
    "cricket":   (15, 32, 0.0, 20, True),
    "football":  (8,  25, 2.0, 30, True),
    "soccer":    (8,  25, 2.0, 30, True),
    "picnic":    (18, 30, 0.0, 15, True),
    "swimming":  (22, 40, 0.0, 20, True),
    "gym":       (0,  50, 99,  99, False),
    "yoga":      (15, 35, 5.0, 99, False),
    "dinner":    (0,  50, 99,  99, False),
    "shopping":  (0,  50, 99,  99, False),
    "museum":    (0,  50, 99,  99, False),
    "workout":   (8,  24, 1.0, 25, True),
    "exercise":  (8,  24, 1.0, 25, True),
}

# (feels_like_threshold, emoji, label, tip)
CLOTHING_RULES = [
    (35,  "🥵", "Extremely Hot",  "Ultra-light breathable clothing, wide-brim hat, SPF 50+ sunscreen"),
    (28,  "😅", "Hot",            "Light summer clothes, sun hat, extra water bottle essential"),
    (20,  "😊", "Comfortable",    "T-shirt and light trousers or shorts — perfect conditions"),
    (12,  "🧥", "Cool",           "Light jacket or hoodie, long trousers recommended"),
    (5,   "🧣", "Cold",           "Warm jacket, scarf, and gloves — layer up"),
    (-99, "🥶", "Very Cold",      "Heavy winter coat, thermal base layers, gloves, and hat"),
]

AQI_RANGES = [
    (0,   20,  "Excellent",  "#00e676", "🟢"),
    (20,  40,  "Good",       "#b2ff59", "🟢"),
    (40,  60,  "Moderate",   "#ffff00", "🟡"),
    (60,  80,  "Poor",       "#ff9100", "🟠"),
    (80,  100, "Very Poor",  "#ff1744", "🔴"),
    (100, 999, "Hazardous",  "#d500f9", "🟣"),
]


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 2 — TOOL FUNCTIONS  (the agent's "hands")
# ══════════════════════════════════════════════════════════════════════════════

def geocode_location(location: str) -> dict:
    """TOOL: Place name → coordinates + metadata via Open-Meteo Geocoding API."""
    url    = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": location, "count": 1, "language": "en", "format": "json"}
    resp   = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data   = resp.json()
    if not data.get("results"):
        raise ValueError(f"Location '{location}' not found. Try a nearby major city.")
    r = data["results"][0]
    return {
        "lat":       r["latitude"],
        "lon":       r["longitude"],
        "name":      r.get("name", location),
        "country":   r.get("country", ""),
        "timezone":  r.get("timezone", "UTC"),
        "elevation": r.get("elevation", 0),
        "admin1":    r.get("admin1", ""),
    }


def fetch_hourly_weather(lat: float, lon: float, timezone: str) -> dict:
    """
    TOOL: Fetch today's hourly forecast (24 entries) from Open-Meteo.
    Returns {hour: weather_dict} with rich fields.
    """
    url    = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude":  lat,
        "longitude": lon,
        "hourly": [
            "temperature_2m", "apparent_temperature", "precipitation",
            "windspeed_10m", "windgusts_10m", "weathercode", "is_day",
            "relativehumidity_2m", "visibility", "uv_index",
            "precipitation_probability",
        ],
        "timezone":      timezone,
        "forecast_days": 1,
    }
    resp = requests.get(url, params=params, timeout=12)
    resp.raise_for_status()
    raw  = resp.json()["hourly"]
    hourly = {}
    for i, ts in enumerate(raw["time"]):
        hour = int(ts.split("T")[1].split(":")[0])
        code = raw["weathercode"][i]
        hourly[hour] = {
            "temperature":   round(raw["temperature_2m"][i], 1),
            "feels_like":    round(raw["apparent_temperature"][i], 1),
            "precipitation": round(raw["precipitation"][i], 2),
            "precip_prob":   raw["precipitation_probability"][i],
            "windspeed":     round(raw["windspeed_10m"][i], 1),
            "windgusts":     round(raw["windgusts_10m"][i], 1),
            "humidity":      raw["relativehumidity_2m"][i],
            "visibility":    round(raw["visibility"][i] / 1000, 1),
            "uv_index":      round(raw["uv_index"][i], 1),
            "weathercode":   code,
            "condition":     WMO_LABELS.get(code, f"WMO {code}"),
            "emoji":         WMO_EMOJI.get(code, "🌡️"),
            "is_day":        raw["is_day"][i],
        }
    return hourly


def fetch_air_quality(lat: float, lon: float) -> dict:
    """TOOL: Fetch current AQI from Open-Meteo Air Quality API (free, no key)."""
    url    = "https://air-quality-api.open-meteo.com/v1/air-quality"
    params = {
        "latitude":  lat,
        "longitude": lon,
        "hourly":    ["european_aqi", "pm10", "pm2_5"],
        "forecast_days": 1,
    }
    try:
        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()["hourly"]
        now_h = datetime.datetime.now().hour
        aqi_val = data["european_aqi"][now_h] or 0
        label, color, icon = _classify_aqi(aqi_val)
        return {
            "aqi":   aqi_val,
            "pm10":  round(data["pm10"][now_h] or 0, 1),
            "pm2_5": round(data["pm2_5"][now_h] or 0, 1),
            "label": label, "color": color, "icon": icon,
        }
    except Exception:
        return {"aqi":0,"pm10":0,"pm2_5":0,"label":"Unknown","color":"#888","icon":"⬜"}


def _classify_aqi(aqi: float) -> tuple:
    for lo, hi, label, color, icon in AQI_RANGES:
        if lo <= aqi < hi:
            return label, color, icon
    return "Unknown", "#888", "⬜"


def fetch_7day_summary(lat: float, lon: float, timezone: str) -> list:
    """TOOL: Fetch daily summary for 7 days (max/min temp, rain, UV, wind)."""
    url    = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude":  lat,
        "longitude": lon,
        "daily": [
            "weathercode","temperature_2m_max","temperature_2m_min",
            "precipitation_sum","windspeed_10m_max","uv_index_max",
            "precipitation_probability_max",
        ],
        "timezone":      timezone,
        "forecast_days": 7,
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    d    = resp.json()["daily"]
    result = []
    for i in range(len(d["time"])):
        code = d["weathercode"][i]
        result.append({
            "date":      d["time"][i],
            "emoji":     WMO_EMOJI.get(code, "🌡️"),
            "condition": WMO_LABELS.get(code, ""),
            "temp_max":  d["temperature_2m_max"][i],
            "temp_min":  d["temperature_2m_min"][i],
            "rain_sum":  d["precipitation_sum"][i],
            "wind_max":  d["windspeed_10m_max"][i],
            "uv_max":    d["uv_index_max"][i],
            "rain_prob": d["precipitation_probability_max"][i],
        })
    return result


def get_clothing_advice(feels_like: float, rain: float, wind: float) -> tuple:
    """TOOL: Return (emoji, label, tip) based on feels-like temperature + rain/wind."""
    for threshold, emoji, label, tip in CLOTHING_RULES:
        if feels_like >= threshold:
            extras = []
            if rain > 1:  extras.append("bring a waterproof jacket/umbrella")
            if wind > 30: extras.append("windproof outer layer recommended")
            full_tip = tip + (f". Also: {'; '.join(extras)}." if extras else ".")
            return emoji, label, full_tip
    return "🥶", "Extreme cold", "Full winter gear essential."


def get_uv_advice(uv_index: float, activity: str) -> str:
    """TOOL: Return UV safety advice string (empty if indoor activity)."""
    profile = ACTIVITY_PROFILES.get(activity.lower().split()[0])
    if profile and not profile[4]:
        return ""   # indoor — no UV concern
    if uv_index < 3:  return "UV Low — no special protection needed."
    if uv_index < 6:  return "UV Moderate — apply SPF 30+."
    if uv_index < 8:  return "UV High — SPF 50+, hat, avoid peak 10 AM–2 PM."
    if uv_index < 11: return "UV Very High — minimise direct sun exposure."
    return "⚠️ UV Extreme — stay indoors or wear maximum protection."


def evaluate_activity_suitability(activity: str, weather: dict) -> dict:
    """
    TOOL: Score activity suitability 0-100 using activity profiles + weather.
    Returns {suitable, score, grade, issues, positives, health_flags}.
    """
    act_key = activity.lower().split()[0]
    profile = ACTIVITY_PROFILES.get(act_key)
    issues, positives, health_flags = [], [], []
    score = 100

    rain  = weather["precipitation"]
    feels = weather["feels_like"]
    temp  = weather["temperature"]
    wind  = weather["windspeed"]
    gusts = weather["windgusts"]
    humid = weather["humidity"]
    uv    = weather["uv_index"]
    vis   = weather["visibility"]
    cond  = weather["condition"]
    prob  = weather["precip_prob"]
    is_outdoor = not profile or profile[2] < 90

    if profile:
        t_min, t_max, rain_tol, wind_tol, uv_concern = profile

        # Rain
        if rain > rain_tol * 3:
            issues.append(f"Heavy rain {rain}mm (limit {rain_tol}mm)")
            score -= 40
        elif rain > rain_tol:
            issues.append(f"Rain {rain}mm above ideal tolerance")
            score -= 20
        else:
            positives.append(f"Dry conditions ✓" if rain == 0 else f"Light rain {rain}mm OK")

        # Temperature
        if feels < t_min - 5:
            issues.append(f"Too cold — feels {feels}°C (ideal ≥{t_min}°C)")
            score -= 30
        elif feels < t_min:
            issues.append(f"Slightly cool {feels}°C — dress in layers")
            score -= 10
        elif feels > t_max + 8:
            issues.append(f"Dangerous heat — {feels}°C (ideal ≤{t_max}°C)")
            health_flags.append("🌡️ Heat stress risk — hydrate every 15 min")
            score -= 35
        elif feels > t_max:
            issues.append(f"Warm {feels}°C — watch for overheating")
            score -= 15
        else:
            positives.append(f"Temperature ideal {feels}°C ✓")

        # Wind
        if wind > wind_tol * 1.5 or gusts > wind_tol * 2:
            issues.append(f"Strong wind {wind}km/h (gusts {gusts}km/h)")
            score -= 20
        elif wind > wind_tol:
            issues.append(f"Elevated wind {wind}km/h")
            score -= 10
        else:
            positives.append(f"Wind comfortable {wind}km/h ✓")

        # UV
        if uv_concern and uv >= 8:
            issues.append(f"UV Very High ({uv}) — sun protection critical")
            health_flags.append("☀️ UV Very High — SPF 50+ mandatory")
            score -= 15
        elif uv_concern and uv >= 6:
            issues.append(f"UV High ({uv}) — wear sunscreen")
            score -= 5
        elif uv_concern and uv >= 3:
            positives.append(f"UV moderate ({uv}) — SPF advised")

    # Universal checks
    if "thunderstorm" in cond.lower():
        issues.append("⚡ Thunderstorm — unsafe outdoors")
        health_flags.append("⚡ Lightning danger — seek shelter")
        score -= 60

    if is_outdoor and prob >= 70:
        issues.append(f"High rain probability {prob}%")
        score -= 10

    if humid > 85 and feels > 25:
        health_flags.append(f"💧 Humidity {humid}% — heat index elevated")
        score -= 8

    if vis < 1 and is_outdoor:
        issues.append(f"Poor visibility {vis}km — foggy")
        score -= 10

    score = max(0, min(100, score))
    return {
        "suitable":     score >= 60,
        "score":        score,
        "grade":        "A" if score>=90 else "B" if score>=75 else "C" if score>=60 else "D" if score>=40 else "F",
        "issues":       issues,
        "positives":    positives,
        "health_flags": health_flags,
    }


def find_better_hours(hourly: dict, activity: str, preferred: int, window: int = 8) -> list:
    """TOOL: Find top-3 better hours within ±window of preferred time."""
    candidates = []
    for h in range(max(5, preferred - window), min(23, preferred + window + 1)):
        if h == preferred or h not in hourly:
            continue
        ev = evaluate_activity_suitability(activity, hourly[h])
        if ev["score"] > 60:
            candidates.append({
                "hour":       h,
                "time_label": f"{h:02d}:00",
                "score":      ev["score"],
                "weather":    hourly[h],
                "issues":     ev["issues"],
                "positives":  ev["positives"],
            })
    return sorted(candidates, key=lambda x: x["score"], reverse=True)[:3]


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 3 — INTENT PARSER
# ══════════════════════════════════════════════════════════════════════════════

ACTIVITY_KEYWORDS = [
    "running","jogging","run","jog","cycling","biking","bike","cycle",
    "hiking","hike","walk","walking","stroll","strolling","tennis","golf",
    "football","soccer","cricket","gym","yoga","swimming","swim","picnic",
    "outdoor","dinner","shopping","museum","workout","exercise","trekking","trek",
]

_ACTIVITY_WORDS_SET = {
    "run","running","jog","jogging","gym","yoga","walk","walking","cycling",
    "biking","bike","hike","hiking","swim","swimming","tennis","golf","picnic",
    "dinner","shopping","morning","evening","afternoon","night","noon","go","the","a",
}


def _clean_loc(s: str) -> str:
    return re.sub(r'\s+(at|on|by|for|tomorrow|today|this|the|a|an)$',
                  '', s.strip(), flags=re.I).strip()


def parse_intent_rule_based(user_input: str) -> dict:
    """Fast rule-based intent extraction — works without any API key."""
    text   = user_input.strip()
    intent = {"location": None, "hour": None, "activity": None, "raw": text}

    # Activity
    for kw in ACTIVITY_KEYWORDS:
        if re.search(rf'\b{kw}\b', text, re.I):
            intent["activity"] = kw
            break
    intent["activity"] = intent["activity"] or "outdoor activity"

    # Time — 12h
    m = re.search(r'\b(\d{1,2})\s*(?::(\d{2}))?\s*(am|pm)\b', text, re.I)
    if m:
        h = int(m.group(1))
        if m.group(3).lower() == "pm" and h != 12: h += 12
        elif m.group(3).lower() == "am" and h == 12: h = 0
        intent["hour"] = h
    else:
        m24 = re.search(r'\b([01]?\d|2[0-3]):([0-5]\d)\b', text)
        if m24:
            intent["hour"] = int(m24.group(1))
        elif re.search(r'\b(morning|dawn|sunrise)\b', text, re.I): intent["hour"] = 7
        elif re.search(r'\bnoon\b',       text, re.I): intent["hour"] = 12
        elif re.search(r'\bafternoon\b',  text, re.I): intent["hour"] = 14
        elif re.search(r'\b(evening|sunset)\b', text, re.I): intent["hour"] = 18
        elif re.search(r'\bnight\b',      text, re.I): intent["hour"] = 20
        else: intent["hour"] = datetime.datetime.now().hour

    # Location — Strategy 1: "in/at/near <place>" (case-insensitive, ≤3 words)
    lm = re.search(
        r'\b(?:in|at|near|around)\s+([a-zA-Z][a-zA-Z\s\-]{1,30}?)'
        r'(?=\s+(?:at|on|by|for|tomorrow|today|this|\d)|[,\.]|$)',
        text, re.I)
    if lm:
        cand  = _clean_loc(lm.group(1))
        first = cand.split()[0].lower() if cand else ""
        if first not in _ACTIVITY_WORDS_SET and 2 <= len(cand) and len(cand.split()) <= 3:
            intent["location"] = cand.title()

    # Strategy 2: capitalized proper-noun clusters
    if not intent["location"]:
        caps = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', text)
        skip = {"I","PM","AM","Monday","Tuesday","Wednesday","Thursday",
                "Friday","Saturday","Sunday","Today","Tomorrow"}
        places = [c for c in caps if c not in skip]
        if places:
            intent["location"] = places[-1]

    # Strategy 3: last lowercase after prep
    if not intent["location"]:
        all_m = re.findall(r'\b(?:in|at|near|around)\s+([a-z][a-z\-]+)', text, re.I)
        skip2 = {"the","a","an","my","our","this","that","morning","evening",
                 "afternoon","night","noon","go","run","gym","yoga"}
        for m2 in reversed(all_m):
            if m2.lower() not in skip2:
                intent["location"] = m2.title()
                break

    return intent


def parse_intent_with_llm(user_input: str, client, provider: str) -> dict:
    """LLM-enhanced intent extraction — graceful fallback to rule-based."""
    now_h  = datetime.datetime.now().hour
    prompt = f"""Extract structured info from this activity-plan message.
Return ONLY valid JSON — no markdown, no explanation.

Message: "{user_input}"

Expected JSON:
{{
  "location": "city name or null",
  "hour": {now_h},
  "activity": "activity keyword",
  "raw": "{user_input}"
}}

Rules:
- hour: 0-23 integer. "5 PM"→17, "morning"→7, "afternoon"→14, "evening"→18, "night"→20
- location: extract city/town only, null if none mentioned
- activity: concise label like "running", "cycling", "gym", "picnic"
"""
    try:
        if provider == "anthropic":
            msg = client.messages.create(
                model="claude-opus-4-5", max_tokens=250,
                messages=[{"role":"user","content":prompt}])
            raw = msg.content[0].text.strip()
        elif provider == "gemini":
            raw = client.generate_content(prompt).text.strip()
        else:
            raise ValueError("Unknown provider")
        raw    = re.sub(r"```json|```", "", raw).strip()
        parsed = json.loads(raw)
        parsed.setdefault("raw", user_input)
        return parsed
    except Exception:
        return parse_intent_rule_based(user_input)


def generate_llm_response(client, provider, intent, weather,
                           evaluation, clothing, uv_advice, aqi, alternatives) -> str:
    """Ask LLM to write the natural-language final answer."""
    alt_text = (f"Best alt: {alternatives[0]['time_label']} score {alternatives[0]['score']}/100"
                if alternatives else "None found")
    prompt = f"""You are a warm, expert weather advisor. Write a natural 3-4 sentence response.

Activity: {intent['activity']} in {intent['location']} at {intent['hour']:02d}:00
Weather: {weather['condition']}, {weather['temperature']}°C (feels {weather['feels_like']}°C)
Rain: {weather['precipitation']}mm ({weather['precip_prob']}% chance), Wind: {weather['windspeed']}km/h
UV: {weather['uv_index']}, Humidity: {weather['humidity']}%, Visibility: {weather['visibility']}km
Suitability: {evaluation['score']}/100 ({'GO' if evaluation['suitable'] else 'NO-GO'})
Issues: {'; '.join(evaluation['issues']) or 'None'}
Clothing: {clothing[2]}
UV advice: {uv_advice or 'N/A'}
AQI: {aqi['label']} ({aqi['aqi']})
Alternative: {alt_text}

Start with clear go/no-go. Be conversational, include one practical tip. No bullet points.
"""
    try:
        if provider == "anthropic":
            msg = client.messages.create(
                model="claude-opus-4-5", max_tokens=350,
                messages=[{"role":"user","content":prompt}])
            return msg.content[0].text.strip()
        elif provider == "gemini":
            return client.generate_content(prompt).text.strip()
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 4 — WEATHER AGENT  (ReAct generator)
# ══════════════════════════════════════════════════════════════════════════════

class WeatherAgent:
    def __init__(self, llm_client=None, llm_provider=None):
        self.llm  = llm_client
        self.prov = llm_provider

    def run(self, user_input: str):
        # ── Phase 1 — Intent ─────────────────────────────────────────
        yield self._t("thought", "🧠", "Parsing Intent",
                      f'Received: "{user_input[:70]}…" — extracting location, time & activity.')

        if self.llm:
            yield self._t("action","🤖","Action → LLM Intent Parse",
                          f"Calling {self.prov.title()} for deep NL understanding.")
            intent = parse_intent_with_llm(user_input, self.llm, self.prov)
        else:
            yield self._t("action","🔍","Action → Rule-Based Intent Parse",
                          "Using 3-strategy regex + keyword engine.")
            intent = parse_intent_rule_based(user_input)

        loc      = intent.get("location")
        hour     = intent.get("hour", datetime.datetime.now().hour)
        activity = intent.get("activity", "outdoor activity")

        if not loc:
            yield self._t("observation","❓","No Location Detected",
                          "Could not find a city name. Please include one, e.g. 'run in Lahore at 6 PM'.")
            yield {"type":"error",
                   "message":"No location found. Please mention a city, e.g. **run in Karachi at 7 AM**."}
            return

        yield self._t("observation","📋","Intent Extracted",
                      f"📍 **{loc}** | 🕐 **{hour:02d}:00** | 🏃 **{activity}**")

        # ── Phase 2 — Geocode ────────────────────────────────────────
        yield self._t("action","🗺️","Action → Geocoding",
                      f'Resolving "{loc}" → coordinates via Open-Meteo.')
        try:
            geo = geocode_location(loc)
        except ValueError as e:
            yield self._t("observation","❌","Geocoding Failed", str(e))
            yield {"type":"error","message":str(e)}
            return
        except requests.RequestException as e:
            yield self._t("observation","❌","Network Error", str(e))
            yield {"type":"error","message":f"Network error: {e}"}
            return

        yield self._t("observation","📍","Location Resolved",
                      f"**{geo['name']}**, {geo['admin1']}, {geo['country']} | "
                      f"lat {geo['lat']:.3f} lon {geo['lon']:.3f} | "
                      f"Elevation: {geo['elevation']}m | TZ: {geo['timezone']}")

        # ── Phase 3 — Hourly weather ─────────────────────────────────
        yield self._t("action","🌐","Action → Hourly Weather Fetch",
                      "Requesting today's 24-hour forecast from Open-Meteo.")
        try:
            hourly = fetch_hourly_weather(geo["lat"], geo["lon"], geo["timezone"])
        except requests.RequestException as e:
            yield self._t("observation","❌","Weather Fetch Failed", str(e))
            yield {"type":"error","message":f"Weather API error: {e}"}
            return

        temps = [h["temperature"] for h in hourly.values()]
        yield self._t("observation","☁️","Weather Data Ready",
                      f"Got {len(hourly)} hourly records. "
                      f"Temp range today: {min(temps)}–{max(temps)}°C")

        # ── Phase 4 — Air Quality ────────────────────────────────────
        yield self._t("action","💨","Action → Air Quality Check",
                      "Fetching AQI from Open-Meteo Air Quality API.")
        aqi = fetch_air_quality(geo["lat"], geo["lon"])
        yield self._t("observation","🌬️","AQI Retrieved",
                      f"{aqi['icon']} Air Quality: **{aqi['label']}** "
                      f"(AQI {aqi['aqi']}) | PM2.5: {aqi['pm2_5']} µg/m³ | PM10: {aqi['pm10']} µg/m³")

        # ── Phase 5 — 7-day summary ──────────────────────────────────
        yield self._t("action","📅","Action → 7-Day Forecast Fetch",
                      "Requesting daily summaries for the week ahead.")
        try:
            week = fetch_7day_summary(geo["lat"], geo["lon"], geo["timezone"])
            yield self._t("observation","🗓️","7-Day Forecast Ready",
                          f"Retrieved {len(week)} days. Best day: "
                          f"{max(week, key=lambda d: d['temp_max'])['date']} "
                          f"({max(week, key=lambda d: d['temp_max'])['temp_max']}°C max)")
        except Exception as e:
            week = []
            yield self._t("observation","⚠️","7-Day Fetch Failed", str(e))

        # ── Phase 6 — Analyse target hour ───────────────────────────
        target = hourly.get(hour)
        if not target:
            hour   = min(hourly.keys(), key=lambda h: abs(h - hour))
            target = hourly[hour]

        yield self._t("thought","🌡️","Analysing Target Hour Conditions",
                      f"At **{hour:02d}:00** → {target['emoji']} {target['condition']} | "
                      f"Temp: {target['temperature']}°C (feels {target['feels_like']}°C) | "
                      f"Rain: {target['precipitation']}mm ({target['precip_prob']}%) | "
                      f"Wind: {target['windspeed']}km/h (gusts {target['windgusts']}km/h) | "
                      f"UV: {target['uv_index']} | Humidity: {target['humidity']}% | "
                      f"Visibility: {target['visibility']}km")

        # ── Phase 7 — Suitability scoring ────────────────────────────
        yield self._t("action","⚖️","Action → Suitability Analysis",
                      f'Scoring "{activity}" against activity-profile matrix.')
        ev = evaluate_activity_suitability(activity, target)
        verdict = "✅ GO" if ev["suitable"] else "❌ NO-GO"
        yield self._t("observation","📊",
                      f"Score: **{ev['score']}/100** Grade **{ev['grade']}** — {verdict}",
                      (f"Issues: {'; '.join(ev['issues']) or 'None'} | "
                       f"Positives: {'; '.join(ev['positives']) or 'None'}"
                       + (f" | ⚠️ Health: {'; '.join(ev['health_flags'])}"
                          if ev["health_flags"] else "")))

        # ── Phase 8 — Clothing + UV ──────────────────────────────────
        yield self._t("action","👕","Action → Clothing & UV Advisory",
                      "Computing clothing recommendation and UV safety level.")
        clothing  = get_clothing_advice(target["feels_like"], target["precipitation"], target["windspeed"])
        uv_advice = get_uv_advice(target["uv_index"], activity)
        yield self._t("observation","👔","Clothing & UV Advice",
                      f"{clothing[0]} **{clothing[1]}** — {clothing[2]}"
                      + (f" | ☀️ {uv_advice}" if uv_advice else ""))

        # ── Phase 9 — Alternatives ───────────────────────────────────
        alternatives = []
        if not ev["suitable"]:
            yield self._t("thought","🔄","Searching Better Time Windows",
                          f"Score {ev['score']}/100 < 60. Scanning ±8 hours for better conditions.")
            yield self._t("action","🔎","Action → Alternative Hour Scan",
                          "Evaluating suitability for each hour in the search window.")
            alternatives = find_better_hours(hourly, activity, hour)
            if alternatives:
                best = alternatives[0]
                yield self._t("observation","💡","Better Window Found",
                              f"**{best['time_label']}** scores {best['score']}/100 — "
                              f"{best['weather']['emoji']} {best['weather']['condition']}, "
                              f"{best['weather']['temperature']}°C")
            else:
                yield self._t("observation","😔","No Better Window Nearby",
                              "All hours within ±8h have similar or worse conditions.")

        # ── Phase 10 — Final response ────────────────────────────────
        yield self._t("thought","✍️","Composing Final Response",
                      ("Calling " + self.prov.title() + " for natural language output."
                       if self.llm else "Using template engine (add API key for richer text)."))

        nat = None
        if self.llm:
            nat = generate_llm_response(self.llm, self.prov, intent, target,
                                        ev, clothing, uv_advice, aqi, alternatives)
        if not nat:
            nat = self._template(activity, geo["name"], hour, target,
                                 ev, clothing, uv_advice, aqi, alternatives)

        snap = {h: hourly[h] for h in sorted(hourly) if 5 <= h <= 23}

        yield {
            "type":             "answer",
            "intent":           intent,
            "location_info":    geo,
            "hour":             hour,
            "weather":          target,
            "evaluation":       ev,
            "clothing":         clothing,
            "uv_advice":        uv_advice,
            "aqi":              aqi,
            "alternatives":     alternatives,
            "natural_response": nat,
            "hourly_snapshot":  snap,
            "week_forecast":    week,
        }

    @staticmethod
    def _t(typ, icon, label, body):
        return {"type":typ,"icon":icon,"label":label,"body":body}

    @staticmethod
    def _template(activity, city, hour, wx, ev, clothing, uv, aqi, alts):
        cond  = wx["condition"]; temp = wx["temperature"]; feels = wx["feels_like"]
        rain  = wx["precipitation"]; prob = wx["precip_prob"]
        if ev["suitable"]:
            rec    = f"Great news — conditions look ✅ **good** for **{activity}** in {city} at {hour:02d}:00."
            detail = (f"Expect {cond.lower()}, {temp}°C (feels {feels}°C)"
                      + (f", {rain}mm rain ({prob}% chance)" if rain>0 else ", no rain expected") + ".")
            tip    = f" {clothing[2]}" if clothing else ""
            uv_n   = f" {uv}" if uv else ""
            aqi_n  = f" Air quality is {aqi['label']}." if aqi["label"] != "Unknown" else ""
            return f"{rec} {detail}{tip}{uv_n}{aqi_n}"
        else:
            rec    = f"⚠️ Conditions are **not ideal** for **{activity}** in {city} at {hour:02d}:00."
            issues = "; ".join(ev["issues"][:2])
            detail = f"Forecast: {cond.lower()}, {temp}°C — key concerns: {issues}."
            if alts:
                b   = alts[0]
                alt = (f" Consider **{b['time_label']}** instead — "
                       f"{b['weather']['condition']}, {b['weather']['temperature']}°C "
                       f"(suitability score {b['score']}/100).")
                return f"{rec} {detail}{alt}"
            return f"{rec} {detail} No significantly better windows found in the next 8 hours."


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 5 — STREAMLIT UI  (Premium Dark Glassmorphism)
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="WeatherMind AI",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CRITICAL FIX: Sidebar-safe CSS ───────────────────────────────────────────
# The original code used:
#   #MainMenu, footer, header { visibility:hidden; }
# This hid the sidebar collapse/toggle button (rendered inside <header>).
# Fix: target only the deploy button and Streamlit branding, NOT the full header.
# Also restore [data-testid="collapsedControl"] visibility explicitly.
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=Plus+Jakarta+Sans:ital,wght@0,300;0,400;0,500;0,600;1,400&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --bg-deep:   #060b18;
  --bg-mid:    #0c1527;
  --bg-card:   rgba(255,255,255,0.04);
  --border:    rgba(255,255,255,0.08);
  --border-hi: rgba(255,255,255,0.15);
  --accent:    #38bdf8;
  --accent2:   #818cf8;
  --accent3:   #34d399;
  --warn:      #fb923c;
  --danger:    #f87171;
  --text-hi:   #f0f6ff;
  --text-mid:  #94a3b8;
  --text-lo:   #475569;
  --fh: 'Syne', sans-serif;
  --fb: 'Plus Jakarta Sans', sans-serif;
  --fm: 'JetBrains Mono', monospace;
}

html, body, [class*="css"] { font-family: var(--fb) !important; color: var(--text-hi) !important; }
.stApp { background: var(--bg-deep) !important; }

/* ── Hide Streamlit chrome — deploy button, footer branding, main menu ── */
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; height: 0 !important; }
.stDeployButton { display: none !important; }

/* ── TRANSPARENT HEADER ── */
/* Make the top toolbar fully transparent/glassmorphism so the dark bg shows through */
header[data-testid="stHeader"] {
  background: transparent !important;
  backdrop-filter: blur(12px) !important;
  -webkit-backdrop-filter: blur(12px) !important;
  border-bottom: 1px solid rgba(255,255,255,0.05) !important;
  box-shadow: none !important;
}
/* Keep all buttons inside the header visible */
header[data-testid="stHeader"] * { visibility: visible !important; }
header[data-testid="stHeader"] button { visibility: visible !important; }

/* ── FIX: Explicitly restore sidebar toggle button visibility ── */
[data-testid="collapsedControl"] { visibility: visible !important; display: flex !important; }
[data-testid="baseButton-headerNoPadding"] { visibility: visible !important; }
button[kind="header"] { visibility: visible !important; }

/* ── FIX: Ensure the sidebar itself is not hidden ── */
section[data-testid="stSidebar"] { visibility: visible !important; display: block !important; }

/* ── REMOVE WHITE BOTTOM BAR — transparent floating chat input ── */
/* The white bar comes from the stBottom / chat input wrapper having a solid bg */
[data-testid="stBottom"] {
  background: transparent !important;
  border-top: none !important;
  box-shadow: none !important;
  padding-bottom: 0 !important;
}
/* The inner sticky container that creates the white block */
[data-testid="stBottom"] > div {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}
/* Remove any white block around the chat input at the page bottom */
.stChatFloatingInputContainer,
[class*="stChatInputContainer"],
[data-testid="stChatInputContainer"] {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0.5rem 0 1rem !important;
}
/* Fade the bottom of the main area so chat messages dissolve into the input */
.main .block-container::after {
  content: '';
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 130px;
  background: linear-gradient(to bottom, transparent, var(--bg-deep) 85%);
  pointer-events: none;
  z-index: 0;
}

.block-container { padding:1.5rem 2rem 5rem !important; max-width:1180px; }

/* animated background */
.stApp::before {
  content:''; position:fixed; inset:0; z-index:-1;
  background:
    radial-gradient(ellipse 80% 60% at 10% 10%, rgba(56,189,248,0.07) 0%,transparent 60%),
    radial-gradient(ellipse 60% 80% at 90% 80%, rgba(129,140,248,0.07) 0%,transparent 60%),
    radial-gradient(ellipse 50% 50% at 50% 50%, rgba(52,211,153,0.04) 0%,transparent 70%),
    var(--bg-deep);
}

/* sidebar */
section[data-testid="stSidebar"] {
  background: var(--bg-mid) !important;
  border-right: 1px solid var(--border) !important;
}
section[data-testid="stSidebar"] * { color: var(--text-hi) !important; }
section[data-testid="stSidebar"] .stSelectbox > div > div,
section[data-testid="stSidebar"] .stTextInput > div > div {
  background: var(--bg-card) !important;
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
}
.sb-logo { font-family:var(--fh); font-size:1.4rem; font-weight:800;
           background:linear-gradient(90deg,var(--accent),var(--accent2));
           -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.sb-tag  { font-size:0.72rem; color:var(--text-mid); }

/* sidebar weather widget */
.sw { background:var(--bg-card); border:1px solid var(--border);
      border-radius:16px; padding:1.1rem; margin:0.8rem 0; }
.sw-city { font-size:0.7rem; text-transform:uppercase; letter-spacing:0.09em; color:var(--text-mid); }
.sw-temp { font-family:var(--fh); font-size:2.8rem; font-weight:800; color:var(--text-hi); line-height:1; }
.sw-cond { font-size:0.85rem; color:var(--accent); margin-bottom:0.8rem; }
.sw-grid { display:grid; grid-template-columns:1fr 1fr; gap:0.45rem; }
.sw-s    { background:rgba(255,255,255,0.03); border-radius:8px; padding:0.45rem 0.6rem; }
.sw-sv   { font-size:0.88rem; font-weight:600; color:var(--text-hi); }
.sw-sl   { font-size:0.64rem; color:var(--text-mid); }
.sw-tip  { font-size:0.75rem; color:var(--text-mid); margin-top:0.7rem; border-top:1px solid var(--border); padding-top:0.5rem; }

/* hero */
.hero {
  position:relative; overflow:hidden;
  background:linear-gradient(135deg,rgba(56,189,248,0.10) 0%,rgba(129,140,248,0.09) 50%,rgba(52,211,153,0.07) 100%);
  border:1px solid var(--border-hi); border-radius:24px;
  padding:3rem 2.5rem 2.4rem; margin-bottom:1.8rem; text-align:center;
}
.hero::before {
  content:''; position:absolute; top:-80px; right:-80px;
  width:320px; height:320px; border-radius:50%;
  background:radial-gradient(circle,rgba(56,189,248,0.12),transparent 70%);
  animation:hpulse 5s ease-in-out infinite;
}
.hero::after {
  content:''; position:absolute; bottom:-90px; left:-60px;
  width:280px; height:280px; border-radius:50%;
  background:radial-gradient(circle,rgba(129,140,248,0.10),transparent 70%);
  animation:hpulse 6s ease-in-out infinite reverse;
}
@keyframes hpulse { 0%,100%{transform:scale(1)} 50%{transform:scale(1.12)} }
.hero-badge {
  display:inline-block; font-size:0.7rem; font-weight:700; letter-spacing:0.12em;
  text-transform:uppercase; color:var(--accent); border:1px solid rgba(56,189,248,0.3);
  border-radius:99px; padding:0.25rem 1rem; margin-bottom:1rem;
  background:rgba(56,189,248,0.08);
}
.hero h1 {
  font-family:var(--fh); font-size:3.2rem; font-weight:800; color:var(--text-hi);
  margin:0 0 0.7rem; line-height:1.05; letter-spacing:-1.5px;
}
.hero h1 span { background:linear-gradient(90deg,var(--accent),var(--accent2));
                -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.hero p { font-size:1rem; color:var(--text-mid); max-width:540px; margin:0 auto; line-height:1.7; }

/* quick prompt buttons */
.stButton > button {
  background: var(--bg-card) !important; border: 1px solid var(--border) !important;
  color: var(--text-mid) !important; border-radius:12px !important;
  font-size:0.8rem !important; padding:0.5rem 0.7rem !important;
  transition:all 0.2s !important; font-family:var(--fb) !important;
  text-align:left !important; width:100% !important;
}
.stButton > button:hover {
  border-color:var(--accent) !important; color:var(--accent) !important;
  background:rgba(56,189,248,0.07) !important;
  transform:translateY(-2px) !important;
  box-shadow:0 6px 24px rgba(56,189,248,0.14) !important;
}

/* chat messages */
.stChatMessage { background:var(--bg-card) !important; border:1px solid var(--border) !important;
                 border-radius:16px !important; backdrop-filter:blur(10px) !important; }
[data-testid="stChatMessageContent"] { color:var(--text-hi) !important; }

/* chat input — transparent floating pill */
[data-testid="stChatInput"] {
  background: transparent !important;
}
[data-testid="stChatInput"] > div {
  background: rgba(12,21,39,0.75) !important;
  border: 1px solid var(--border-hi) !important;
  border-radius: 18px !important;
  backdrop-filter: blur(20px) !important;
  -webkit-backdrop-filter: blur(20px) !important;
  box-shadow: 0 8px 32px rgba(0,0,0,0.4), 0 0 0 1px rgba(56,189,248,0.08) !important;
}
[data-testid="stChatInput"] textarea {
  color: var(--text-hi) !important;
  font-family: var(--fb) !important;
  background: transparent !important;
}
[data-testid="stChatInput"] textarea::placeholder { color: var(--text-lo) !important; }

/* thought log */
.tlog { border-left:2px solid var(--accent2); background:rgba(129,140,248,0.05);
        border-radius:0 10px 10px 0; padding:0.5rem 0.9rem; margin:0.3rem 0;
        font-family:var(--fm); font-size:0.76rem; }
.tlog.action      { border-color:var(--accent);  background:rgba(56,189,248,0.05); }
.tlog.observation { border-color:var(--accent3); background:rgba(52,211,153,0.05); }
.tlog.error       { border-color:var(--danger);  background:rgba(248,113,113,0.07); }
.tlog-lbl { font-size:0.67rem; font-weight:700; color:var(--text-mid);
            letter-spacing:0.07em; text-transform:uppercase; margin-bottom:2px; }
.tlog-body { color:var(--text-hi); line-height:1.55; }

/* natural response bubble */
.nat-resp {
  background:linear-gradient(135deg,rgba(56,189,248,0.07),rgba(129,140,248,0.07));
  border:1px solid var(--border-hi); border-radius:16px;
  padding:1.2rem 1.5rem; font-size:0.97rem; line-height:1.75;
  color:var(--text-hi); margin:0.5rem 0 1.2rem;
}

/* decision card */
.dcard {
  background:linear-gradient(145deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02));
  border:1px solid var(--border-hi); border-radius:22px; padding:2rem;
  box-shadow:0 10px 50px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.07);
  backdrop-filter:blur(20px); margin:0.5rem 0 1rem;
}
.dcard-head { display:flex; align-items:center; gap:1.2rem; margin-bottom:1.5rem; }
.dcard-icon { font-size:3.2rem; line-height:1; }
.dcard-title { font-family:var(--fh); font-size:1.55rem; font-weight:800;
               color:var(--text-hi); margin:0; letter-spacing:-0.5px; }
.dcard-sub  { font-size:0.83rem; color:var(--text-mid); margin:0.25rem 0 0; }

.verdict {
  display:inline-flex; align-items:center; gap:0.5rem;
  font-weight:700; font-size:0.83rem; letter-spacing:0.05em;
  padding:0.4rem 1.2rem; border-radius:99px; margin-bottom:1.3rem;
}
.verdict.go   { background:rgba(52,211,153,0.15); color:var(--accent3);
                border:1px solid rgba(52,211,153,0.3); }
.verdict.nogo { background:rgba(251,146,60,0.15); color:var(--warn);
                border:1px solid rgba(251,146,60,0.3); }

.score-row { display:flex; align-items:center; gap:1.2rem; margin:0.6rem 0 1.5rem; }
.score-num { font-family:var(--fh); font-size:2.6rem; font-weight:800; line-height:1; }
.score-meta{ font-size:0.75rem; color:var(--text-mid); margin-top:2px; }
.sbar-bg   { flex:1; height:9px; background:rgba(255,255,255,0.08); border-radius:99px; overflow:hidden; }
.sbar-fill { height:100%; border-radius:99px; transition:width 0.9s cubic-bezier(.4,0,.2,1); }

/* metric tiles */
.mg { display:grid; grid-template-columns:repeat(auto-fill,minmax(120px,1fr)); gap:0.65rem; margin:0.8rem 0; }
.mt { background:rgba(255,255,255,0.03); border:1px solid var(--border); border-radius:14px;
      padding:0.85rem 0.7rem; text-align:center;
      transition:border-color 0.2s, transform 0.2s; }
.mt:hover { border-color:var(--border-hi); transform:translateY(-2px); }
.mt-icon { font-size:1.35rem; margin-bottom:0.3rem; }
.mt-val  { font-family:var(--fh); font-size:1.2rem; font-weight:700; color:var(--text-hi); }
.mt-lbl  { font-size:0.65rem; color:var(--text-mid); text-transform:uppercase;
           letter-spacing:0.07em; margin-top:3px; }

/* section header */
.shdr { font-family:var(--fh); font-size:0.68rem; font-weight:700;
        letter-spacing:0.12em; text-transform:uppercase; color:var(--text-mid);
        margin:1.5rem 0 0.7rem; display:flex; align-items:center; gap:0.6rem; }
.shdr::after { content:''; flex:1; height:1px; background:var(--border); }

/* tags */
.tag-row { display:flex; flex-wrap:wrap; gap:0.4rem; margin:0.5rem 0; }
.tag { font-size:0.77rem; padding:0.28rem 0.75rem; border-radius:8px; font-weight:500; }
.tag.issue  { background:rgba(251,146,60,0.12); color:var(--warn); border:1px solid rgba(251,146,60,0.25); }
.tag.good   { background:rgba(52,211,153,0.10); color:var(--accent3); border:1px solid rgba(52,211,153,0.25); }
.tag.health { background:rgba(248,113,113,0.10); color:var(--danger); border:1px solid rgba(248,113,113,0.25); }

/* clothing card */
.cl-card { background:rgba(56,189,248,0.06); border:1px solid rgba(56,189,248,0.18);
           border-radius:14px; padding:1rem 1.2rem; margin:0.5rem 0; }
.cl-title { font-weight:600; color:var(--accent); font-size:0.92rem; margin-bottom:0.3rem; }
.cl-body  { font-size:0.86rem; color:var(--text-mid); line-height:1.6; }

/* alt windows */
.alt-card {
  background:rgba(255,255,255,0.03); border:1px solid var(--border);
  border-radius:13px; padding:0.85rem 1.1rem; margin:0.4rem 0;
  display:flex; align-items:center; justify-content:space-between;
  transition:border-color 0.2s, background 0.2s;
}
.alt-card:hover { border-color:var(--accent); background:rgba(56,189,248,0.04); }
.alt-time { font-family:var(--fh); font-weight:700; color:var(--accent); font-size:1.05rem; }
.alt-info { font-size:0.8rem; color:var(--text-mid); margin-top:2px; }
.alt-sc   { font-size:0.78rem; color:var(--accent3); font-weight:700; }

/* 7-day grid */
.wk-grid { display:grid; grid-template-columns:repeat(7,1fr); gap:0.5rem; margin:0.7rem 0; }
.wk-day  { background:var(--bg-card); border:1px solid var(--border); border-radius:12px;
           padding:0.75rem 0.35rem; text-align:center;
           transition:border-color 0.2s, background 0.2s; }
.wk-day:hover { border-color:var(--border-hi); background:rgba(255,255,255,0.06); }
.wk-day.today { border-color:var(--accent); background:rgba(56,189,248,0.07); }
.wk-name  { font-size:0.62rem; text-transform:uppercase; letter-spacing:0.08em; color:var(--text-mid); }
.wk-emoji { font-size:1.5rem; margin:0.25rem 0; }
.wk-hi    { font-size:0.9rem; font-weight:700; color:var(--text-hi); }
.wk-lo    { font-size:0.75rem; color:var(--text-mid); }
.wk-rain  { font-size:0.62rem; color:var(--accent); margin-top:0.2rem; }

/* hourly scroll */
.h-scroll { display:flex; gap:0.4rem; overflow-x:auto; padding-bottom:0.6rem;
            scrollbar-width:thin; scrollbar-color:var(--border) transparent; }
.h-card { flex:0 0 76px; background:var(--bg-card); border:1px solid var(--border);
          border-radius:12px; padding:0.65rem 0.35rem; text-align:center;
          transition:border-color 0.2s; }
.h-card.hi { border-color:var(--accent); background:rgba(56,189,248,0.09); }
.h-card:hover { border-color:var(--border-hi); }
.h-t  { font-size:0.6rem; color:var(--text-mid); text-transform:uppercase; }
.h-e  { font-size:1.25rem; margin:0.2rem 0; }
.h-v  { font-size:0.85rem; font-weight:700; color:var(--text-hi); }
.h-r  { font-size:0.58rem; color:var(--accent); }

/* tabs */
.stTabs [data-baseweb="tab-list"] { background:transparent !important; gap:0.5rem; }
.stTabs [data-baseweb="tab"] { background:var(--bg-card) !important; border:1px solid var(--border) !important;
  border-radius:10px !important; color:var(--text-mid) !important; font-family:var(--fb) !important; }
.stTabs [aria-selected="true"] { background:rgba(56,189,248,0.1) !important;
  border-color:rgba(56,189,248,0.4) !important; color:var(--accent) !important; }
.stTabs [data-baseweb="tab-panel"] { padding-top:1rem !important; }

/* expander */
details { background:var(--bg-card) !important; border:1px solid var(--border) !important;
          border-radius:12px !important; padding:0.3rem 1rem !important; }
summary { color:var(--text-mid) !important; font-size:0.86rem !important; }

/* dataframe */
[data-testid="stDataFrame"] { background:var(--bg-card) !important; border-radius:12px !important; }

hr { border-color:var(--border) !important; margin:1rem 0 !important; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown('<div class="sb-logo">⛅ WeatherMind AI</div>', unsafe_allow_html=True)
    st.markdown('<div class="sb-tag">Agentic · ReAct · v2.0</div>', unsafe_allow_html=True)
    st.markdown("---")

    # LLM config
    st.markdown("**🤖 LLM Provider** *(optional)*")
    provider_choice = st.selectbox("Provider", ["None (rule-based)","Anthropic Claude","Google Gemini"],
                                   index=0, label_visibility="collapsed")
    api_key_input = ""
    if provider_choice != "None (rule-based)":
        lbl = "Anthropic API Key" if "Anthropic" in provider_choice else "Gemini API Key"
        api_key_input = st.text_input(lbl, type="password", placeholder="Paste key…")
        if api_key_input:
            st.success("Key saved ✓", icon="🔑")

    st.markdown("---")

    # Live weather widget
    st.markdown("**🌍 Quick Weather Check**")
    sw_city = st.text_input("City", value="Lahore", label_visibility="collapsed",
                             placeholder="Any city…", key="sw_city_in")
    if sw_city:
        try:
            with st.spinner(""):
                sg  = geocode_location(sw_city)
                sh  = fetch_hourly_weather(sg["lat"], sg["lon"], sg["timezone"])
                nh  = datetime.datetime.now().hour
                sw  = sh.get(nh) or sh[min(sh.keys(), key=lambda x: abs(x - nh))]
            sa  = fetch_air_quality(sg["lat"], sg["lon"])
            cl  = get_clothing_advice(sw["feels_like"], sw["precipitation"], sw["windspeed"])
            st.markdown(f"""
            <div class="sw">
              <div class="sw-city">📍 {sg['name']}, {sg['country']}</div>
              <div class="sw-temp">{sw['temperature']}°</div>
              <div class="sw-cond">{sw['emoji']} {sw['condition']}</div>
              <div class="sw-grid">
                <div class="sw-s"><div class="sw-sv">💧 {sw['humidity']}%</div><div class="sw-sl">Humidity</div></div>
                <div class="sw-s"><div class="sw-sv">💨 {sw['windspeed']}</div><div class="sw-sl">km/h Wind</div></div>
                <div class="sw-s"><div class="sw-sv">☀️ {sw['uv_index']}</div><div class="sw-sl">UV Index</div></div>
                <div class="sw-s"><div class="sw-sv">{sa['icon']} {sa['label']}</div><div class="sw-sl">Air Quality</div></div>
              </div>
              <div class="sw-tip">{cl[0]} {cl[2]}</div>
            </div>
            """, unsafe_allow_html=True)
        except Exception as e:
            st.caption(f"⚠️ {e}")

    st.markdown("---")
    st.markdown("**📖 ReAct Loop**")
    st.markdown("""
<div style="font-size:0.8rem;color:#94a3b8;line-height:2.0;">
🧠 <b style="color:#f0f6ff">Thought</b> — reason about task<br>
⚙️ <b style="color:#f0f6ff">Action</b> — invoke a tool<br>
👁️ <b style="color:#f0f6ff">Observe</b> — read result<br>
🔁 <b style="color:#f0f6ff">Repeat</b> — until data complete<br>
✅ <b style="color:#f0f6ff">Answer</b> — synthesise response
</div>
""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**🛠️ Agent Tools**")
    st.markdown("""
<div style="font-size:0.78rem;color:#94a3b8;line-height:2.1;">
🗺️ Open-Meteo Geocoding<br>
☁️ Hourly Forecast (11 vars)<br>
💨 Air Quality / AQI<br>
📅 7-Day Daily Summary<br>
⚖️ Activity Suitability v2<br>
👕 Clothing Adviser<br>
☀️ UV Risk Adviser<br>
🔎 Alternative Window Scan
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  LLM CLIENT INIT
# ══════════════════════════════════════════════════════════════════════════════

llm_client = llm_provider = None
if api_key_input.strip():
    if "Anthropic" in provider_choice and ANTHROPIC_AVAILABLE:
        try:
            llm_client   = anthropic.Anthropic(api_key=api_key_input.strip())
            llm_provider = "anthropic"
        except Exception as e:
            st.sidebar.error(f"Anthropic error: {e}")
    elif "Gemini" in provider_choice and GEMINI_AVAILABLE:
        try:
            genai.configure(api_key=api_key_input.strip())
            llm_client   = genai.GenerativeModel("gemini-1.5-flash")
            llm_provider = "gemini"
        except Exception as e:
            st.sidebar.error(f"Gemini error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN PAGE
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="hero">
  <div class="hero-badge">⚡ ReAct Agentic AI · 8-Tool Reasoning System</div>
  <h1>Weather<span>Mind</span> AI</h1>
  <p>Tell me your plans — I'll reason through conditions, score activity suitability,
     check air quality, UV risk, clothing, and find you the optimal time window.</p>
</div>
""", unsafe_allow_html=True)

EXAMPLES = [
    ("🏃", "Run in Lahore at 6 PM"),
    ("🚴", "Cycling in Karachi at 8 AM"),
    ("🧘", "Yoga in Islamabad this morning"),
    ("🏏", "Cricket in Rawalpindi at 3 PM"),
    ("🧺", "Picnic in Multan this afternoon"),
    ("⛰️", "Hiking in Quetta tomorrow morning"),
]
cols = st.columns(len(EXAMPLES))
for col, (icon, txt) in zip(cols, EXAMPLES):
    with col:
        if st.button(f"{icon} {txt}", use_container_width=True):
            st.session_state["prefill"] = txt

st.markdown("")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prefill    = st.session_state.pop("prefill", "")
user_input = st.chat_input("Describe your plan… e.g. 'run in Lahore at 6 PM' or 'cricket in Rawalpindi at 3 PM'")
if prefill and not user_input:
    user_input = prefill


# ══════════════════════════════════════════════════════════════════════════════
#  RENDER HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def render_thought(entry: dict):
    css = {"thought":"tlog","action":"tlog action",
           "observation":"tlog observation","error":"tlog error"}.get(entry["type"],"tlog")
    st.markdown(f"""
    <div class="{css}">
      <div class="tlog-lbl">{entry.get('icon','')} {entry.get('label','')}</div>
      <div class="tlog-body">{entry.get('body','')}</div>
    </div>""", unsafe_allow_html=True)


def render_answer(ans: dict):
    ev    = ans["evaluation"]
    wx    = ans["weather"]
    alts  = ans["alternatives"]
    hour  = ans["hour"]
    geo   = ans["location_info"]
    intent= ans["intent"]
    aqi   = ans["aqi"]
    cl    = ans["clothing"]
    uv    = ans["uv_advice"]
    week  = ans["week_forecast"]
    snap  = ans["hourly_snapshot"]

    score   = ev["score"]
    go      = ev["suitable"]
    bar_col = "#34d399" if score>=75 else "#fb923c" if score>=50 else "#f87171"
    v_cls   = "go" if go else "nogo"
    v_txt   = "✅ GO — Conditions Suitable" if go else "⚠️ NO-GO — Conditions Poor"
    DAY_NMS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

    # natural response
    st.markdown(f'<div class="nat-resp">{ans["natural_response"]}</div>',
                unsafe_allow_html=True)

    # decision card
    st.markdown(f"""
    <div class="dcard">
      <div class="dcard-head">
        <div class="dcard-icon">{wx['emoji']}</div>
        <div>
          <div class="dcard-title">{intent.get('activity','Activity').title()} in {geo['name']}</div>
          <div class="dcard-sub">📍 {geo['name']}, {geo['admin1']}, {geo['country']}
            &nbsp;|&nbsp; 🕐 {hour:02d}:00 &nbsp;|&nbsp; 📏 {geo['elevation']}m</div>
        </div>
      </div>
      <span class="verdict {v_cls}">{v_txt}</span>
      <div class="score-row">
        <div>
          <div class="score-num" style="color:{bar_col}">{score}</div>
          <div class="score-meta">Grade {ev['grade']} · out of 100</div>
        </div>
        <div class="sbar-bg">
          <div class="sbar-fill" style="width:{score}%;background:{bar_col}"></div>
        </div>
      </div>
      <div class="mg">
        <div class="mt"><div class="mt-icon">🌡️</div><div class="mt-val">{wx['temperature']}°C</div><div class="mt-lbl">Temperature</div></div>
        <div class="mt"><div class="mt-icon">🤔</div><div class="mt-val">{wx['feels_like']}°C</div><div class="mt-lbl">Feels Like</div></div>
        <div class="mt"><div class="mt-icon">🌧️</div><div class="mt-val">{wx['precipitation']}mm</div><div class="mt-lbl">Rain ({wx['precip_prob']}%)</div></div>
        <div class="mt"><div class="mt-icon">💨</div><div class="mt-val">{wx['windspeed']}</div><div class="mt-lbl">km/h Wind</div></div>
        <div class="mt"><div class="mt-icon">💨</div><div class="mt-val">{wx['windgusts']}</div><div class="mt-lbl">km/h Gusts</div></div>
        <div class="mt"><div class="mt-icon">💧</div><div class="mt-val">{wx['humidity']}%</div><div class="mt-lbl">Humidity</div></div>
        <div class="mt"><div class="mt-icon">☀️</div><div class="mt-val">{wx['uv_index']}</div><div class="mt-lbl">UV Index</div></div>
        <div class="mt"><div class="mt-icon">👁️</div><div class="mt-val">{wx['visibility']}km</div><div class="mt-lbl">Visibility</div></div>
        <div class="mt"><div class="mt-icon">{aqi['icon']}</div><div class="mt-val" style="font-size:0.85rem">{aqi['label']}</div><div class="mt-lbl">Air Quality</div></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Analysis tags
    if ev["issues"] or ev["positives"] or ev["health_flags"]:
        st.markdown('<div class="shdr">Analysis</div>', unsafe_allow_html=True)
        tags = ""
        for t in ev["issues"]:      tags += f'<span class="tag issue">⚠️ {t}</span>'
        for t in ev["positives"]:   tags += f'<span class="tag good">✓ {t}</span>'
        for t in ev["health_flags"]:tags += f'<span class="tag health">🚨 {t}</span>'
        st.markdown(f'<div class="tag-row">{tags}</div>', unsafe_allow_html=True)

    # Clothing
    st.markdown('<div class="shdr">Clothing & UV</div>', unsafe_allow_html=True)
    uv_row = f'<div class="cl-body" style="color:#38bdf8;margin-top:0.4rem">☀️ {uv}</div>' if uv else ""
    st.markdown(f"""
    <div class="cl-card">
      <div class="cl-title">{cl[0]} {cl[1]} — What to Wear</div>
      <div class="cl-body">{cl[2]}</div>
      {uv_row}
    </div>""", unsafe_allow_html=True)

    # Alternative windows
    if alts:
        st.markdown('<div class="shdr">Better Time Windows</div>', unsafe_allow_html=True)
        for alt in alts:
            bc2 = "#34d399" if alt["score"]>=75 else "#fb923c"
            st.markdown(f"""
            <div class="alt-card">
              <div>
                <div class="alt-time">🕐 {alt['time_label']}</div>
                <div class="alt-info">{alt['weather']['emoji']} {alt['weather']['condition']}
                  · {alt['weather']['temperature']}°C · 💧{alt['weather']['humidity']}%
                  · 🌧️{alt['weather']['precipitation']}mm</div>
              </div>
              <div style="text-align:right">
                <div class="alt-sc">Score {alt['score']}/100</div>
                <div style="width:80px;height:5px;background:rgba(255,255,255,0.08);
                            border-radius:99px;margin-top:5px;overflow:hidden">
                  <div style="width:{alt['score']}%;height:100%;background:{bc2};border-radius:99px"></div>
                </div>
              </div>
            </div>""", unsafe_allow_html=True)

    # Tabs
    st.markdown("")
    tab1, tab2 = st.tabs(["⏱️ Today's Hourly Timeline", "📅 7-Day Forecast"])

    with tab1:
        if snap:
            html = '<div class="h-scroll">'
            for h, hw in sorted(snap.items()):
                hi    = "hi" if h == hour else ""
                rl    = f"🌧️{hw['precipitation']}mm" if hw["precipitation"]>0 else f"☁️{hw['precip_prob']}%"
                html += f"""<div class="h-card {hi}">
                  <div class="h-t">{h:02d}:00</div>
                  <div class="h-e">{hw['emoji']}</div>
                  <div class="h-v">{hw['temperature']}°</div>
                  <div class="h-r">{rl}</div>
                </div>"""
            html += '</div>'
            st.markdown(html, unsafe_allow_html=True)

    with tab2:
        if week:
            wk = '<div class="wk-grid">'
            for day in week:
                dt     = datetime.date.fromisoformat(day["date"])
                dn     = DAY_NMS[dt.weekday()]
                today  = dt == datetime.date.today()
                tc     = "today" if today else ""
                label  = "TODAY" if today else dn
                wk += f"""<div class="wk-day {tc}">
                  <div class="wk-name">{label}</div>
                  <div class="wk-emoji">{day['emoji']}</div>
                  <div class="wk-hi">{day['temp_max']}°</div>
                  <div class="wk-lo">{day['temp_min']}°</div>
                  <div class="wk-rain">🌧️{day['rain_prob']}%</div>
                </div>"""
            wk += '</div>'
            st.markdown(wk, unsafe_allow_html=True)

            import pandas as pd
            df = pd.DataFrame([{
                "Date":      d["date"],
                "Weather":   f"{d['emoji']} {d['condition']}",
                "Max °C":    d["temp_max"],
                "Min °C":    d["temp_min"],
                "Rain mm":   d["rain_sum"],
                "Rain %":    f"{d['rain_prob']}%",
                "Wind km/h": d["wind_max"],
                "UV Max":    d["uv_max"],
            } for d in week])
            with st.expander("📊 Detailed 7-Day Table", expanded=False):
                st.dataframe(df, hide_index=True, use_container_width=True)
        else:
            st.info("7-day forecast unavailable.")


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN INTERACTION
# ══════════════════════════════════════════════════════════════════════════════

if user_input:
    st.session_state.messages.append({"role":"user","content":user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.status("🧠 Agent is reasoning…", expanded=True) as status:
            agent  = WeatherAgent(llm_client=llm_client, llm_provider=llm_provider)
            answer = error = None

            for step in agent.run(user_input):
                if step["type"] == "answer":
                    answer = step
                    status.update(label="✅ Analysis complete", state="complete", expanded=False)
                elif step["type"] == "error":
                    error = step["message"]
                    status.update(label="❌ Error", state="error", expanded=True)
                    st.error(step["message"])
                    break
                else:
                    render_thought(step)

        if answer:
            render_answer(answer)
            st.session_state.messages.append({
                "role": "assistant",
                "content": answer["natural_response"],
            })
        elif not error:
            st.warning("No answer produced — please rephrase your query.")