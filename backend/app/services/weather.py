import httpx

from app.config import Settings


async def get_weather(destination: str, settings: Settings) -> dict[str, str | float | None]:
    if not settings.openweather_api_key:
        return {
            "source": "demo",
            "description": "Weather preview unavailable until OpenWeather API is configured.",
            "temperature_c": None,
        }

    params = {
        "q": destination,
        "appid": settings.openweather_api_key,
        "units": "metric",
    }

    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.get("https://api.openweathermap.org/data/2.5/weather", params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError:
        return {
            "source": "demo",
            "description": "Weather service unavailable; using planning fallback.",
            "temperature_c": None,
        }

    weather = data.get("weather", [{}])[0]
    main = data.get("main", {})
    return {
        "source": "openweather",
        "description": weather.get("description", "No description"),
        "temperature_c": main.get("temp"),
    }
