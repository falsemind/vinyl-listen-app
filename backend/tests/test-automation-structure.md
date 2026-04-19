
# High-Level Pytest Test Automation Structure


```
backend/
│
├── app/
│
├── tests/
│
│   ├── api/
│   │   ├── test_health.py
│   │   ├── test_identify_api.py
│   │   ├── test_releases_api.py
│   │   ├── test_sessions_api.py
│   │   └── test_analytics_api.py
│   │
│   ├── services/
│   │   ├── test_discogs_service.py
│   │   ├── test_release_service.py
│   │   └── test_session_service.py
│   │
│   ├── pipelines/
│   │   ├── test_barcode_detector.py
│   │   ├── test_ocr_extractor.py
│   │   └── test_candidate_ranker.py
│   │
│   ├── fixtures/
│   │   ├── api_client.py
│   │   ├── db.py
│   │   ├── test_data.py
│   │   └── discogs_mock.py
│   │
│   ├── data/
│   │   ├── images/
│   │   │   ├── barcode_sample.jpg
│   │   │   ├── sleeve_sample.jpg
│   │   │   └── label_sample.jpg
│   │   │
│   │   └── discogs_responses/
│   │       ├── search_result.json
│   │       └── release_metadata.json
│   │
│   ├── utils/
│   │   ├── image_helpers.py
│   │   └── response_validators.py
│   │
│   ├── conftest.py
│   └── pytest.ini
```

---
# Testing Layers:

## 1️⃣ API Tests (Primary Layer)

Location:

```
tests/api/
```

These test **endpoints exactly how the Android client will call them**.

Example coverage:

| Endpoint         | Test File             |
| ---------------- | --------------------- |
| /health          | `test_health.py`        |
| /identify        | `test_identify_api.py`  |
| /releases/import | `test_releases_api.py`  |
| /sessions        | `test_sessions_api.py`  |
| /analytics       | `test_analytics_api.py` |

---
# 2️⃣ Service Tests

Location:

```
tests/services/
```

These test **business logic without HTTP layer**.

Example targets:

```
DiscogsService  
ReleaseService  
SessionService  
AnalyticsService
```

---
# 3️⃣ Pipeline Tests

Location:

```
tests/pipelines/
```

Specifically for **record identification pipeline**.

Components tested:

```
barcode detection  
OCR extraction  
identifier parsing  
candidate ranking
```

---
# 4️⃣ Fixtures

Location:

```
tests/fixtures/
```

Reusable pytest fixtures live here.

**Examples:**

### API Client Fixture

```
api_client.py
```

Creates a test FastAPI client.

---
### Database Fixture

```
db.py
```

Provides a test database session.

### Discogs Mock

```
discogs_mock.py
```

Mocks Discogs API responses.

---
# 5️⃣ Test Data

Location:

```
tests/data/
```

Contains stable artifacts used in tests.

Examples:

### Images

```
barcode_sample.jpg  
vinyl_label.jpg  
album_cover.jpg
```

### Discogs responses

```
search_result.json  
release_metadata.json
```

Using recorded responses avoids hitting the real API.

---
# 6️⃣ Utility Helpers

Location:

```
tests/utils/
```

Test helper utilities.

Examples:

```
image preprocessing  
response schema validation  
test object builders
```

---
# 7️⃣ `conftest.py`

Location:

```
tests/conftest.py
```

Central pytest configuration.

Common responsibilities:

- load environment variables
    
- register fixtures
    
- configure test DB
    
- override FastAPI dependencies
    

Example fixtures:

```
api_client  
db_session  
test_settings
```

---

# 8️⃣ `pytest.ini`

Location:

```
tests/pytest.ini
```

Example configuration:

```
[pytest]  
testpaths = tests  
python_files = test_*.py  
addopts = -v
```

Optional:

```
asyncio_mode = auto
```
