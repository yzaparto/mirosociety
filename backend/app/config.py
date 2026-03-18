from pathlib import Path

from pydantic_settings import BaseSettings

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    database_dir: str = str(_PROJECT_ROOT / "data")
    host: str = "0.0.0.0"
    port: int = 8000
    max_concurrent_llm_calls: int = 10

    model_config = {
        "env_file": [".env", str(_PROJECT_ROOT / ".env")],
        "env_file_encoding": "utf-8",
    }


settings = Settings()
