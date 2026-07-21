import logging
import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import Settings, get_settings
from app.models import ExpenseCreate, ExpenseUpdate, ItineraryUpdate, PlacesResponse, TripPlan, TripRequest, TripUpdate, UploadResponse, UserCreate, UserFavoritesUpdate, UserUpdate
from app.services.ai import AIServiceError, generate_trip_plan, stream_trip_plan
from app.services.database import DatabaseError, MongoDatabase, TravelRepository
from app.services.places import GoogleMapsServiceError, fetch_place_photo, geocode_destination, search_popular_places
from app.services.uploads import upload_to_cloudinary
from app.services.weather import get_weather

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)
settings = get_settings()
database = MongoDatabase(settings)
repository = TravelRepository(database)


class DiagnosticCORSMiddleware(CORSMiddleware):
    """Temporarily log the exact values Starlette compares for preflights."""

    def preflight_response(self, request_headers):
        logger.info(
            "CORS preflight comparison: origin=%r allow_origins=%r",
            request_headers.get("origin"),
            self.allow_origins,
        )
        return super().preflight_response(request_headers)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.connect()
    yield
    await database.close()


app = FastAPI(title=settings.app_name, version="1.1.0", lifespan=lifespan)


@app.exception_handler(DatabaseError)
async def database_exception_handler(_: Request, exc: DatabaseError) -> JSONResponse:
    logger.error("Database error: %s", exc)
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": "Database service is temporarily unavailable."})


@app.exception_handler(AIServiceError)
async def ai_service_exception_handler(_: Request, exc: AIServiceError) -> JSONResponse:
    logger.warning("AI service error: %s", exc)
    return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content={"detail": str(exc)})


@app.exception_handler(GoogleMapsServiceError)
async def google_maps_exception_handler(_: Request, exc: GoogleMapsServiceError) -> JSONResponse:
    logger.warning("Google Maps service error: %s", exc)
    return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content={"detail": str(exc)})


@app.exception_handler(KeyError)
async def not_found_exception_handler(_: Request, __: KeyError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": "Resource not found."})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name, "database": "connected" if database.db is not None else "disconnected"}


# Existing frontend endpoints (preserved)
@app.post("/api/trips/generate", response_model=TripPlan)
async def create_trip(request: TripRequest, stream: bool = False, current_settings: Settings = Depends(get_settings)) -> TripPlan | StreamingResponse:
    if request.end_date < request.start_date:
        raise HTTPException(status_code=422, detail="End date must be on or after start date.")
    weather = await get_weather(request.destination, current_settings)
    if stream:
        async def event_stream():
            chunks: list[str] = []
            try:
                async for chunk in stream_trip_plan(request, weather, current_settings):
                    chunks.append(chunk)
                    yield f"event: delta\ndata: {json.dumps({'text': chunk})}\n\n"
                payload = json.loads("".join(chunks))
                payload["currency"] = request.currency
                payload.setdefault("selected_attractions", [item.model_dump(mode="json") for item in request.selected_attractions])
                plan = TripPlan(**payload, weather=weather, ai_provider="gemini")
            except Exception as exc:
                logger.warning("Streaming itinerary generation fell back to standard generation: %s", exc)
                plan = await generate_trip_plan(request, weather, current_settings)
            saved_plan = await repository.save_generated_trip(request, plan)
            yield f"event: final\ndata: {saved_plan.model_dump_json()}\n\n"
        return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    plan = await generate_trip_plan(request, weather, current_settings)
    return await repository.save_generated_trip(request, plan)


@app.get("/api/trips")
async def list_trips(user_id: str | None = None):
    try:
        return await repository.list_trips(user_id)
    except Exception as exc:
        logger.exception("GET /api/trips failed for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Unable to load saved trips.") from exc


@app.get("/api/places", response_model=PlacesResponse)
async def list_places(destination: str, page_token: str | None = None, current_settings: Settings = Depends(get_settings)) -> PlacesResponse:
    return await search_popular_places(destination, page_token, current_settings)


@app.get("/api/places/photo")
async def place_photo(name: str, current_settings: Settings = Depends(get_settings)):
    return await fetch_place_photo(name, current_settings)


@app.get("/api/geocode")
async def geocode(destination: str, current_settings: Settings = Depends(get_settings)):
    latitude, longitude = await geocode_destination(destination, current_settings)
    return {"destination": destination, "latitude": latitude, "longitude": longitude}


@app.post("/api/uploads", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...), current_settings: Settings = Depends(get_settings)):
    return await upload_to_cloudinary(file, current_settings)


