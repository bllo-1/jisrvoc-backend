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
    llm_provider: str = "openai"  # openai or vertex_ai
    openai_api_key: str = ""
    embedding_dim: int = 1536  # OpenAI text-embedding-3-small

    # Vertex AI (Phase 4)
    gcp_project_id: str = ""
    gcp_region: str = "me-central1"  # Dammam, Saudi Arabia

    # Observability
    sentry_dsn: str = ""
    log_level: str = "INFO"

    # CORS
    allowed_origins: str = "*"  # Comma-separated list; "*" for dev only

    # Railway
    port: int = int(os.getenv("PORT", "8000"))


settings = Settings()
