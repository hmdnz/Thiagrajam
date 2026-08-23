from pydantic_settings import BaseSettings
# from pydantic import BaseSettings

# class Settings(BaseSettings):

class Settings(BaseSettings):
    DATABASE_HOSTNAME: str
    DATABASE_PORT: int
    DATABASE_PASSWORD: str
    DATABASE_NAME: str
    DATABASE_USERNAME: str


    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    

    ZOHO_EMAIL: str
    ZOHO_APP_PASSWORD: str
    SMTP_SERVER: str
    SMTP_PORT: int

# Termii Configuration
    TERMII_API_KEY: str
    TERMII_SENDER_ID: str = "Termii"          # falls back to shared ID if you haven't registered one
    TERMII_BASE_URL: str = "https://api.ng.termii.com/api"





    class Config:
        env_file = ".env"

settings = Settings()


