from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SelectedAttraction(BaseModel):
    id: str
    name: str
    rating: float | None = None
    category: str | None = None
    description: str | None = None
    distance: str | None = None
    user_reviews_count: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    opening_hours: list[str] = Field(default_factory=list)
    google_maps_url: str | None = None


class TripRequest(BaseModel):
    destination: str = Field(min_length=2, max_length=120)
    start_date: date
    end_date: date
    budget: float = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    travelers: int = Field(default=1, ge=1, le=20)
    interests: list[str] = Field(default_factory=list)
    travel_style: Literal["balanced", "budget", "luxury", "adventure", "family", "romantic"] = "balanced"
    selected_attractions: list[SelectedAttraction] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=800)
    user_id: str | None = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class ItineraryActivity(BaseModel):
    time: str
    place: str
    duration: str
    description: str
    estimated_cost: float


class ItineraryDay(BaseModel):
    day: int
    date: date
    activities: list[ItineraryActivity]


class TripPlan(BaseModel):
    id: str | None = None
    destination: str
    summary: str
    currency: str = "USD"
    budget_breakdown: dict[str, float]
    weather: dict[str, str | float | None]
    itinerary: list[ItineraryDay]
    packing_tips: list[str]
    local_tips: list[str]
    map_query: str
    ai_provider: str
    selected_attractions: list[SelectedAttraction] = Field(default_factory=list)


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    firebase_uid: str | None = Field(default=None, min_length=1, max_length=128)
    profile_photo: str | None = None
    favorite_destinations: list[str] = Field(default_factory=list)


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    email: str | None = Field(default=None, min_length=3, max_length=254)
    profile_photo: str | None = None
    favorite_destinations: list[str] | None = None


class TripUpdate(BaseModel):
    user_id: str | None = None
    destination: str | None = Field(default=None, min_length=2, max_length=120)
    start_date: date | None = None
    end_date: date | None = None
    budget: float | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    travelers: int | None = Field(default=None, ge=1, le=20)
    travel_style: str | None = None
    interests: list[str] | None = None
    selected_attractions: list[SelectedAttraction] | None = None
    weather: dict[str, str | float | None] | None = None
    packing_list: list[str] | None = None


class ItineraryUpdate(BaseModel):
    trip_id: str | None = None
    user_id: str | None = None
    destination: str | None = None
    travel_dates: dict[str, str] | None = None
    selected_attractions: list[SelectedAttraction] | None = None
    weather: dict[str, str | float | None] | None = None
    budget: dict | None = None
    packing_list: list[str] | None = None
    ai_response: dict | None = None


class ExpenseCreate(BaseModel):
    trip_id: str
    user_id: str | None = None
    category: str = Field(min_length=1, max_length=80)
    amount: float = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    description: str | None = Field(default=None, max_length=500)
    expense_date: date | None = None


class ExpenseUpdate(BaseModel):
    category: str | None = Field(default=None, min_length=1, max_length=80)
    amount: float | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    description: str | None = Field(default=None, max_length=500)
    expense_date: date | None = None


class UploadResponse(BaseModel):
    url: str
    public_id: str
    resource_type: str


class PlaceResult(BaseModel):
    id: str
    name: str
    rating: float | None = None
    user_reviews_count: int | None = None
    category: str
    description: str
    distance: str | None = None
    address: str | None = None
    image_url: str | None = None
    photo_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    opening_hours: list[str] = Field(default_factory=list)
    google_maps_url: str | None = None


class PlacesResponse(BaseModel):
    places: list[PlaceResult]
    next_page_token: str | None = None
    source: str
    destination_coordinates: dict[str, float] | None = None
