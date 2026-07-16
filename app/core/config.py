from pydantic_settings import BaseSettings, SettingsConifgDict

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    model_config = SettingsConifgDict(
        env_file=".env",
        extra="ignore"
    )

settings = Settings()