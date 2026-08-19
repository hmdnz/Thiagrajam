from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

import sys
import os

# so alembic can find your "app" package
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.database import SQLALCHEMY_DATABASE_URL, Base
from app import models  # noqa — must import so models register on Base.metadata

config = context.config
config.set_main_option("sqlalchemy.url", SQLALCHEMY_DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata