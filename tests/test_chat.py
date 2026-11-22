import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
os.environ["CHAT_DISABLE_LLM"] = "1"

import _advisor  # noqa: E402
import chat  # noqa: E402


def now():
    return datetime.now(timezone.utc).isoformat()


def ids(reading, crop="maize"):
    return [f["id"] for f in _advisor.assess(reading, crop)]


def test_dry_soil_triggers_irrigation_with_litres():
    f = _advisor.assess({"ts": now(), "soil_moisture": 15, "air_temperature": 25, "air_humidity": 60, "pump": "off"})
    assert f[0]["id"] == "irrigate" and f[0]["level"] == "action"
    assert "litres" in f[0]["en"] and "lita" in f[0]["sw"]


def test_rain_postpones_irrigation():
    assert "dry_but_raining" in ids({"ts": now(), "soil_moisture": 15, "rainfall": 5})


def test_wet_soil_with_pump_on():
    got = ids({"ts": now(), "soil_moisture": 52, "pump": "on"})
    assert "waterlogged" in got and "pump_off" in got


def test_blight_only_for_susceptible_crops():
    r = {"ts": now(), "soil_moisture": 33, "air_temperature": 20, "air_humidity": 94}
    assert "blight" in ids(r, "tomato")
    assert "blight" not in ids(r, "maize") and "fungal" in ids(r, "maize")


def test_heat_and_stale():
    assert "heat" in ids({"ts": now(), "air_temperature": 36, "soil_moisture": 30})
    assert "stale" in ids({"ts": "2020-01-01T00:00:00Z", "soil_moisture": 30})


def test_no_data():
    assert ids(None) == ["no_data"]


def test_answer_falls_back_to_rules_in_swahili():
    res = chat.answer({"message": "Nimwagilie?", "lang": "sw", "crop": "beans",
                       "reading": {"ts": now(), "soil_moisture": 12}})
    assert res["mode"] == "rules" and "Mwagilia" in res["reply"]


def test_bad_crop_defaults_to_maize():
    assert chat.answer({"crop": "rocks"})["crop"] == "maize"


def test_rules_mode_answers_the_topic_asked():
    r = {"ts": now(), "soil_moisture": 15, "air_temperature": 22, "air_humidity": 60}
    disease = chat.answer({"message": "Is there a disease risk?", "reading": r})["reply"]
    assert "disease risk" in disease and "Irrigate" not in disease
    water = chat.answer({"message": "Nimwagilie leo?", "lang": "sw", "reading": r})["reply"]
    assert "Mwagilia" in water
