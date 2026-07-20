from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Job Searching API"
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    MAX_FOLLOWUPS: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

print("config laoded")

settings = Settings()