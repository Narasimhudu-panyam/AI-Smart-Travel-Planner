from datetime import timedelta
import asyncio
import json
import logging
import re
from typing import AsyncIterator

import httpx

from app.config import Settings
from app.models import ItineraryActivity, ItineraryDay, TripPlan, TripRequest

logger = logging.getLogger(__name__)


class AIServiceError(RuntimeError):
    """A safe, user-facing failure from the configured AI provider."""


# Currency exchange rates (relative to USD)
EXCHANGE_RATES = {
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.79,
    "INR": 83.0,
}


def _get_currency_multiplier(currency: str) -> float:
    """Get multiplier to convert costs to the specified currency"""
    return EXCHANGE_RATES.get(currency, 1.0)


def _trip_days(request: TripRequest) -> int:
    return max((request.end_date - request.start_date).days + 1, 1)


def _attractions_for_day(attractions: list, day_index: int, days: int) -> list:
    per_day = max(1, (len(attractions) + days - 1) // days)
    start = day_index * per_day
    return attractions[start : start + per_day]


def _demo_plan(request: TripRequest, weather: dict[str, str | float | None]) -> TripPlan:
    interests = request.interests or ["food", "culture", "landmarks"]
    days = _trip_days(request)
    
    # Convert budget to USD equivalent for calculation, then convert back to selected currency
    currency_multiplier = _get_currency_multiplier(request.currency)
    usd_budget = request.budget / currency_multiplier if currency_multiplier > 0 else request.budget
    daily_budget_usd = round(usd_budget / days, 2)
    
    itinerary = []

    # Use selected attractions if available, otherwise use generic demo activities
    if request.selected_attractions:
        activity_cost_usd = round(usd_budget * 0.24 / len(request.selected_attractions), 2)
        activity_cost = round(activity_cost_usd * currency_multiplier, 2)
        breakfast_cost = round(daily_budget_usd * 0.08 * currency_multiplier, 2)
        lunch_cost = round(daily_budget_usd * 0.14 * currency_multiplier, 2)
        dinner_cost = round(daily_budget_usd * 0.18 * currency_multiplier, 2)
        local_evening_cost = round(daily_budget_usd * 0.10 * currency_multiplier, 2)
        
        for day_index in range(days):
            current_date = request.start_date + timedelta(days=day_index)
            attractions_for_day = _attractions_for_day(request.selected_attractions, day_index, days)
            morning_attraction = attractions_for_day[0] if attractions_for_day else None
            afternoon_attraction = attractions_for_day[1] if len(attractions_for_day) > 1 else None
            evening_attraction = attractions_for_day[2] if len(attractions_for_day) > 2 else None

            activities = [
                ItineraryActivity(
                    time="08:00",
                    place="Breakfast and day briefing",
                    duration="1 hour",
                    description=f"Start with breakfast near your stay and review the route for day {day_index + 1}.",
                    estimated_cost=breakfast_cost,
                )
            ]

            if morning_attraction:
                activities.append(
                    ItineraryActivity(
                        time="09:30",
                        place=morning_attraction.name,
                        duration="2 hours",
                        description=morning_attraction.description or f"Visit {morning_attraction.name} while the day is still fresh.",
                        estimated_cost=activity_cost,
                    )
                )

            activities.append(
                ItineraryActivity(
                    time="12:30",
                    place="Lunch break",
                    duration="1 hour",
                    description="Pause for a local lunch close to the morning stop.",
                    estimated_cost=lunch_cost,
                )
            )

            if afternoon_attraction:
                activities.append(
                    ItineraryActivity(
                        time="14:00",
                        place=afternoon_attraction.name,
                        duration="2 hours",
                        description=afternoon_attraction.description or f"Explore {afternoon_attraction.name} after lunch.",
                        estimated_cost=activity_cost,
                    )
                )
            else:
                activities.append(
                    ItineraryActivity(
                        time="14:00",
                        place="Rest and local exploration",
                        duration="2 hours",
                        description=f"Use this block for shopping, cafe time, or a relaxed walk in {request.destination}.",
                        estimated_cost=local_evening_cost,
                    )
                )

            if evening_attraction:
                evening_place = evening_attraction.name
                evening_description = evening_attraction.description or f"Visit {evening_attraction.name} in the evening."
                evening_cost = activity_cost
            else:
                evening_place = f"Evening experience in {request.destination}"
                evening_description = "Enjoy a sunset viewpoint, local market, waterfront walk, or cultural area before dinner."
                evening_cost = local_evening_cost

            activities.extend(
                [
                    ItineraryActivity(
                        time="17:30",
                        place=evening_place,
                        duration="1.5 hours",
                        description=evening_description,
                        estimated_cost=evening_cost,
                    ),
                    ItineraryActivity(
                        time="20:00",
                        place="Dinner and night walk",
                        duration="1.5 hours",
                        description="End the day with dinner and a relaxed walk near a safe, lively area.",
                        estimated_cost=dinner_cost,
                    ),
                ]
            )

            itinerary.append(
                ItineraryDay(
                    day=day_index + 1,
                    date=current_date,
                    activities=activities,
                )
            )
    else:
        # Generic demo itinerary when no attractions selected
        for index in range(days):
            current_date = request.start_date + timedelta(days=index)
            activity_cost_usd = round(daily_budget_usd * 0.22, 2)
            activity_cost = round(activity_cost_usd * currency_multiplier, 2)
            itinerary.append(
                ItineraryDay(
                    day=index + 1,
                    date=current_date,
                    activities=[
                        ItineraryActivity(
                            time="08:00",
                            place="Breakfast and route planning",
                            duration="1 hour",
                            description=f"Start the day with breakfast and review the plan for {request.destination}.",
                            estimated_cost=round(daily_budget_usd * 0.08 * currency_multiplier, 2),
                        ),
                        ItineraryActivity(
                            time="09:30",
                            place=f"Popular Spot {index + 1}",
                            duration="2 hours",
                            description=f"Explore a signature attraction in {request.destination}.",
                            estimated_cost=activity_cost,
                        ),
                        ItineraryActivity(
                            time="12:30",
                            place="Lunch",
                            duration="1 hour",
                            description="Local restaurant",
                            estimated_cost=activity_cost,
                        ),
                        ItineraryActivity(
                            time="14:00",
                            place=f"Afternoon Experience {index + 1}",
                            duration="2 hours",
                            description=f"Visit another sightseeing area, museum, market, or cultural spot in {request.destination}.",
                            estimated_cost=activity_cost,
                        ),
                        ItineraryActivity(
                            time="17:30",
                            place=f"Evening Activity {index + 1}",
                            duration="1.5 hours",
                            description="Sunset or cultural experience",
                            estimated_cost=activity_cost,
                        ),
                        ItineraryActivity(
                            time="20:00",
                            place="Dinner and night walk",
                            duration="1.5 hours",
                            description="Dinner followed by a relaxed walk in a safe, lively area.",
                            estimated_cost=round(daily_budget_usd * 0.18 * currency_multiplier, 2),
                        ),
                    ],
                )
            )

    # Calculate budget breakdown in selected currency
    accommodation_usd = round(usd_budget * 0.38, 2)
    food_usd = round(usd_budget * 0.24, 2)
    activities_usd = round(usd_budget * 0.24, 2)
    transport_usd = round(usd_budget * 0.14, 2)
    
    accommodation = round(accommodation_usd * currency_multiplier, 2)
    food = round(food_usd * currency_multiplier, 2)
    activities = round(activities_usd * currency_multiplier, 2)
    transport = round(transport_usd * currency_multiplier, 2)

    attraction_names = [a.name for a in request.selected_attractions] if request.selected_attractions else interests
    
    return TripPlan(
        destination=request.destination,
        summary=f"A {days}-day {request.travel_style} itinerary visiting {len(attraction_names)} attractions for {request.travelers} traveler(s).",
        currency=request.currency,
        budget_breakdown={
            "accommodation": accommodation,
            "food": food,
            "activities": activities,
            "transport": transport,
        },
        weather=weather,
        itinerary=itinerary,
        selected_attractions=request.selected_attractions,
        packing_tips=[
            "Keep digital copies of ID, bookings, and emergency contacts.",
            "Pack comfortable walking shoes and a compact power bank.",
            "Carry weather-appropriate layers based on the latest forecast.",
        ],
        local_tips=[
            "Book high-demand experiences early.",
            "Use public transport or verified ride apps for predictable costs.",
            "Keep one flexible block each day for delays or spontaneous discoveries.",
        ],
        map_query=request.destination,
        ai_provider="demo",
    )


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("AI response did not contain JSON")
    return json.loads(match.group(0))


def _prompt(request: TripRequest, weather: dict[str, str | float | None]) -> str:
    attractions_list = ""
    
    if request.selected_attractions:
        attractions_list = "\n".join([f"- {a.name}" for a in request.selected_attractions])
        attractions_instruction = """
CRITICAL INSTRUCTIONS:
• Visit ONLY these attractions. Do not include any other places.
• Arrange attractions based on logical travel order to minimize backtracking.
• Include realistic travel time between attractions (15-30 minutes).
• Allocate realistic visiting durations for each attraction (typically 1-3 hours).
• Include breakfast, lunch, and dinner recommendations at nearby restaurants.
• Respect typical opening hours and plan activities accordingly.
• Consider weather conditions when scheduling outdoor vs indoor activities.
• Keep total expenses within the provided budget.
• Generate a detailed day-wise itinerary with specific times."""
    else:
        attractions_list = "No attractions selected"
        attractions_instruction = "Create a general travel itinerary based on interests and travel style."

    full_day_instruction = """
FULL-DAY PLANNER REQUIREMENTS:
- Build every day from morning to night, not only 09:00 to 13:00.
- Start around 08:00 with breakfast or a short day briefing.
- Include morning sightseeing, lunch, afternoon sightseeing, evening experience, and dinner.
- End around 20:00-21:30 with dinner or a safe night walk.
- Use realistic travel/rest buffers between major stops.
- If selected attractions are limited, fill the remaining day with meals, rest, shopping, cafe time, local walking, or safe evening blocks."""
    attractions_instruction = f"{attractions_instruction}\n{full_day_instruction}"
    
    daily_budget = round(request.budget / max((request.end_date - request.start_date).days + 1, 1), 2)
    
    return f"""Create a realistic and detailed full-day travel itinerary using ONLY the selected attractions.

TRIP DETAILS:
Destination: {request.destination}
Dates: {request.start_date} to {request.end_date}
Total Budget: {request.budget} {request.currency}
Daily Budget: ~{daily_budget} {request.currency}
Travelers: {request.travelers}
Travel Style: {request.travel_style}
Interests: {", ".join(request.interests) if request.interests else "general sightseeing, food, culture"}
Weather: {weather}
Notes: {request.notes or "none"}

SELECTED ATTRACTIONS (VISIT ONLY THESE):
{attractions_list}

{attractions_instruction}

Return ONLY valid JSON (no markdown, no code blocks) matching this exact structure:
{{
  "destination": "{request.destination}",
  "summary": "string describing the {len(request.selected_attractions)}-attraction itinerary",
  "currency": "{request.currency}",
  "budget_breakdown": {{"accommodation": number, "food": number, "activities": number, "transport": number}},
  "itinerary": [
    {{
      "day": 1,
      "date": "YYYY-MM-DD",
      "activities": [
        {{
          "time": "HH:MM",
          "place": "attraction name from selected attractions",
          "duration": "time string like '2 hours'",
          "description": "specific details about the visit",
          "estimated_cost": number
        }}
      ]
    }}
  ],
  "packing_tips": ["tip1", "tip2"],
  "local_tips": ["tip1", "tip2"],
  "map_query": "{request.destination}"
}}"""


async def generate_trip_plan(request: TripRequest, weather: dict[str, str | float | None], settings: Settings) -> TripPlan:
    """Generate every itinerary with Gemini; never substitute fabricated plans."""
    if settings.ai_provider.lower() != "gemini":
        raise AIServiceError("Gemini is the required AI provider for itinerary generation.")
    if not settings.gemini_api_key:
        logger.error("Gemini itinerary generation requested without GEMINI_API_KEY configured.")
        raise AIServiceError("AI itinerary generation is unavailable because Gemini is not configured.")
    try:
        text = await _call_gemini(_prompt(request, weather), settings.gemini_api_key)
        payload = _extract_json(text)
        payload["currency"] = request.currency
        payload.setdefault("selected_attractions", [attraction.model_dump(mode="json") for attraction in request.selected_attractions])
        return TripPlan(**payload, weather=weather, ai_provider="gemini")
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        logger.warning("Gemini rejected itinerary generation with HTTP %s.", status_code)
        if status_code in (401, 403):
            raise AIServiceError("Gemini rejected the configured API key. Check GEMINI_API_KEY.") from exc
        raise AIServiceError("Gemini could not generate an itinerary. Please try again shortly.") from exc
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        logger.exception("Gemini itinerary generation failed.")
        raise AIServiceError("Gemini returned an invalid itinerary response. Please try again.") from exc


async def stream_trip_plan(request: TripRequest, weather: dict[str, str | float | None], settings: Settings) -> AsyncIterator[str]:
    """Yield Gemini text chunks while retaining the same final TripPlan payload."""
    if settings.ai_provider.lower() != "gemini" or not settings.gemini_api_key:
        raise AIServiceError("Streaming AI generation is unavailable; using the standard generator.")

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:streamGenerateContent?alt=sse"
    headers = {"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": _prompt(request, weather)}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream("POST", url, headers=headers, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                event = json.loads(line[6:])
                for candidate in event.get("candidates", []):
                    for part in candidate.get("content", {}).get("parts", []):
                        text = part.get("text")
                        if text:
                            yield text


async def _call_gemini(prompt: str, api_key: str) -> str:
    # Use Gemini's rolling Flash alias to avoid pinned-model availability changes.
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    async with httpx.AsyncClient(timeout=45) as client:
        for attempt in range(3):
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code != 503 or attempt == 2:
                break
            delay = attempt + 1
            logger.warning("Gemini is busy; retrying itinerary generation in %s second(s).", delay)
            await asyncio.sleep(delay)
        if response.is_error:
            logger.error("Gemini API response %s: %s", response.status_code, response.text[:1000])
        response.raise_for_status()
        data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


async def _call_openai(prompt: str, api_key: str) -> str:
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a travel planning API. Return strict JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    return data["choices"][0]["message"]["content"]
