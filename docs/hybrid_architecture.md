# Hybrid Django Backend Architecture

## Final structure

```text
wpe-backend/
├── .env
├── .env.example
├── core_system/
│   ├── manage.py
│   ├── apps/
│   │   ├── auth/
│   │   ├── items/
│   │   └── presales/
│   ├── common/
│   │   ├── authentication.py
│   │   ├── grn_client.py
│   │   └── middleware.py
│   └── core_system/
│       ├── asgi.py
│       ├── settings.py
│       ├── urls.py
│       └── wsgi.py
├── grn_service/
│   ├── manage.py
│   ├── grn_app/
│   └── grn_service/
│       ├── asgi.py
│       ├── settings.py
│       ├── urls.py
│       └── wsgi.py
├── docs/
│   └── hybrid_architecture.md
├── main.py
├── pyproject.toml
└── uv.lock
```

`LOGIN/` and `MASTERS/` were removed as active Django projects. The new canonical entry points are `core_system/manage.py` and `grn_service/manage.py`.

## Core system

- Main monolith: `core_system`
- Apps moved into:
  - `LOGIN/Auth` -> `core_system/apps/auth`
  - `MASTERS/Items` -> `core_system/apps/items`
  - `MASTERS/Presales` -> `core_system/apps/presales`
- Central settings and routing:
  - `core_system/core_system/settings.py`
  - `core_system/core_system/urls.py`

### JWT setup

- `REST_FRAMEWORK` now uses:
  - `rest_framework_simplejwt.authentication.JWTAuthentication`
  - `common.authentication.APIKeyAuthentication`
- Global permission default is `IsAuthenticated`
- Token endpoints:
  - `POST /api/token/`
  - `POST /api/token/refresh/`
  - `POST /api/token/verify/`
- Backward-compatible login alias:
  - `POST /api/auth/login/`

### Middleware

- Shared middleware lives in `core_system/common/middleware.py`
- Shared auth helpers live in `core_system/common/authentication.py`
- Behavior:
  - disables CSRF checks for `/api/`
  - rejects unauthenticated `/api/` requests with JSON `401`
  - accepts JWT first
  - falls back to `X-API-Key` or `Authorization: Api-Key <key>`

### Protected API view example

Current protected user endpoint:

- `GET /api/auth/me/`
- implementation: `core_system/apps/auth/views.py`

Example response:

```json
{
  "id": 1,
  "username": "admin",
  "email": "admin@example.com",
  "first_name": "",
  "last_name": "",
  "is_staff": true
}
```

### Example API requests

Obtain JWT:

```bash
curl -X POST http://127.0.0.1:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

Use JWT:

```bash
curl http://127.0.0.1:8000/api/auth/me/ \
  -H "Authorization: Bearer <access-token>"
```

Use API key fallback:

```bash
curl http://127.0.0.1:8000/api/items/ \
  -H "X-API-Key: <shared-api-key>"
```

## GRN service

- `Purchases_Inwards` moved to `grn_service/grn_app`
- Settings and routes live in:
  - `grn_service/grn_service/settings.py`
  - `grn_service/grn_service/urls.py`

### Important GRN note

GRN still comes from another website. That inbound integration path was kept separate from the core monolith and the receiver endpoint remains:

- `POST /api/grn/grncreate/`

This path is exempt by default in `grn_service/grn_service/settings.py` so the existing sender does not have to be rerouted through `core_system`.

## Core -> GRN API call

Reusable client:

- `core_system/common/grn_client.py`

Example:

```python
from common.grn_client import GRNServiceClient

client = GRNServiceClient()
grn_payload = client.fetch_grn(grn_no="GRN-00045")
qcr_payload = client.move_grn_to_qcr(grn_id=45)
```

Required env:

```env
GRN_SERVICE_BASE_URL=http://127.0.0.1:8001
GRN_SERVICE_API_KEY=replace-with-grn-api-key
```

## Run both services

Core monolith:

```bash
.venv/bin/python core_system/manage.py migrate
.venv/bin/python core_system/manage.py createsuperuser
.venv/bin/python core_system/manage.py runserver 127.0.0.1:8000
```

GRN service:

```bash
.venv/bin/python grn_service/manage.py migrate
.venv/bin/python grn_service/manage.py runserver 127.0.0.1:8001
```

## Validation

Both services pass:

```bash
.venv/bin/python core_system/manage.py check
.venv/bin/python grn_service/manage.py check
.venv/bin/python core_system/manage.py makemigrations --check --dry-run
.venv/bin/python grn_service/manage.py makemigrations --check --dry-run
```
