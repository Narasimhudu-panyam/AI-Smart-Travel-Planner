from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Smart Travel Planner"
    app_env: str = "development"
    # Comma-separated, explicit browser origins permitted to call the API.
    # Set this to the Vercel production URL in Render, for example:
    # FRONTEND_ORIGIN=https://travel-planner.vercel.app
    frontend_origin: str = ""

    ai_provider: str = "gemini"
    gemini_api_key: str | None = None
    openai_api_key: str | None = None

    # Required in deployed environments. Keep this value in backend/.env, never in source.
    mongodb_uri: str | None = None
    mongodb_database: str = "smart_travel_planner"

    openweather_api_key: str | None = None

    cloudinary_cloud_name: str | None = None
    cloudinary_api_key: str | None = None
    cloudinary_api_secret: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origins(self) -> list[str]:
        """Return the configured production origins plus supported local origins."""
        configured_origins = [
            origin.strip().rstrip("/")
            for origin in self.frontend_origin.split(",")
            if origin.strip()
        ]
        local_origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
        return list(dict.fromkeys([*configured_origins, *local_origins]))


@lru_cache
def get_settings() -> Settings:
    return Settings()
