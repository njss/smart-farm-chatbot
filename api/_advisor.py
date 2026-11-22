"""Rule-based agronomic advisor.

Turns one sensor reading into a short list of findings, in English and Swahili.
The chatbot always runs these rules first:
  * with no LLM available, the findings ARE the answer (works offline, costs nothing);
  * with an LLM, the findings are given to the model as grounded facts.

Students: this is the file to improve during the workshop. Every threshold is a
plain number in CROPS below, so local agronomists and farmers can correct it.
Values are indicative starting points for smallholder plots in the Tanzanian
southern highlands, not certified recommendations.
"""

from __future__ import annotations

from datetime import datetime, timezone

# soil moisture in % volumetric water content (VWC); temperatures in degrees Celsius
CROPS = {
    "maize":     {"sw": "mahindi",    "moist": (25, 40), "hot": 35, "cold": 10, "root_mm": 400, "blight": False},
    "beans":     {"sw": "maharage",   "moist": (25, 38), "hot": 30, "cold": 10, "root_mm": 300, "blight": False},
    "tomato":    {"sw": "nyanya",     "moist": (28, 42), "hot": 32, "cold": 10, "root_mm": 300, "blight": True},
    "potato":    {"sw": "viazi",      "moist": (28, 40), "hot": 29, "cold": 5,  "root_mm": 300, "blight": True},
    "sunflower": {"sw": "alizeti",    "moist": (20, 35), "hot": 35, "cold": 8,  "root_mm": 500, "blight": False},
    "vegetables": {"sw": "mbogamboga", "moist": (30, 42), "hot": 30, "cold": 8,  "root_mm": 200, "blight": False},
}

STALE_AFTER_MIN = 15


def _finding(fid, level, en, sw):
    return {"id": fid, "level": level, "en": en, "sw": sw}


def _age_minutes(ts: str | None) -> float | None:
    if not ts:
        return None
    try:
        t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - t).total_seconds() / 60


def assess(reading: dict | None, crop: str = "maize") -> list[dict]:
    """Return findings ordered from most to least urgent.

    level: "action" (do something today), "watch" (keep an eye on it), "ok".
    """
    if not reading:
        return [_finding("no_data", "watch",
                         "I have no sensor data yet, so I can only give general advice.",
                         "Bado sina data ya vihisi, kwa hiyo naweza kutoa ushauri wa jumla tu.")]

    c = CROPS.get(crop, CROPS["maize"])
    crop_en, crop_sw = crop if crop in CROPS else "maize", c["sw"]
    lo, hi = c["moist"]
    out: list[dict] = []

    sm = reading.get("soil_moisture")
    t = reading.get("air_temperature")
    rh = reading.get("air_humidity")
    rain = reading.get("rainfall") or 0
    pump = reading.get("pump") == "on"

    age = _age_minutes(reading.get("ts"))
    if age is not None and age > STALE_AFTER_MIN:
        out.append(_finding("stale", "watch",
                            f"The last sensor reading is {int(age)} minutes old. Check that the sensor kit is on.",
                            f"Usomaji wa mwisho wa vihisi una dakika {int(age)}. Hakikisha kifaa cha vihisi kimewashwa."))

    if sm is not None:
        if sm < lo:
            deficit = (lo + hi) / 2 - sm
            litres = round(deficit / 100 * c["root_mm"])  # 1 mm of water = 1 litre per m2
            split_en = split_sw = ""
            if litres > 30:  # large deficits are refilled in two waterings to avoid run-off
                split_en = f" Split it into two waterings of about {round(litres / 2)} litres."
                split_sw = f" Gawanya katika umwagiliaji mara mbili wa takriban lita {round(litres / 2)} kila mara."
            if rain >= 2:
                out.append(_finding("dry_but_raining", "watch",
                                    f"The soil is dry ({sm}% moisture) but it is raining now. Wait and check again after the rain.",
                                    f"Udongo ni mkavu (unyevu {sm}%) lakini mvua inanyesha sasa. Subiri, kisha angalia tena baada ya mvua."))
            elif pump:
                out.append(_finding("dry_pump_on", "watch",
                                    f"The soil is dry ({sm}%) and the pump is already on. Keep watering until moisture reaches about {lo + 5}%.",
                                    f"Udongo ni mkavu ({sm}%) na pampu tayari inafanya kazi. Endelea kumwagilia hadi unyevu ufike karibu {lo + 5}%."))
            else:
                out.append(_finding("irrigate", "action",
                                    f"The soil is too dry for {crop_en} ({sm}% moisture, best is {lo} to {hi}%). Irrigate about {litres} litres per square metre, early in the morning or in the evening." + split_en,
                                    f"Udongo ni mkavu mno kwa {crop_sw} (unyevu {sm}%, bora ni {lo} hadi {hi}%). Mwagilia takriban lita {litres} kwa kila mita ya mraba, asubuhi na mapema au jioni." + split_sw))
        elif sm > hi + 8:
            out.append(_finding("waterlogged", "action",
                                f"The soil is waterlogged ({sm}% moisture). Do not irrigate. Open drainage channels so roots do not rot.",
                                f"Udongo umejaa maji ({sm}% unyevu). Usimwagilie. Fungua mifereji ya kutoa maji ili mizizi isioze."))
        elif sm > hi:
            out.append(_finding("wet", "watch",
                                f"The soil is wetter than needed ({sm}%). No irrigation is needed today.",
                                f"Udongo una unyevu zaidi ya unaohitajika ({sm}%). Hakuna haja ya kumwagilia leo."))
        else:
            out.append(_finding("moisture_ok", "ok",
                                f"Soil moisture is good for {crop_en} ({sm}%). No irrigation is needed now.",
                                f"Unyevu wa udongo ni mzuri kwa {crop_sw} ({sm}%). Hakuna haja ya kumwagilia sasa."))
        if pump and sm >= hi:
            out.append(_finding("pump_off", "action",
                                "The pump is on but the soil is already wet. Switch the pump off to save water.",
                                "Pampu inafanya kazi lakini udongo tayari una maji ya kutosha. Zima pampu ili kuokoa maji."))

    if t is not None:
        if t >= c["hot"]:
            out.append(_finding("heat", "action",
                                f"It is very hot ({t} °C) for {crop_en}. Mulch the soil, water in the evening, and shade young seedlings.",
                                f"Kuna joto kali ({t} °C) kwa {crop_sw}. Weka matandazo kwenye udongo, mwagilia jioni, na kivulia miche michanga."))
        elif t <= c["cold"]:
            out.append(_finding("cold", "watch",
                                f"It is cold ({t} °C). Growth will be slow. Protect seedlings at night if frost is possible.",
                                f"Kuna baridi ({t} °C). Ukuaji utakuwa wa polepole. Linda miche usiku kama kuna uwezekano wa barafu."))

    if rh is not None and t is not None:
        if rh >= 90 and 15 <= t <= 28:
            if c["blight"]:
                out.append(_finding("blight", "action",
                                    f"Humid and mild weather ({rh}% humidity, {t} °C) favours late blight on {crop_en}. Check the leaves today for dark, wet-looking spots and ask your extension officer about prevention.",
                                    f"Hali ya unyevu mwingi na joto la wastani ({rh}%, {t} °C) inapendelea ugonjwa wa baka-jani chelewa kwa {crop_sw}. Kagua majani leo kuona madoa meusi yenye unyevu, na muulize afisa ugani kuhusu kinga."))
            else:
                out.append(_finding("fungal", "watch",
                                    f"Very humid air ({rh}%) raises the risk of fungal disease. Check leaves and avoid wetting them when you irrigate.",
                                    f"Hewa yenye unyevu mwingi ({rh}%) huongeza hatari ya magonjwa ya ukungu. Kagua majani na usiyalowanishe unapomwagilia."))
        elif rh <= 30 and t >= 28:
            out.append(_finding("dry_air", "watch",
                                f"The air is hot and dry ({t} °C, {rh}% humidity), so water evaporates fast. Irrigate at the base of plants, not on the leaves.",
                                f"Hewa ni ya joto na kavu ({t} °C, unyevu {rh}%), kwa hiyo maji huvukiza haraka. Mwagilia kwenye shina la mmea, si juu ya majani."))

    if rain >= 10:
        out.append(_finding("heavy_rain", "watch",
                            f"Heavy rain now ({rain} mm per hour). Keep drainage channels open and do not apply fertiliser today, it will wash away.",
                            f"Mvua kubwa inanyesha sasa ({rain} mm kwa saa). Hakikisha mifereji iko wazi na usiweke mbolea leo, itasombwa na maji."))

    order = {"action": 0, "watch": 1, "ok": 2}
    out.sort(key=lambda f: order[f["level"]])
    return out


