from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/aks_export.db"
    data_dir: str = "./data"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    max_upload_size: int = 100 * 1024 * 1024  # 100MB

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
