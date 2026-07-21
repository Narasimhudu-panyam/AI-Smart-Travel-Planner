"""MongoDB Atlas connection and persistence services.

This module owns the application-wide Motor client. Repositories receive the
same database instance so API handlers do not create connections per request.
"""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.errors import PyMongoError

from app.config import Settings
from app.models import ExpenseCreate, ExpenseUpdate, ItineraryUpdate, TripPlan, TripRequest, TripUpdate, UserCreate, UserUpdate

logger = logging.getLogger(__name__)


class DatabaseError(RuntimeError):
    """Raised when Atlas is unavailable or an operation cannot be completed."""


class MongoDatabase:
    """Reusable Atlas connection used for FastAPI's entire lifespan."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client: AsyncIOMotorClient | None = None
        self.db: AsyncIOMotorDatabase | None = None

    async def connect(self) -> None:
        if not self.settings.mongodb_uri:
            raise DatabaseError("MONGODB_URI is not configured. Add it to backend/.env.")
        try:
            self.client = AsyncIOMotorClient(self.settings.mongodb_uri, serverSelectionTimeoutMS=10_000)
            await self.client.admin.command("ping")
            self.db = self.client[self.settings.mongodb_database]
            await self._create_indexes()
            logger.info("Connected to MongoDB Atlas database '%s'.", self.settings.mongodb_database)
        except PyMongoError as exc:
            logger.exception("MongoDB Atlas connection failed.")
            await self.close()
            raise DatabaseError("Could not connect to MongoDB Atlas.") from exc

    async def _create_indexes(self) -> None:
        assert self.db is not None
        await self.db.users.create_index("email", unique=True)
        await self.db.trips.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
        await self.db.itineraries.create_index([("trip_id", ASCENDING), ("created_at", DESCENDING)])
        await self.db.expenses.create_index([("trip_id", ASCENDING), ("created_at", DESCENDING)])

    async def close(self) -> None:
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            logger.info("MongoDB Atlas connection closed.")

    def collection(self, name: str):
        if self.db is None:
            raise DatabaseError("MongoDB Atlas is not connected.")
        return self.db[name]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clean(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None
    document["id"] = str(document.pop("_id"))
    return document


class TravelRepository:
    """CRUD persistence for users, trips, itineraries, and expenses."""

    def __init__(self, database: MongoDatabase):
        self.database = database

    async def _one(self, collection: str, item_id: str) -> dict[str, Any]:
        try:
            item = _clean(await self.database.collection(collection).find_one({"_id": item_id}))
        except PyMongoError as exc:
            logger.exception("Failed reading %s %s", collection, item_id)
            raise DatabaseError("Database read failed.") from exc
        if not item:
            raise KeyError(item_id)
        return item

    async def create_user(self, payload: UserCreate) -> dict[str, Any]:
        now = _now()
        document = {"_id": str(uuid4()), **payload.model_dump(mode="json"), "created_at": now, "updated_at": now}
        document["email"] = document["email"].lower()
        try:
            identity_query: dict[str, Any] = {"email": document["email"]}
            if document.get("firebase_uid"):
                identity_query = {"$or": [{"email": document["email"]}, {"firebase_uid": document["firebase_uid"]}]}
            existing = await self.database.collection("users").find_one(identity_query)
            if existing:
                updates = {key: value for key, value in document.items() if key not in {"_id", "created_at"} and value is not None}
                updated = await self.database.collection("users").find_one_and_update({"_id": existing["_id"]}, {"$set": updates}, return_document=ReturnDocument.AFTER)
                return _clean(updated)  # type: ignore[return-value]
            await self.database.collection("users").insert_one(document)
            return _clean(document)  # type: ignore[return-value]
        except PyMongoError as exc:
            logger.exception("Failed creating user.")
            raise DatabaseError("User could not be created; the email may already exist.") from exc

    async def list_users(self) -> list[dict[str, Any]]:
        try:
            return [_clean(item) async for item in self.database.collection("users").find().sort("created_at", DESCENDING)]
        except PyMongoError as exc:
            raise DatabaseError("Could not list users.") from exc

    async def get_user(self, user_id: str) -> dict[str, Any]: return await self._one("users", user_id)

    async def update_user(self, user_id: str, payload: UserUpdate) -> dict[str, Any]:
        updates = payload.model_dump(exclude_unset=True, mode="json")
        if "email" in updates: updates["email"] = updates["email"].lower()
        updates["updated_at"] = _now()
        try:
            result = await self.database.collection("users").find_one_and_update({"_id": user_id}, {"$set": updates}, return_document=ReturnDocument.AFTER)
        except PyMongoError as exc:
            raise DatabaseError("Could not update user.") from exc
        if not result: raise KeyError(user_id)
        return _clean(result)  # type: ignore[return-value]

    async def delete_user(self, user_id: str) -> None:
        try: result = await self.database.collection("users").delete_one({"_id": user_id})
        except PyMongoError as exc: raise DatabaseError("Could not delete user.") from exc
        if not result.deleted_count: raise KeyError(user_id)

    async def save_generated_trip(self, request: TripRequest, plan: TripPlan) -> TripPlan:
        """Persist the complete AI result in itineraries and its trip summary in trips."""
        trip_id, itinerary_id, now = str(uuid4()), str(uuid4()), _now()
        plan.id = trip_id
        request_data = request.model_dump(mode="json")
        ai_response = plan.model_dump(mode="json")
        trip = {
            "_id": trip_id, "user_id": request.user_id, "destination": request.destination,
            "start_date": request.start_date.isoformat(), "end_date": request.end_date.isoformat(),
            "budget": request.budget, "currency": request.currency, "travelers": request.travelers,
            "travel_style": request.travel_style, "interests": request.interests,
            "selected_attractions": request_data["selected_attractions"], "weather": plan.weather,
            "packing_list": plan.packing_tips, "itinerary_id": itinerary_id, "created_at": now, "updated_at": now,
        }
        itinerary = {
            "_id": itinerary_id, "trip_id": trip_id, "user_id": request.user_id,
            "destination": request.destination, "travel_dates": {"start": request.start_date.isoformat(), "end": request.end_date.isoformat()},
            "selected_attractions": request_data["selected_attractions"], "weather": plan.weather,
            "budget": {"amount": request.budget, "currency": request.currency, "breakdown": plan.budget_breakdown},
            "packing_list": plan.packing_tips, "ai_response": ai_response, "created_at": now, "updated_at": now,
        }
        try:
            await self.database.collection("trips").insert_one(trip)
            await self.database.collection("itineraries").insert_one(itinerary)
            logger.info("Saved generated itinerary %s for trip %s", itinerary_id, trip_id)
            return plan
        except PyMongoError as exc:
            logger.exception("Failed saving generated trip.")
            raise DatabaseError("Generated itinerary could not be saved.") from exc

    async def list_trips(self, user_id: str | None = None) -> list[dict[str, Any]]:
        query = {"user_id": user_id} if user_id else {}
        try:
            output = []
            async for trip in self.database.collection("trips").find(query).sort("created_at", DESCENDING).limit(25):
                trip_id = trip["_id"]
                itinerary = await self.database.collection("itineraries").find_one({"trip_id": trip_id})
                output.append({"id": trip_id, "user_id": trip.get("user_id"), "plan": (itinerary or {}).get("ai_response"), "created_at": trip.get("created_at")})
            return output
        except PyMongoError as exc:
            logger.exception("Failed listing trips.")
            raise DatabaseError("Could not list trips.") from exc

    async def create_trip(self, payload: TripUpdate) -> dict[str, Any]:
        now = _now(); document = {"_id": str(uuid4()), **payload.model_dump(mode="json"), "created_at": now, "updated_at": now}
        try: await self.database.collection("trips").insert_one(document); return _clean(document)  # type: ignore[return-value]
        except PyMongoError as exc: raise DatabaseError("Could not create trip.") from exc
    async def get_trip(self, trip_id: str) -> dict[str, Any]: return await self._one("trips", trip_id)
    async def update_trip(self, trip_id: str, payload: TripUpdate) -> dict[str, Any]: return await self._update("trips", trip_id, payload)
    async def delete_trip(self, trip_id: str) -> None: await self._delete("trips", trip_id)

    async def create_itinerary(self, payload: ItineraryUpdate) -> dict[str, Any]: return await self._create("itineraries", payload)
    async def list_itineraries(self, trip_id: str | None = None) -> list[dict[str, Any]]: return await self._list("itineraries", {"trip_id": trip_id} if trip_id else {})
    async def get_itinerary(self, item_id: str) -> dict[str, Any]: return await self._one("itineraries", item_id)
    async def update_itinerary(self, item_id: str, payload: ItineraryUpdate) -> dict[str, Any]: return await self._update("itineraries", item_id, payload)
    async def delete_itinerary(self, item_id: str) -> None: await self._delete("itineraries", item_id)

    async def create_expense(self, payload: ExpenseCreate) -> dict[str, Any]: return await self._create("expenses", payload)
    async def list_expenses(self, trip_id: str | None = None) -> list[dict[str, Any]]: return await self._list("expenses", {"trip_id": trip_id} if trip_id else {})
    async def get_expense(self, item_id: str) -> dict[str, Any]: return await self._one("expenses", item_id)
    async def update_expense(self, item_id: str, payload: ExpenseUpdate) -> dict[str, Any]: return await self._update("expenses", item_id, payload)
    async def delete_expense(self, item_id: str) -> None: await self._delete("expenses", item_id)

    async def _create(self, collection: str, payload: Any) -> dict[str, Any]:
        now = _now(); document = {"_id": str(uuid4()), **payload.model_dump(exclude_unset=True, mode="json"), "created_at": now, "updated_at": now}
        try: await self.database.collection(collection).insert_one(document); return _clean(document)  # type: ignore[return-value]
        except PyMongoError as exc: raise DatabaseError(f"Could not create {collection} item.") from exc
    async def _list(self, collection: str, query: dict[str, Any]) -> list[dict[str, Any]]:
        try: return [_clean(item) async for item in self.database.collection(collection).find(query).sort("created_at", DESCENDING)]
        except PyMongoError as exc: raise DatabaseError(f"Could not list {collection}.") from exc
    async def _update(self, collection: str, item_id: str, payload: Any) -> dict[str, Any]:
        updates = payload.model_dump(exclude_unset=True, mode="json"); updates["updated_at"] = _now()
        try: item = await self.database.collection(collection).find_one_and_update({"_id": item_id}, {"$set": updates}, return_document=ReturnDocument.AFTER)
        except PyMongoError as exc: raise DatabaseError(f"Could not update {collection} item.") from exc
        if not item: raise KeyError(item_id)
        return _clean(item)  # type: ignore[return-value]
    async def _delete(self, collection: str, item_id: str) -> None:
        try: result = await self.database.collection(collection).delete_one({"_id": item_id})
        except PyMongoError as exc: raise DatabaseError(f"Could not delete {collection} item.") from exc
        if not result.deleted_count: raise KeyError(item_id)
