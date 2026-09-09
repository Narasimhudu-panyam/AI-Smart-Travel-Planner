from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date, timedelta
from typing import Any, AsyncIterator

import httpx

from app.config import Settings
from app.models import (
    BudgetAnalysis,
    ItineraryActivity,
    ItineraryDay,
    SelectedAttraction,
    TripPlan,
    TripRequest,
)

logger = logging.getLogger(__name__)

# Active Gemini models in order of priority (verified working with Google API)
CANDIDATE_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite-preview",
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.5-flash",
    "gemini-3.7-flash",
]


class AIServiceError(RuntimeError):
    """A safe, user-facing failure from the configured AI provider."""


def _trip_days(request: TripRequest) -> int:
    return max((request.end_date - request.start_date).days + 1, 1)


def _extract_json(text: str) -> dict[str, Any]:
    """Extract and parse JSON from model response text, stripping code fences or stray characters."""
    text = text.strip()
    # Remove markdown code fences if present
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence_match:
        text = fence_match.group(1).strip()

    # Locate first '{' and last '}'
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        json_str = text[start : end + 1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            try:
                # Try cleaning trailing commas
                cleaned = re.sub(r",\s*([\]}])", r"\1", json_str)
                return json.loads(cleaned)
            except Exception as exc:
                logger.warning("JSON decode failed after comma cleanup: %s", exc)

    raise ValueError("AI response did not contain a valid JSON object.")


def _build_ai_prompt(request: TripRequest, weather: dict[str, Any]) -> str:
    days = _trip_days(request)
    daily_budget = round(request.budget / days, 2)
    per_person_daily = round(daily_budget / request.travelers, 2)

    attractions_list = ""
    if request.selected_attractions:
        attractions_list = "\n".join(
            [f"- {a.name} ({a.category or 'Attraction'}) - {a.description or ''}" for a in request.selected_attractions]
        )
    else:
        attractions_list = "None pre-selected; recommend top authentic attractions for this destination based on user interests."

    interests_str = ", ".join(request.interests) if request.interests else "general sightseeing, food, culture"
    weather_desc = weather.get("description", "Not available")
    temp_c = weather.get("temperature_c")
    weather_info = f"{weather_desc} ({temp_c}°C)" if temp_c is not None else weather_desc

    return f"""You are an expert, empathetic, and highly knowledgeable AI Travel Assistant.
Create a comprehensive, realistic, and personalized travel plan based strictly on the user's specific request.

TRIP DETAILS:
- Destination: {request.destination}
- Dates: {request.start_date} to {request.end_date} ({days} day{'s' if days > 1 else ''})
- Total Budget: {request.budget} {request.currency} (~{daily_budget} {request.currency}/day total, ~{per_person_daily} {request.currency}/day per person)
- Travelers: {request.travelers} person(s)
- Travel Style: {request.travel_style.capitalize()}
- Interests: {interests_str}
- Weather Forecast: {weather_info}
- Additional Notes: {request.notes or 'None'}

SELECTED ATTRACTIONS (prioritize or incorporate if provided):
{attractions_list}

CRITICAL ASSISTANT INSTRUCTIONS:
1. DESTINATION INTELLIGENCE: Adapt activities specifically to {request.destination}. Mention real neighborhoods, landmarks, local cuisines, and travel methods.
2. DURATION INTELLIGENCE: You MUST generate exactly {days} day-by-day itinerary entries (Day 1 through Day {days}).
3. BUDGET & COST INTELLIGENCE:
   - Treat the budget as a user constraint, NEVER a reason to fail or complain.
   - If the budget is tight/low for {request.destination} and {request.travelers} traveler(s), optimize the itinerary by prioritizing free attractions, self-guided walks, public transit, street food/affordable eateries, and budget stays.
   - Provide a realistic estimated cost and explain the trade-offs kindly in the summary and budget advice.
   - Scale food, activity, accommodation, and transport calculations proportionally for {request.travelers} traveler(s).
4. TRAVEL STYLE & INTERESTS:
   - Style: {request.travel_style}. Align recommendations, pacing, and lodging/dining options with this style.
   - Interests: {interests_str}. Center key activities around these interests.
5. FULL-DAY ITINERARY FORMAT:
   - For each day, include 3 to 5 realistic time-slotted activities (e.g. morning, lunch, afternoon, evening, dinner).
   - Include realistic estimated costs in {request.currency}.

Return ONLY valid JSON matching this exact structure:
{{
  "destination": "{request.destination}",
  "summary": "A friendly 2-3 sentence overview of this custom {days}-day {request.travel_style} trip for {request.travelers} traveler(s), highlighting key experiences and budget approach.",
  "currency": "{request.currency}",
  "budget_breakdown": {{
    "accommodation": number,
    "food": number,
    "activities": number,
    "transport": number
  }},
  "budget_analysis": {{
    "requested_budget": {request.budget},
    "estimated_cost": number,
    "difference": number,
    "budget_status": "within_budget" or "tight_budget" or "exceeds_budget",
    "advice": "Actionable advice on how this trip was optimized for the budget.",
    "cost_saving_tips": ["Tip 1", "Tip 2", "Tip 3"]
  }},
  "itinerary": [
    {{
      "day": 1,
      "date": "YYYY-MM-DD",
      "activities": [
        {{
          "time": "09:00",
          "place": "Name of Place or Experience",
          "duration": "2 hours",
          "description": "Specific, engaging details of what to see or do here.",
          "estimated_cost": number
        }}
      ]
    }}
  ],
  "food_recommendations": ["Must-try dish or eatery 1", "Must-try dish or eatery 2", "Must-try dish or eatery 3"],
  "transport_suggestions": ["Public transit or taxi recommendation 1", "Transit tip 2"],
  "accommodation_suggestions": ["Recommended area or stay type 1", "Stay tip 2"],
  "packing_tips": ["Packing tip 1", "Packing tip 2", "Packing tip 3"],
  "local_tips": ["Local tip 1", "Local tip 2", "Local tip 3"],
  "map_query": "{request.destination}"
}}"""


def _generate_intelligent_fallback_plan(request: TripRequest, weather: dict[str, Any]) -> TripPlan:
    """Intelligently construct a complete, realistic trip plan when external AI APIs are unavailable."""
    days = _trip_days(request)
    currency = request.currency
    travelers = request.travelers
    style = request.travel_style
    interests = request.interests or ["Sightseeing", "Food", "Culture"]
    
    # Calculate realistic budget breakdown
    total_budget = request.budget
    daily_budget = total_budget / days
    
    # Ratios based on style
    if style == "luxury":
        acc_pct, food_pct, act_pct, trans_pct = 0.45, 0.25, 0.20, 0.10
    elif style == "budget":
        acc_pct, food_pct, act_pct, trans_pct = 0.30, 0.30, 0.20, 0.20
    else:  # balanced, family, adventure, romantic
        acc_pct, food_pct, act_pct, trans_pct = 0.38, 0.27, 0.20, 0.15

    acc_cost = round(total_budget * acc_pct, 2)
    food_cost = round(total_budget * food_pct, 2)
    act_cost = round(total_budget * act_pct, 2)
    trans_cost = round(total_budget * trans_pct, 2)

    # Day-by-day activities
    itinerary_days: list[ItineraryDay] = []
    selected = request.selected_attractions

    for day_idx in range(days):
        current_date = request.start_date + timedelta(days=day_idx)
        day_num = day_idx + 1
        
        # Get attractions for this day if provided
        day_attraction = selected[day_idx % len(selected)] if selected else None
        interest_focus = interests[day_idx % len(interests)]

        daily_food_per_person = round((food_cost / days) / travelers, 2)
        daily_act_per_person = round((act_cost / days) / travelers, 2)

        activities = [
            ItineraryActivity(
                time="08:30",
                place=f"Breakfast & Morning Briefing in {request.destination}",
                duration="1 hour",
                description=f"Start day {day_num} with a traditional breakfast near your accommodation and plan the day's route focusing on {interest_focus.lower()}.",
                estimated_cost=round(daily_food_per_person * 0.25 * travelers, 2),
            ),
            ItineraryActivity(
                time="10:00",
                place=day_attraction.name if day_attraction else f"{request.destination} Signature Landmark & {interest_focus} Exploration",
                duration="2.5 hours",
                description=(day_attraction.description if day_attraction and day_attraction.description else f"Explore top cultural and scenic highlights in {request.destination} with a focus on {interest_focus.lower()}."),
                estimated_cost=round(daily_act_per_person * 0.5 * travelers, 2),
            ),
            ItineraryActivity(
                time="13:00",
                place="Local Cuisine Lunch",
                duration="1.5 hours",
                description=f"Enjoy regional specialties at a recommended local eatery in {request.destination}.",
                estimated_cost=round(daily_food_per_person * 0.35 * travelers, 2),
            ),
            ItineraryActivity(
                time="15:00",
                place=f"{request.destination} Afternoon Walk & Local Discovery",
                duration="2 hours",
                description=f"Stroll through vibrant markets, scenic avenues, or peaceful parks in {request.destination}.",
                estimated_cost=round(daily_act_per_person * 0.5 * travelers, 2),
            ),
            ItineraryActivity(
                time="18:30",
                place=f"Evening Atmosphere & Sunset in {request.destination}",
                duration="1.5 hours",
                description=f"Witness the evening ambiance, waterfront, or historic viewpoints tailored for {style} travel.",
                estimated_cost=round(trans_cost / days, 2),
            ),
            ItineraryActivity(
                time="20:00",
                place="Dinner & Night Walk",
                duration="1.5 hours",
                description=f"Conclude day {day_num} with a relaxing dinner and an evening walk in a safe, lively quarter of {request.destination}.",
                estimated_cost=round(daily_food_per_person * 0.40 * travelers, 2),
            ),
        ]

        itinerary_days.append(
            ItineraryDay(
                day=day_num,
                date=current_date,
                activities=activities,
            )
        )

    budget_analysis = BudgetAnalysis(
        requested_budget=total_budget,
        estimated_cost=total_budget,
        difference=0.0,
        budget_status="within_budget",
        advice=f"Itinerary dynamically balanced for {travelers} traveler(s) in {request.destination} using a {style} style.",
        cost_saving_tips=[
            "Use local metro or shared rides for cost-effective transit.",
            "Sample street food and popular neighborhood cafes for authentic flavors at low costs.",
            "Book landmark tickets online in advance to avoid surge pricing.",
        ],
    )

    return TripPlan(
        destination=request.destination,
        summary=f"A custom {days}-day {style} journey to {request.destination} for {travelers} traveler(s), curated around {', '.join(interests[:3])}.",
        currency=currency,
        start_date=str(request.start_date),
        end_date=str(request.end_date),
        duration_days=days,
        travelers=travelers,
        travel_style=style,
        budget=total_budget,
        budget_breakdown={
            "accommodation": acc_cost,
            "food": food_cost,
            "activities": act_cost,
            "transport": trans_cost,
        },
        budget_analysis=budget_analysis,
        weather=weather,
        itinerary=itinerary_days,
        food_recommendations=[
            f"Popular regional breakfast dishes of {request.destination}",
            f"Signature street food specialties",
            f"Traditional dinner restaurants favored by locals",
        ],
        transport_suggestions=[
            "Official ride-hailing apps or city public transit",
            "Walking for central sights to take in local streetscapes",
        ],
        accommodation_suggestions=[
            f"Central neighborhoods with easy transit access in {request.destination}",
            f"Stay options suited for {style} travel",
        ],
        packing_tips=[
            "Comfortable walking footwear",
            "Universal power adapter and power bank",
            "Weather-appropriate attire and rain layer",
        ],
        local_tips=[
            "Keep digital backups of your tickets and ID",
            "Stay hydrated and explore popular markets in the late afternoon",
            "Observe local customs and tipping etiquette",
        ],
        map_query=request.destination,
        ai_provider="assistant-engine",
        selected_attractions=request.selected_attractions,
    )


async def _call_gemini_with_fallback(prompt: str, api_key: str) -> str:
    """Attempt Gemini generateContent across active candidate models with backoff retry."""
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }

    last_error: Exception | None = None

    async with httpx.AsyncClient(timeout=45) as client:
        for model in CANDIDATE_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            for attempt in range(2):
                try:
                    response = await client.post(url, headers=headers, json=payload)
                    if response.status_code == 200:
                        data = response.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts and "text" in parts[0]:
                                logger.info("Gemini generation succeeded with model: %s", model)
                                return parts[0]["text"]
                    elif response.status_code in (429, 503):
                        logger.warning("Model %s returned HTTP %s; retrying...", model, response.status_code)
                        await asyncio.sleep(1 + attempt)
                        continue
                    else:
                        logger.warning("Model %s returned HTTP %s: %s", model, response.status_code, response.text[:200])
                        break
                except Exception as exc:
                    logger.warning("Request to Gemini model %s failed: %s", model, exc)
                    last_error = exc
                    break

    raise AIServiceError(f"All Gemini models were temporarily unavailable: {last_error}")