# CRUD APIs
@app.post("/api/users", status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate): return await repository.create_user(payload)
@app.get("/api/users")
async def list_users(): return await repository.list_users()
@app.get("/api/users/profile")
async def get_user_profile(firebase_uid: str): return await repository.get_user_profile(firebase_uid)
@app.put("/api/users/profile")
async def update_user_profile(firebase_uid: str, payload: UserFavoritesUpdate): return await repository.update_user_favorites(firebase_uid, payload)
@app.get("/api/users/{user_id}")
async def get_user(user_id: str): return await repository.get_user(user_id)
@app.patch("/api/users/{user_id}")
async def update_user(user_id: str, payload: UserUpdate): return await repository.update_user(user_id, payload)
@app.delete("/api/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: str): await repository.delete_user(user_id)

@app.post("/api/trips", status_code=status.HTTP_201_CREATED)
async def create_manual_trip(payload: TripUpdate): return await repository.create_trip(payload)
@app.get("/api/trips/{trip_id}")
async def get_trip(trip_id: str): return await repository.get_trip(trip_id)
@app.patch("/api/trips/{trip_id}")
async def update_trip(trip_id: str, payload: TripUpdate): return await repository.update_trip(trip_id, payload)
@app.delete("/api/trips/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trip(trip_id: str): await repository.delete_trip(trip_id)

@app.post("/api/itineraries", status_code=status.HTTP_201_CREATED)
async def create_itinerary(payload: ItineraryUpdate): return await repository.create_itinerary(payload)
@app.get("/api/itineraries")
async def list_itineraries(trip_id: str | None = None): return await repository.list_itineraries(trip_id)
@app.get("/api/itineraries/{itinerary_id}")
async def get_itinerary(itinerary_id: str): return await repository.get_itinerary(itinerary_id)
@app.patch("/api/itineraries/{itinerary_id}")
async def update_itinerary(itinerary_id: str, payload: ItineraryUpdate): return await repository.update_itinerary(itinerary_id, payload)
@app.delete("/api/itineraries/{itinerary_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_itinerary(itinerary_id: str): await repository.delete_itinerary(itinerary_id)

@app.post("/api/expenses", status_code=status.HTTP_201_CREATED)
async def create_expense(payload: ExpenseCreate): return await repository.create_expense(payload)
@app.get("/api/expenses")
async def list_expenses(trip_id: str | None = None): return await repository.list_expenses(trip_id)
@app.get("/api/expenses/{expense_id}")
async def get_expense(expense_id: str): return await repository.get_expense(expense_id)
@app.patch("/api/expenses/{expense_id}")
async def update_expense(expense_id: str, payload: ExpenseUpdate): return await repository.update_expense(expense_id, payload)
@app.delete("/api/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(expense_id: str): await repository.delete_expense(expense_id)


# Keep CORS outside FastAPI's ServerErrorMiddleware. This ensures an allowed
# browser origin also receives CORS headers when an unexpected 500 occurs.
# The FastAPI instance remains exported as ``app`` for uvicorn app.main:app.
app.middleware_stack = DiagnosticCORSMiddleware(
    app=app.build_middleware_stack(),
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info("CORS allowlist configured for: %s", settings.cors_origins)
logger.info("FastAPI routes loaded: %s", [route.path for route in app.routes])
