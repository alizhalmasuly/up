import json
import os
from urllib.error import URLError
from urllib.request import Request, urlopen

from weather.services import get_weather


def recommend_gear(message, mountain="", season="summer", duration="5", difficulty="moderate", language="ru", latitude=None, longitude=None):
    weather = get_weather(latitude=latitude, longitude=longitude, language=language)
    if weather["available"]:
        weather_context = {
            "ru": f"{weather['temperature']}°C, {weather['condition']}, ветер {weather['wind']} м/с",
            "kk": f"{weather['temperature']}°C, {weather['condition']}, жел {weather['wind']} м/с",
            "en": f"{weather['temperature']}°C, {weather['condition']}, wind {weather['wind']} m/s",
        }.get(language, f"{weather['temperature']}°C, {weather['condition']}, wind {weather['wind']} m/s")
        weather_note = {
            "ru": f"Текущие условия: {weather_context}.",
            "kk": f"Ағымдағы жағдай: {weather_context}.",
            "en": f"Current conditions: {weather_context}.",
        }.get(language, f"Current conditions: {weather_context}.")
    else:
        weather_note = {
            "ru": "Актуальная погода недоступна — проверьте местный прогноз перед выходом.",
            "kk": "Ағымдағы ауа райы қолжетімсіз — жолға шығарда жергілікті болжамды тексеріңіз.",
            "en": "Current weather is unavailable; check the local forecast before setting out.",
        }.get(language, "Current weather is unavailable; check the local forecast before setting out.")
        weather_context = weather_note
    api_key = os.getenv("AI_API_KEY", "").strip()
    if api_key:
        endpoint = os.getenv("AI_API_URL", "https://api.openai.com/v1/chat/completions")
        model = os.getenv("AI_MODEL", "gpt-6-luna")
        language_names = {"ru": "Russian", "kk": "Kazakh", "en": "English"}
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": f"You are a cautious mountain hiking gear assistant. Reply in {language_names.get(language, 'Russian')}. Give concise, practical advice based on route, season, duration, difficulty and the user's existing kit. Mention checking local forecasts and never imply safety is guaranteed."},
                {"role": "user", "content": f"Route: {mountain or 'not specified'}; season: {season}; duration: {duration}; difficulty: {difficulty}; current weather context: {weather_context}. Existing gear: {message}"},
            ],
        }
        if model.startswith("gpt-6-"):
            payload["reasoning_effort"] = "low"
        else:
            payload["temperature"] = 0.4
        request = Request(endpoint, data=json.dumps(payload).encode(), headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=15) as response:
                result = json.loads(response.read())
            return result["choices"][0]["message"]["content"].strip()
        except (URLError, TimeoutError, KeyError, ValueError):
            pass

    lowered = message.casefold()
    present = []
    for words, label in [
        (("boot", "ботин", "етік"), "boots"), (("water", "вода", "су"), "water"),
        (("jacket", "куртк", "күрте"), "jacket"), (("first aid", "аптеч", "дәрі қобди"), "first aid"),
        (("map", "карта", "карта"), "navigation"), (("flashlight", "фонар", "шам"), "light"),
    ]:
        if any(word in lowered for word in words):
            present.append(label)

    missing_by_language = {
        "ru": {"jacket": "непромокаемую куртку", "first aid": "аптечку первой помощи", "navigation": "навигацию и заряженный телефон", "warm": "тёплый слой"},
        "kk": {"jacket": "су өткізбейтін күрте", "first aid": "алғашқы көмек қобдишасы", "navigation": "навигация және қуатталған телефон", "warm": "жылы қабат"},
        "en": {"jacket": "waterproof layer", "first aid": "first-aid kit", "navigation": "navigation and a charged phone", "warm": "warm layer"},
    }
    present_by_language = {
        "ru": {"boots": "ботинки", "water": "вода", "jacket": "куртка", "first aid": "аптечка", "navigation": "навигация", "light": "фонарь"},
        "kk": {"boots": "етік", "water": "су", "jacket": "күрте", "first aid": "дәрі қобдишасы", "navigation": "навигация", "light": "шам"},
        "en": {"boots": "boots", "water": "water", "jacket": "jacket", "first aid": "first-aid kit", "navigation": "navigation", "light": "flashlight"},
    }
    missing_labels = missing_by_language.get(language, missing_by_language["ru"])
    owned_warm_layer = "warm layer" in lowered or "тепл" in lowered or "жылы" in lowered
    missing = [
        label for category, label in missing_labels.items()
        if category not in present and not (category == "warm" and owned_warm_layer)
    ]
    present_labels = present_by_language.get(language, present_by_language["ru"])
    present_text = [present_labels[item] for item in present]
    if language == "kk":
        season_names = {"spring": "көктемде", "summer": "жазда", "autumn": "күзде", "winter": "қыста"}
        difficulties = {"easy": "жеңіл", "moderate": "орташа", "hard": "қиын"}
        return f"Жақсы бастама! {mountain + ' бағытына ' if mountain else ''}{season_names.get(season, 'жолға')} шығатын сапарыңызға жинақталып жатырсыз. Тізіміңізде бар: {', '.join(present_text) if present_text else 'негізгі жабдықтар'}. Қосымша алыңыз: {', '.join(missing) if missing else 'жабдықтарыңыз толық көрінеді'}. {duration} сағаттық, {difficulties.get(difficulty, difficulty)} бағыт үшін су мен жылы қабатты алдын ала жоспарлаңыз. {weather_note}"
    if language == "en":
        difficulties = {"easy": "easy", "moderate": "moderate", "hard": "challenging"}
        return f"Good start{f' for {mountain}' if mountain else ''}. Planning a {duration}-hour {difficulties.get(difficulty, difficulty)} hike in {season} conditions. {weather_note} I spotted: {', '.join(present_text) if present_text else 'some essentials'}. Consider adding: {', '.join(missing) if missing else 'your kit looks well covered'}. Plan water for the route and conditions."
    season_names = {"spring": "весной", "summer": "летом", "autumn": "осенью", "winter": "зимой"}
    difficulties = {"easy": "лёгкий", "moderate": "средний", "hard": "сложный"}
    return f"Хорошее начало{f' для маршрута «{mountain}»' if mountain else ''}. Для похода на {duration} ч. {season_names.get(season, 'в горах')} по маршруту категории «{difficulties.get(difficulty, difficulty)}» учтите запас сил. Уже есть: {', '.join(present_text) if present_text else 'базовое снаряжение'}. Добавьте: {', '.join(missing) if missing else 'похоже, комплект собран'}. {weather_note} Рассчитайте запас воды по условиям маршрута."
