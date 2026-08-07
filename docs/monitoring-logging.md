# Monitoring and Logging

Keep your TW Framework applications healthy with proper monitoring and logging.

## Why Monitor?

| Metric | What It Tells You |
|--------|-------------------|
| Error rate | Are things breaking? |
| Response time | Is the site slow? |
| Traffic volume | How many users? |
| Build time | Is CI getting slower? |
| Cache hit rate | Is caching effective? |

## Logging

### Structured Logging

Use JSON-formatted logs for easy parsing:

```python
# [home]/utils/logger.py
import json
import sys
from datetime import datetime

class StructuredLogger:
    def log(self, level, message, **kwargs):
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            **kwargs
        }
        print(json.dumps(entry), file=sys.stderr)

    def info(self, message, **kwargs):
        self.log("info", message, **kwargs)

    def warning(self, message, **kwargs):
        self.log("warning", message, **kwargs)

    def error(self, message, **kwargs):
        self.log("error", message, **kwargs)

logger = StructuredLogger()
```

### Usage in API Routes

```twm
from utils.logger import logger

function get_products(request):
    logger.info("Fetching products", route="/api/products", method="GET")

    try:
        products = db.products.all()
        logger.info("Products fetched", count=len(products))
        return json_response(products)
    except Exception as e:
        logger.error("Failed to fetch products", error=str(e), traceback=traceback.format_exc())
        return json_response({"error": "Internal error"}, status=500)
```

### Request Logging Middleware

```python
# hooks/request_logger.py
import time
from utils.logger import logger

def log_request(request, response):
    duration = time.time() - request.start_time
    logger.info(
        "Request completed",
        method=request.method,
        path=request.path,
        status=response.status_code,
        duration_ms=round(duration * 1000, 2),
        user_agent=request.headers.get("User-Agent", "")
    )
```

## Error Tracking

### Sentry Integration

```bash
pip install sentry-sdk
```

```python
# [home]/sentry.py
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

sentry_sdk.init(
    dsn="https://your-key@sentry.io/project-id",
    integrations=[FlaskIntegration()],
    traces_sample_rate=0.1,
    profiles_sample_rate=0.1,
)
```

### Custom Error Reporting

```twm
function handle_error(request, error):
    # Send to external service
    requests.post("https://errors.example.com/report", json={
        "error": str(error),
        "path": request.path,
        "method": request.method,
        "timestamp": datetime.utcnow().isoformat()
    })

    return json_response({"error": "Something went wrong"}, status=500)
```

## Performance Monitoring

### Timing Decorator

```python
# [home]/utils/timing.py
import time
from functools import wraps
from utils.logger import logger

def timed(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        logger.info(
            f"{func.__name__} executed",
            duration_ms=round(duration * 1000, 2)
        )
        return result
    return wrapper
```

```twm
from utils.timing import timed

@timed
function get_slow_data(request):
    # This will log execution time automatically
    return json_response(expensive_query())
```

### Build Performance

Track build times:

```bash
time tw build --prod
```

Add to CI:

```yaml
- name: Build and measure
  run: |
    START=$(date +%s)
    tw build --prod
    END=$(date +%s)
    echo "Build took $((END - START))s"
```

## Health Checks

### Simple Health Endpoint

```twm
# [home]/api/health/route.twm
function get(request):
    checks = {
        "database": check_database(),
        "cache": check_cache(),
        "disk": check_disk_space()
    }

    all_healthy = all(c["healthy"] for c in checks.values())
    status = 200 if all_healthy else 503

    return json_response({
        "status": "healthy" if all_healthy else "unhealthy",
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat()
    }, status=status)

def check_database():
    try:
        conn = get_db()
        conn.execute("SELECT 1")
        conn.close()
        return {"healthy": True}
    except Exception as e:
        return {"healthy": False, "error": str(e)}

def check_cache():
    try:
        cache_set("health_check", "ok", ttl=10)
        return {"healthy": True}
    except Exception as e:
        return {"healthy": False, "error": str(e)}

def check_disk_space():
    import shutil
    usage = shutil.disk_usage("/")
    free_percent = usage.free / usage.total * 100
    return {
        "healthy": free_percent > 10,
        "free_percent": round(free_percent, 2)
    }
```

## Alerting

### Slack Notifications

```python
# [home]/utils/alerts.py
import requests
import os

SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK_URL")

def alert_slack(message, level="warning"):
    if not SLACK_WEBHOOK:
        return

    color = {"info": "#36a64f", "warning": "#ff9900", "error": "#ff0000"}

    requests.post(SLACK_WEBHOOK, json={
        "attachments": [{
            "color": color.get(level, "#ff9900"),
            "text": message,
            "footer": "TW Framework",
            "ts": int(time.time())
        }]
    })
```

```twm
function critical_endpoint(request):
    try:
        result = process_critical_task()
        return json_response(result)
    except Exception as e:
        alert_slack(f"Critical error: {e}", level="error")
        return json_response({"error": "Critical failure"}, status=500)
```

## Log Aggregation

### File-Based Logging

```python
# [home]/utils/file_logger.py
import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# App logs
app_handler = RotatingFileHandler(
    f"{LOG_DIR}/app.log", maxBytes=10*1024*1024, backupCount=5
)
app_handler.setFormatter(formatter)

# Error logs
error_handler = RotatingFileHandler(
    f"{LOG_DIR}/error.log", maxBytes=10*1024*1024, backupCount=5
)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(formatter)

logger = logging.getLogger("tw_app")
logger.addHandler(app_handler)
logger.addHandler(error_handler)
logger.setLevel(logging.INFO)
```

## Best Practices

1. **Never log sensitive data**: Passwords, tokens, credit cards.
2. **Use correlation IDs**: Track requests across services.
3. **Log at appropriate levels**: DEBUG for dev, INFO for normal, ERROR for problems.
4. **Rotate logs**: Prevent disk space issues.
5. **Monitor log volume**: Sudden spikes indicate problems.
6. **Set up alerts**: Know about issues before users do.
