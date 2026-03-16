import datetime
import json
import logging
import traceback
import sys
from typing import Any, Dict


class MongoLogHandler(logging.Handler):
    """
    A standard `logging.Handler` that inserts log records into MongoDB.
    Expects the log messages to be formatted as JSON strings by structlog,
    which it then parses into BSON-compatible dicts for insertion.
    """

    def __init__(self, collection_name: str = "application_logs", level: int = logging.NOTSET):
        super().__init__(level)
        self.collection_name = collection_name

    def emit(self, record: logging.LogRecord) -> None:
        try:
            from backend.core.database import get_collection
            collection = get_collection(self.collection_name)

            doc: Dict[str, Any] = {}
            try:
                msg = self.format(record)
                if isinstance(msg, str):
                    try:
                        # Structlog formats as JSON, parse it for MongoDB
                        doc = json.loads(msg)
                    except json.JSONDecodeError:
                        doc = {
                            "message": msg,
                            "logger": record.name,
                            "level": record.levelname,
                            "timestamp": datetime.datetime.fromtimestamp(
                                record.created, datetime.timezone.utc
                            ).isoformat()
                        }
                else:
                    if isinstance(msg, dict):
                        doc = msg
                    else:
                        doc = {"message": str(msg)}
            except Exception:
                doc = {
                    "message": record.getMessage(),
                    "logger": record.name,
                    "level": record.levelname,
                    "timestamp": datetime.datetime.fromtimestamp(
                        record.created, datetime.timezone.utc
                    ).isoformat()
                }

            if "timestamp" not in doc:
                doc["timestamp"] = datetime.datetime.fromtimestamp(
                    record.created, datetime.timezone.utc
                ).isoformat()
                
            # Add basic metric fields for future Observability tools if missing
            if "request_id" not in doc and hasattr(record, "request_id"):
                doc["request_id"] = getattr(record, "request_id")

            # Avoid storing exc_info objects directly in MongoDB (non-serializable),
            # though structlog format_exc_info usually handles this.
            
            # Fire and forget insertion
            collection.insert_one(doc)

        except Exception as e:
            print(f"MongoLogHandler error: {e}", file=sys.stderr)
            self.handleError(record)
