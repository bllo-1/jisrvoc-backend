from pydantic_settings import BaseSettings, SettingsConfigDict
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"

    # Railway compatibility: normalize DATABASE_URL if needed
    @property
    def normalized_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    database_url: str = "postgresql+asyncpg://jisrvoc:jisrvoc@localhost:5432/jisrvoc"
    redis_url: str = "redis://localhost:6379/0"
    use_mock_data: bool = True

    # OIDC/SSO
    oidc_issuer: str = ""
    oidc_audience: str = ""
    oidc_jwks_url: str = ""

    # AI/ML
    embedding_dim: int = 1024

    # Observability
    sentry_dsn: str = ""
    log_level: str = "INFO"

    # CORS
    allowed_origins: str = "*"  # Comma-separated list; "*" for dev only

    # Railway
    port: int = int(os.getenv("PORT", "8000"))


settings = Settings()
