# Yo' Momma — The Dozens Joke API

> Programmatic access to a curated, community-contributed library of "Yo' Momma" style
> insults and jokes. Fetch random burns, browse by category, filter by NSFW status, and
> contribute your own content — all through a clean REST or GraphQL interface.

---

## Overview

The Dozens is a moderated joke API built around the classic "Yo' Momma" insult format.
Every joke in the library is categorized by **theme** (e.g., *Appearance*, *Intelligence*)
and **category** (e.g., *Fat*, *Stupid*, *Poor*, *Old*) and tagged with an explicit
content (`nsfw`) flag so you decide exactly what your audience sees.

Whether you're building a Discord bot, a mobile party game, a Slack integration, or
just want a comedic data source, The Dozens gives you a structured, filterable,
paginated API to work with.

---

## Base URL

```
https://yo-momma.io/api/
```

---

## Authentication

Public **read** endpoints require no credentials. **Write** operations (create, update,
delete) use Token authentication.

Include your token in every authenticated request:

```
Authorization: Token YOUR_API_TOKEN_HERE
```

Tokens are issued at account registration. See the `/auth/` endpoints for full account
and token management.

---

## Endpoints at a Glance

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/insults/random/` | No | Fetch one random insult |
| `GET` | `/api/insults/category/{category}/` | No | Browse insults by category |
| `GET` | `/api/insults/{reference_id}/` | No | Look up a specific insult |
| `POST` | `/api/insults/new` | **Yes** | Submit a new insult |
| `PUT` | `/api/insults/{reference_id}/` | **Yes** (owner) | Replace an insult |
| `PATCH` | `/api/insults/{reference_id}/` | **Yes** (owner) | Partially update an insult |
| `DELETE` | `/api/insults/{reference_id}/` | **Yes** (owner) | Delete an insult |
| `GET` | `/api/categories/` | No | List all categories and themes |
| `GET` | `/api/health/` | No | Service health check |
| `POST` | `/api/report-joke/` | No | Flag a joke for review |

> A **GraphQL** endpoint is also available at `/graphql/` for flexible querying.

---

## Query Parameters

### `GET /api/insults/random/`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `nsfw` | boolean | No | `true` = explicit only · `false` = clean only · omit = both |
| `category` | string | No | Filter by category key (e.g., `fat`) or full name (e.g., `Fat`) |

### `GET /api/insults/category/{category}/`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `nsfw` | boolean | No | Same as above |
| `page` | integer | No | Page number (default: 1) |
| `page_size` | integer | No | Results per page (default: 20) |

---

## Reference IDs

Every insult carries a stable, human-readable **reference ID** — for example:

```
GIGGLE-00042
CHUCKLE-00015
SNORT-00301
```

Use reference IDs to bookmark specific jokes, build shareable permalinks, or implement
recommendation flows without exposing internal database keys.

---

## Response Format

### Single insult

```json
{
  "reference_id": "GIGGLE-00042",
  "content": "Yo momma is so fat she rolled over 4 quarters and made a dollar.",
  "category": "Fat",
  "nsfw": false,
  "added_by": "Mike R.",
  "added_on": "2 years ago"
}
```

### Paginated list

```json
{
  "count": 312,
  "next": "https://yo-momma.io/api/insults/category/fat/?page=2",
  "previous": null,
  "results": [ ... ]
}
```

### Error response

All errors follow a consistent shape:

```json
{
  "detail": "Yo momma so lost, she tried to route to this page with Apple Maps.",
  "code": "not_found",
  "status_code": 404
}
```

---

## HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `201` | Resource created |
| `204` | Success, no content (update / delete) |
| `400` | Bad request — invalid input |
| `401` | Authentication required |
| `403` | Forbidden — you don't own this resource |
| `404` | Resource not found |
| `429` | Rate limit exceeded |
| `500` | Internal server error |

---

## Code Examples

### Fetch a random clean insult

**cURL**
```bash
curl -X GET "https://yo-momma.io/api/insults/random/?nsfw=false"
```

**Python**
```python
import requests

