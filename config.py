import os

from dotenv import load_dotenv

load_dotenv()


def get_env_var(var_name: str) -> str:
    """Returns the value from the env associated with the var_name"""
    value = os.environ.get(var_name)
    if value is None:
        raise RuntimeError(f"No env variable associated with {var_name}")

    return value


database_url = get_env_var("DATABASE_URL")
