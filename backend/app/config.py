from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Smart Travel Planner"
    app_env: str = "development"
    frontend_origin: str = "http://127.0.0.1:5173"

    ai_provider: str = "gemini"
    gemini_api_key: str | None = None
    openai_api_key: str | None = None

    # Required in deployed environments. Keep this value in backend/.env, never in source.
    mongodb_uri: str | None = None
    mongodb_database: str = "smart_travel_planner"

    openweather_api_key: str | None = None

    # One Maps Platform key is used server-side for Places and Geocoding APIs.
    google_maps_api_key: str | None = None

    cloudinary_cloud_name: str | None = None
    cloudinary_api_key: str | None = None
    cloudinary_api_secret: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