response = requests.get(
    "https://yo-momma.io/api/insults/random/",
    params={"nsfw": "false"}
)
joke = response.json()
print(joke["content"])
```

**JavaScript (fetch)**
```javascript
const response = await fetch(
  "https://yo-momma.io/api/insults/random/?nsfw=false"
);
const joke = await response.json();
console.log(joke.content);
```

---

### Browse insults by category

**cURL**
```bash
curl -X GET "https://yo-momma.io/api/insults/category/poor/?nsfw=false&page=1"
```

**Python**
```python
import requests

response = requests.get(
    "https://yo-momma.io/api/insults/category/poor/",
    params={"nsfw": "false", "page": 1}
)
data = response.json()
for joke in data["results"]:
    print(joke["reference_id"], "—", joke["content"])
```

**JavaScript (fetch)**
```javascript
const res = await fetch(
  "https://yo-momma.io/api/insults/category/poor/?nsfw=false&page=1"
);
const { results } = await res.json();
results.forEach(j => console.log(j.reference_id, "—", j.content));
```

---

### Look up a specific insult by reference ID

**cURL**
```bash
curl -X GET "https://yo-momma.io/api/insults/GIGGLE-00042/"
```

**Python**
```python
import requests

response = requests.get("https://yo-momma.io/api/insults/GIGGLE-00042/")
print(response.json())
```

---

### Submit a new insult (authenticated)

**cURL**
```bash
curl -X POST "https://yo-momma.io/api/insults/new" \
  -H "Authorization: Token YOUR_API_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Yo momma is so old her birth certificate says expired.",
    "category": "old",
    "nsfw": false
  }'
```

**Python**
```python
import requests

headers = {"Authorization": "Token YOUR_API_TOKEN_HERE"}
payload = {
    "content": "Yo momma is so old her birth certificate says expired.",
    "category": "old",
    "nsfw": False,
}
response = requests.post(
    "https://yo-momma.io/api/insults/new",
    json=payload,
    headers=headers
)
print(response.status_code, response.json())
```

**JavaScript (fetch)**
```javascript
const response = await fetch("https://yo-momma.io/api/insults/new", {
  method: "POST",
  headers: {
    "Authorization": "Token YOUR_API_TOKEN_HERE",
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    content: "Yo momma is so old her birth certificate says expired.",
    category: "old",
    nsfw: false,
  }),
});
const data = await response.json();
console.log(data);
```

---

### Query via GraphQL

```graphql
query {
  insults(category: "fat", nsfw: false, first: 5) {
    totalCount
    items {
      referenceId
      content
      category
    }
  }
}
```

Playground available at: `https://yo-momma.io/graphql/`

---

## Categories & Themes

Jokes are organized into **categories** grouped under broader **themes**. Fetch the
full taxonomy at any time:

```bash
curl -X GET "https://yo-momma.io/api/categories/"
```

Use either the category **key** (e.g., `F`) or the full **name** (e.g., `Fat`) in any
endpoint — both are accepted interchangeably.

---

## Content & Moderation

All submitted insults enter a **moderation queue** before becoming publicly visible.
The moderation pipeline uses the following status flags:

| Status | Meaning |
|--------|---------|
| `Active` | Visible to all users |
| `Pending` | Awaiting moderator review |
| `Rejected` | Declined — does not meet guidelines |
| `Flagged` | Reported by community, under review |
| `Removed` | Soft-deleted, no longer visible |

Community members can flag any joke through the `/api/report-joke/` endpoint without
requiring an account.

---

## Rate Limiting

Rate limits are enforced per API key. When exceeded the API returns `429 Too Many Requests`:

```json
{
  "detail": "Yo momma so slow, she hit the rate limit before she even got started.",
  "code": "throttled",
  "status_code": 429
}
```

Retry after the interval specified in the `Retry-After` response header.

---

## Additional Documentation

| Resource | URL |
|----------|-----|
| Interactive Swagger UI | `https://yo-momma.io/api/swagger/` |
| ReDoc Reference | `https://yo-momma.io/api/redoc/` |
| GraphQL Playground | `https://yo-momma.io/graphql/` |
| OpenAPI Schema (JSON) | `https://yo-momma.io/api/schema/` |
| GitHub Repository | `https://github.com/Terry-BrooksJr/the-dozens-django` |

---

## Support

Found a bug or have a question?
Open an issue on [GitHub](https://github.com/Terry-BrooksJr/the-dozens-django/issues)
or reach out at [terry@brooksjr.com](mailto:terry@brooksjr.com).