# Simple keyword intent detection for the rules-only mode (English and Swahili).
INTENTS = {
    "water":   (("irrigat", "water", "dry", "moist", "pump", "mwagili", "maji", "kavu", "unyevu", "pampu"),
                {"irrigate", "dry_but_raining", "dry_pump_on", "waterlogged", "wet", "moisture_ok", "pump_off", "heavy_rain", "dry_air"}),
    "disease": (("disease", "blight", "fung", "leaf", "leaves", "ugonjwa", "magonjwa", "ukungu", "majani", "baka"),
                {"blight", "fungal"}),
    "heat":    (("hot", "heat", "temperat", "cold", "frost", "joto", "baridi", "jua"),
                {"heat", "cold", "dry_air"}),
    "rain":    (("rain", "mvua", "fertili", "mbolea"), {"heavy_rain", "dry_but_raining"}),
}

NOTHING_FOUND = {
    "disease": ("The current humidity and temperature do not signal a high disease risk. Keep checking leaves weekly.",
                "Unyevu na joto la sasa haviashirii hatari kubwa ya magonjwa. Endelea kukagua majani kila wiki."),
    "heat":    ("The temperature is within a safe range for your crop right now.",
                "Joto liko katika kiwango salama kwa zao lako kwa sasa."),
    "rain":    ("There is no heavy rain right now.", "Hakuna mvua kubwa kwa sasa."),
}


def detect_intent(message: str) -> str | None:
    text = (message or "").lower()
    for intent, (words, _ids) in INTENTS.items():
        if any(w in text for w in words):
            return intent
    return None


def rules_reply(findings: list[dict], lang: str = "en", message: str = "") -> str:
    """Plain-text answer built only from the findings (no LLM).

    If the question is about a topic (water, disease, heat, rain), only the
    matching findings are shown; otherwise every finding is listed.
    """
    key = 1 if lang == "sw" else 0
    field = "sw" if lang == "sw" else "en"
    always = [f for f in findings if f["id"] in ("stale", "no_data")]
    intent = detect_intent(message)
    if intent:
        chosen = [f for f in findings if f["id"] in INTENTS[intent][1]]
        lines = [f[field] for f in always + chosen]
        if not chosen and intent in NOTHING_FOUND:
            lines.append(NOTHING_FOUND[intent][key])
        if lines:
            return "\n".join(f"• {line}" for line in lines)
    return "\n".join(f"• {f[field]}" for f in findings)
