# Identity Management API

A Django web application for managing multiple contextual identities across academic, professional, and social contexts, with granular access control and external system integration.

**Project Template:** 4 — Identity and Profile Management System
**Stack:** Django 5.2 · PostgreSQL · Tailwind CSS · Python 3.11

---

## Requirements

- Python 3.11+
- PostgreSQL 15+
- gettext (for translations)

---

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/safiyah12/Identity-Management-API.git
cd Identity-Management-API
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
```

### 2. Create the database

```sql
CREATE DATABASE identity_api_db;
CREATE USER identity_user WITH PASSWORD 'parrot231';
GRANT ALL PRIVILEGES ON DATABASE identity_api_db TO identity_user;
```

### 3. Create a `.env` file in the project root

```env
SECRET_KEY=your-django-secret-key
DEBUG=True
DATABASE_NAME=identity_api_db
DATABASE_USER=postgres
DATABASE_PASSWORD=parrot231
DATABASE_HOST=localhost
DATABASE_PORT=5432
GITHUB_CLIENT_ID=Ov23lixFI2VrJTrqEqdz
GITHUB_CLIENT_SECRET=fb2cd3e878557e09e53f1bd3e17288f96f0687c1
```

### 4. Apply migrations

```bash
python manage.py migrate
```

### 5. Create a superuser (required for admin approval workflow)

```bash
python manage.py createsuperuser
```

### 6. Compile translations

```bash
python manage.py compilemessages
```

### 7. Run the server

```bash
python manage.py runserver
```

Visit: `http://127.0.0.1:8000/home/`

---

## Running Tests

```bash
python manage.py test users -v 2
```

Expected output: **85 tests, 0 failures**

---

## Key URLs

| URL | Description |
|---|---|
| `/home/` | Landing page |
| `/register/` | User registration |
| `/user/login/` | User login |
| `/user/dashboard/` | User dashboard |
| `/identities/create/` | Create identity |
| `/search/` | Search identities |
| `/settings/` | User settings |
| `/manage/clients/` | Admin approval panel (staff only) |
| `/client/register/` | External system registration |
| `/client/login/` | External system login |
| `/client/dashboard/` | External system query interface |
| `/auth/github/` | GitHub OAuth login |
