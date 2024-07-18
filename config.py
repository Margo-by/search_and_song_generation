from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    OPENAI_API_KEY: str
    SERP_API_KEY: str
    TELEGRAM_TOKEN: str
    ANTHROPIC_API_KEY: str
    SUNO_API_CUSTOM_GENERATE_URL:str

    class Config:
        env_file = '.env'

settings = Settings()