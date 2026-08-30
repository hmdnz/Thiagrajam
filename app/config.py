from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database Settings
    DATABASE_HOSTNAME: str
    DATABASE_PORT: int
    DATABASE_PASSWORD: str
    DATABASE_NAME: str
    DATABASE_USERNAME: str

    # JWT Settings
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    # Email Settings (Zoho SMTP)
    ZOHO_EMAIL: str
    ZOHO_APP_PASSWORD: str
    SMTP_SERVER: str
    SMTP_PORT: int

    # KudiSMS Provider Credentials
    KUDISMS_API_KEY: str
    # KUDISMS_ACCOUNT_SID: str
    KUDISMS_AUTH_TOKEN: Optional[str] = None
    # KUDISMS_AUTH_TOKEN: str
    KUDISMS_SENDER_ID: str = "Wenyfour"
    KUDISMS_BASE_URL: str = "https://my.kudisms.net/api"

    KUDISMS_APP_NAME_CODE: str
    KUDISMS_TEMPLATE_CODE: str

    class Config:
        env_file = ".env",
        extra="ignore"  # Keeps server stable if extra keys exist in .env

settings = Settings()