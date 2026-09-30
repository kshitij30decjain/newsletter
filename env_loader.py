from pathlib import Path
import os

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent


def load_project_env():
    load_dotenv(PROJECT_ROOT / ".env", override=False)


def env(name):
    value = os.getenv(name)
    if value is None or str(value).strip() == "":
        raise ValueError(
            f"{name} is not set in the environment or .env file."
        )
    return value.strip()


def env_optional(name, default=""):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().strip("\"'")


def env_int(name):
    return int(env(name))


def env_float(name):
    return float(env(name))


def env_bool(name):
    return env(name).lower() in {"1", "true", "yes", "on"}


load_project_env()
