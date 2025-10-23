import tomllib
from typing import Optional
from djs.config.schema import AppConfig

def load_config(config_path: Optional[str]) -> AppConfig:
    """Lädt TOML-Konfiguration oder liefert Defaults."""
    cfg = AppConfig()
    if not config_path:
        return cfg
    with open(config_path, "rb") as f:
        data = tomllib.load(f)
    if "limit" in data:
        try:
            cfg.limit = int(data["limit"])
        except Exception:
            # stillschweigend default behalten; in realen Projekten ggf. validieren
            pass
    return cfg
