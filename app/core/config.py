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

    # Agent-based enrichment (Phase 5)
    agent_enrichment_enabled: bool = False  # Enable agent-based classification
    agent_rollout_percentage: int = 0  # 0-100: Percentage of feedback to enrich with agents

    # Vertex AI (Phase 4)
    gcp_project_id: str = ""
    gcp_region: str = "me-central1"  # Dammam, Saudi Arabia

    # Connectors (Phase 1)
    hubspot_api_key: str = ""
    zendesk_email: str = ""
    zendesk_api_token: str = ""
    zendesk_subdomain: str = ""

    # Chargebee (Phase 5 - Customer Enrichment)
    chargebee_api_key: str = ""
    chargebee_site: str = "jisr"  # Chargebee site name (e.g., jisr.chargebee.com)

    # Slack (Phase 2 - Alerts)
    slack_bot_token: str = ""
    slack_channel_urgent: str = ""  # Channel for urgent alerts

    # Observability
    sentry_dsn: str = ""
    log_level: str = "INFO"

    # CORS
    allowed_origins: str = "*"  # Comma-separated list; "*" for dev only

    # Railway
    port: int = int(os.getenv("PORT", "8000"))


settings = Settings()
