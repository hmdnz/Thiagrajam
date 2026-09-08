from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # =========================================================
    # DATABASE SETTINGS
    # =========================================================
    DATABASE_HOSTNAME: str
    DATABASE_PORT: int
    DATABASE_PASSWORD: str
    DATABASE_NAME: str
    DATABASE_USERNAME: str

    # =========================================================
    # JWT SETTINGS
    # =========================================================
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    # =========================================================
    # EMAIL SETTINGS
    # =========================================================
    ZOHO_EMAIL: str
    ZOHO_APP_PASSWORD: str
    SMTP_SERVER: str
    SMTP_PORT: int

    # =========================================================
    # KUDISMS SETTINGS
    # =========================================================
    KUDISMS_API_KEY: str
    KUDISMS_AUTH_TOKEN: Optional[str] = None
    KUDISMS_SENDER_ID: str = "Wenyfour"
    KUDISMS_BASE_URL: str = "https://my.kudisms.net/api"

    KUDISMS_APP_NAME_CODE: str
    KUDISMS_TEMPLATE_CODE: str

    # =========================================================
    # AWS S3 SETTINGS
    # =========================================================
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str
    AWS_S3_BUCKET: str

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()