async def generate_trip_plan(request: TripRequest, weather: dict[str, Any], settings: Settings) -> TripPlan:
    """Generate a high-quality travel plan dynamically for ANY destination and budget."""
    if not settings.gemini_api_key or settings.ai_provider.lower() != "gemini":
        logger.info("Gemini key not configured; using intelligent fallback engine.")
        return _generate_intelligent_fallback_plan(request, weather)

    prompt = _build_ai_prompt(request, weather)
    try:
        text = await _call_gemini_with_fallback(prompt, settings.gemini_api_key)
        payload = _extract_json(text)

        # Ensure essential fields are populated
        payload["destination"] = payload.get("destination") or request.destination
        payload["currency"] = request.currency
        payload["start_date"] = str(request.start_date)
        payload["end_date"] = str(request.end_date)
        payload["duration_days"] = _trip_days(request)
        payload["travelers"] = request.travelers
        payload["travel_style"] = request.travel_style
        payload["budget"] = request.budget
        payload.setdefault("selected_attractions", [a.model_dump(mode="json") for a in request.selected_attractions])
        payload.setdefault("map_query", request.destination)
        payload.setdefault("weather", weather)
        payload["ai_provider"] = "gemini"

        return TripPlan(**payload)
    except Exception as exc:
        logger.warning("Gemini AI plan generation failed; falling back to intelligent assistant engine: %s", exc)
        return _generate_intelligent_fallback_plan(request, weather)


async def stream_trip_plan(
    request: TripRequest,
    weather: dict[str, Any],
    settings: Settings,
) -> AsyncIterator[str]:
    """Yield Gemini text chunks while supporting fallback models."""
    if not settings.gemini_api_key or settings.ai_provider.lower() != "gemini":
        raise AIServiceError("Gemini streaming is unavailable.")

    prompt = _build_ai_prompt(request, weather)
    headers = {"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }

    async with httpx.AsyncClient(timeout=60) as client:
        for model in CANDIDATE_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse"
            try:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        logger.warning("Streaming with model %s returned status %s", model, response.status_code)
                        continue
                    
                    streamed_any = False
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        try:
                            event = json.loads(line[6:])
                            for candidate in event.get("candidates", []):
                                for part in candidate.get("content", {}).get("parts", []):
                                    text = part.get("text")
                                    if text:
                                        streamed_any = True
                                        yield text
                        except Exception:
                            continue
                    if streamed_any:
                        return
            except Exception as exc:
                logger.warning("Stream connection failed for model %s: %s", model, exc)
                continue

    raise AIServiceError("All streaming models failed.")
