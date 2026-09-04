from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import quote


class Settings(BaseSettings):
    jwt_secret: str = "change_me_to_a_long_random_string"
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_minutes: int = 15
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "fraudguard"
    postgres_user: str = "fraudguard"
    postgres_password: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def database_url(self) -> str:
        user = quote(self.postgres_user, safe="")
        password = quote(self.postgres_password, safe="")
        return (
            f"postgresql+psycopg2://{user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
