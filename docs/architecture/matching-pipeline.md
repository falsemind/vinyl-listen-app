---
name: matching-pipeline
description: This document explains Discogs Matching Pipeline Specification.
---

# Vinyl Listening App — Discogs Matching Pipeline Specification (MVP)

## Purpose

Define the backend pipeline responsible for identifying a vinyl record from a user-provided photo and returning **candidate Discogs releases**.

The pipeline must:

- support multiple identification signals
    
- respect Discogs API rate limits
    
- minimize external API calls via caching
    
- provide reliable candidate ranking
    
- degrade gracefully to manual search
    

The system is designed for **MVP reliability and simplicity**, with clear extension points for more advanced computer vision later.

---

# Pipeline Objective

Transform a captured image into Discogs candidate releases.

```
photo → extract identifiers → Discogs search → ranked candidates → user confirmation
```

The backend performs all processing.  
The Android app only handles **capture and UI interaction**.

---

# Inputs

Primary input:

```
image file
```

Optional inputs (future support):

```
manual barcode
manual catalog number
artist/title search query
```

Image is uploaded through the backend endpoint:

```
POST /identify
```

Request:

```
multipart/form-data
image
```

---

# High-Level Pipeline

```
graph TD
    A[Image Upload] --> B(Image Preprocessing);
    B --> C{Signal Detection & Identifier Extraction};
    C --> D{Local Database Lookup (DB)};
    D -- Match Found --> E[Return Internal/Cached Metadata];
    D -- No Match Found --> F(Discogs Search API Call);
    F --> G[Candidate Ranking & Filtering];
    G --> H[Return Candidate Releases to Client];

```
---

# Stage 1 — Image Upload

Android uploads the captured photo.

Endpoint:

```
POST /identify
```

Backend responsibilities:

```
validate file type
limit file size
store temporarily
trigger processing pipeline
```

Accepted formats:

```
JPEG
PNG
```

Maximum size recommended:

```
10 MB
```

---

# Stage 2 — Image Preprocessing

Images are normalized before analysis.

Operations:

```
resize
grayscale conversion
contrast enhancement
noise reduction
rotation normalization
```

Purpose:

```
improve barcode detection
improve OCR accuracy
reduce processing time
```

Recommended libraries:

```
OpenCV
Pillow
```

---

# Stage 3 — Signal Detection

The pipeline attempts to extract identifiers in priority order.

```
1 barcode
2 OCR text
```

Signals may be processed in parallel.

---

# Barcode Detection

Attempt to detect barcode on the sleeve.

Libraries:

```
pyzbar
zxing
```

If barcode detected:

```
barcode → Discogs search
```

Example identifier:

```
724384960826
```

Discogs query:

```
/database/search?barcode=724384960826
```

Expected accuracy:

```
very high
```

If results returned:

```
skip OCR stage
```

---

# OCR Text Extraction

If barcode detection fails, attempt OCR.

OCR extracts text that may contain:

```
catalog numbers
artist names
album titles
matrix/runout strings
```

Recommended libraries:

```
Tesseract OCR
PaddleOCR-VL
```

Typical extracted text example:

```
BC 01 A1
Basic Channel
Phylyps Trak
```

---

# Identifier Extraction

Parsed OCR text is analyzed to detect meaningful identifiers.

Extraction targets:

```
catalog number
artist name
title
runout string
```

Basic pattern detection:

```
catalog numbers
alphanumeric strings
```

Example patterns:

```
BC 01
ST-A-732784
KMS-048
```

Parsed identifiers are then used for Discogs search queries.

---

# Discogs Search Strategy

**Prioritization Logic (Crucial):** Before constructing and executing any external Discogs API query, the system must perform a database lookup using the extracted identifiers (barcode, catalog number). If an entry is found in the releases table or associated cache tables, that data is used immediately to return candidates/details, bypassing the Discogs API entirely.

The backend constructs search queries based on available identifiers.

Search priority:

```
barcode
catalog number
artist + title
free text
```

Example queries:

```
/database/search?barcode=xxxx
/database/search?catno=BC+01
/database/search?artist=Basic+Channel&release_title=Phylyps+Trak
/database/search?q=BC+01
```

Discogs returns a list of candidate releases.

---

# Rate Limiting Strategy

Discogs API limit:

```
~60 requests per minute
```

The backend must enforce:

```
request throttling
response caching
retry logic
```

Recommended strategy:

```
token bucket limiter
```

Example configuration:

```
max_discogs_requests_per_minute = 50
```

Remaining capacity provides safety margin.

---

# Caching Strategy

To reduce API calls, metadata is cached locally.

Table:

```
discogs_release_cache
```

Cache stores:

```
discogs_release_id
raw_discogs_json
cached_at
last_accessed_at
```

Cache usage rules:

```
if release metadata exists → return cached
if not → fetch from Discogs
```

Cache expiration policy:

```
no expiration required for MVP
metadata rarely changes
```

---

# Candidate Ranking

Discogs search results are ranked before returning to the client.

Ranking signals:

```
exact barcode match
catalog number match
artist similarity
title similarity
label match
year proximity
```

Scoring model example:

```
barcode match = +100
catalog match = +80
artist/title similarity = +40
label match = +10
year proximity = +5
```

Top results returned to Android.

Limit recommended:

```
5 candidates
```

---

# Response Format

API returns candidate releases.

Example response:

```json
{
  "candidates": [
    {
      "discogs_release_id": 123456,
      "artist": "Basic Channel",
      "title": "Phylyps Trak",
      "year": 1993,
      "label": "Basic Channel",
      "cover_image_url": "https://discogs.com/image.jpg"
    }
  ]
}
```

Android displays candidates for confirmation.

---

# Release Confirmation Flow

After the user selects a release:

```
discogs_release_id
      ↓
POST /releases/import
      ↓
backend imports metadata
      ↓
release_id returned
```

Metadata imported:

```
artist
title
year
label
catalog number
barcode
genres
styles
cover image
```

Stored in:

```
releases table
```

---

# Failure Handling

Possible failures:

```
image unreadable
barcode detection failure
OCR failure
Discogs API failure
no candidate matches
```

Fallback behavior:

```
return empty candidate list
Android navigates to Manual Search
```

Manual search ensures the user can **always log a record**.

---

# Security Considerations

Protect the pipeline from abuse.

Required safeguards:

```
file size limits
rate limiting per client
temporary image storage cleanup
input validation
```

Temporary images should be deleted after processing.

---

# Performance Targets

Typical processing time:

```
barcode detection → < 1 second
OCR pipeline → 2–4 seconds
```

Total acceptable latency:

```
< 5 seconds
```

This is acceptable for user experience.

---

# Future Improvements (Post-MVP)

Possible enhancements:

```
vinyl label artwork recognition
deep learning image matching
runout etching specialized OCR
machine learning candidate ranking
collection-aware ranking
```

Example advanced features:

```
detect label logos
detect record sleeve artwork
visual similarity search
```

These can significantly improve identification accuracy.

---

# Summary

The MVP Discogs Matching Pipeline:

```
photo
   ↓
barcode detection
   ↓
OCR fallback
   ↓
Discogs search
   ↓
candidate ranking
   ↓
user confirmation
```

This architecture provides:

```
high identification accuracy
manageable engineering complexity
Discogs API compatibility
future extensibility
```

while remaining realistic for an MVP implementation.