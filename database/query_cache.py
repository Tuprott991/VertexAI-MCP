import logging
import json
from datetime import datetime
from typing import List, Dict, Optional

from database.connect_db import (
    get_db_connection,
    get_db_transaction,
    close_connection_pool,
    DatabaseError
)

logger = logging.getLogger(__name__)

# This file contains functions to mange query cache data in the database
# Each cache entry stores the query, its result, and metadata like timestamp
# 