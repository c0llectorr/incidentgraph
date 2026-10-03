"""Environment-derived configuration.

Every setting is read here once; the rest of the app imports constants.
"""

import os

DATABASE_PATH = os.environ.get("ORDERS_DB", "orders.db")
DISCOUNT_SERVICE_URL = os.environ.get("DISCOUNT_SERVICE_URL", "")
RATE_LIMIT_MAX = int(os.environ.get("RATE_LIMIT_MAX", "100"))
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
ENVIRONMENT = os.environ.get("APP_ENV", "development")
