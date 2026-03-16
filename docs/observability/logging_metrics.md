# Observability & Logging Architecture

This document describes the logging and metric collection strategy for the application, specifically focusing on the integration of structured logging into MongoDB and future observability goals.

## Current Architecture

The application uses **structured JSON logging** provided by `structlog`. System and application logs are processed via a centralized `ops.logging` configuration. 

### MongoDB Integration

To facilitate persistent storage and future querying of logs, an asynchronous `MongoLogHandler` has been introduced. This handler seamlessly intercepts structured application logs and inserts them as BSON documents into the `application_logs` MongoDB collection.

**Key Design Decisions:**
- **Non-blocking (Asynchronous) Execution**: Given that each log insertion requires a database operation, we route logs via Python's native `logging.handlers.QueueHandler` to a background `QueueListener`. This ensures the application (e.g., FastAPI HTTP requests) is never blocked by logging IO.
- **Native JSON Serialization**: The JSON dict records created by `structlog` are parsed and stored natively within MongoDB, which perfectly aligns with BSON formatting, allowing powerful query capabilities on metric fields (e.g., `event`, `latency_ms`, `level`, `request_id`).

### Sample Log Document

A standard log ingested into MongoDB will look similar to:

```json
{
  "_id": { "$oid": "649a1f2b48d2..." },
  "event": "startup_test",
  "level": "info",
  "logger": "backend.main",
  "timestamp": "2026-03-16T22:25:08.779028Z",
  "request_id": "-",
  "test_true": true
}
```

## Future Roadmap (Metrics & Dashboards)

Currently, metrics and logs are solely stored within MongoDB. Long-term, these logs will act as rich foundational metrics intended to be ingested or visualized through modern observability stacks:

1. **Grafana Dashboards**: We plan to connect Grafana directly to the MongoDB `application_logs` collection (or index it via an intermediate datasource like Elasticsearch or Loki) to visualize application health, LLM response latency, token usage, and user growth.
2. **Prometheus Exporters**: Specialized numerical metrics (e.g., request load, queue depth, cache hits) currently recorded in `application_logs` could be grouped, counted, and eventually scraped by Prometheus to trigger automated alerts.

By establishing standard structured logs early, all relevant metadata and operational context are already being captured reliably for future migration.
