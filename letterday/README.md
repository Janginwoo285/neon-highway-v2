## One-click Render Blueprint

[Deploy Letterday API + PostgreSQL to Render](https://render.com/deploy?repo=https://github.com/Janginwoo285/neon-highway-v2)

The repository-root `render.yaml` provisions the API and PostgreSQL. You must sign in to Render and approve the resources yourself. The Blueprint declares free plans, subject to Render availability and limits; **free PostgreSQL databases expire after 30 days**. The web app is already served by GitHub Pages, but until Render deployment completes and you enter its actual HTTPS API URL in Settings, cross-user sharing remains unavailable.

# Letterday — 나에게 보내는 오늘의 편지

A warm-tone letter-style diary app and portfolio project, combining **HTML, JavaScript, Spring Boot, and Flutter**.

## What is implemented

| Feature | Web (HTML/JS) | Flutter |
| --- | --- | --- |
| Warm-tone letter editor | Yes | Yes |
| Private journal entries | Yes, local mode or API | API |
| Account registration/login | API-connected | API-connected |
| Public community letters | API-connected | API-connected |
| Mood selection | Yes | Yes |
| Photos | Web only, data URL | Not yet |
| Drawing pad | Web only | Not yet |
| Calendar | Web only | Not yet |
| Local JSON backup/restore | Web-only, local mode | Not yet |
| Notification reminder | Web only; explicit permission; tab must be open | Not yet |

The public feed **does not work across devices without a deployed Spring backend and persistent PostgreSQL database**. Public entries are always explicit opt-in. The web version defaults to local-only mode and private entries. The browser reminder is OFF by default and works only while the page is open. No background push is implemented.

## Repository layout

- `index.html` — standalone, responsive web experience (no build required)
- `server/` — Java 17 + Spring Boot REST API, JDBC, PostgreSQL/H2 configuration
- `flutter/` — Flutter mobile project starter, using same API
- `docs/PORTFOLIO.md` — project brief, user flow, acceptance tests, roadmap

## Web deployment

GitHub Pages serves **static HTML/JavaScript only**. This repository also has a car game at its root. The diary lives in the `letterday/` folder, so its URL after Pages is successfully enabled is:

https://janginwoo285.github.io/neon-highway-v2/letterday/

This address has not yet been verified as publicly accessible. Check the repository Settings > Pages and Actions > pages build and deployment. If the page returns 404, the GitHub Pages build is not successfully serving the repository yet.

## Spring API local run

Java 17 and Maven are required:

```sh
cd server
mvn spring-boot:run
```

Default port 8080; health: `http://localhost:8080/api/health`.

Local development defaults to an **in-memory H2 database**, and data disappears on restart. For persistent deployment, provide PostgreSQL JDBC values:

```sh
SPRING_DATASOURCE_URL=jdbc:postgresql://HOST:5432/DATABASE
SPRING_DATASOURCE_USERNAME=YOUR_USERNAME
SPRING_DATASOURCE_PASSWORD=YOUR_PASSWORD
APP_CORS_ORIGINS=https://janginwoo285.github.io
```

Run the Dockerfile on a Java-compatible hosting provider (Render, Railway, Fly.io or equivalent) and provision a PostgreSQL database separately. Use HTTPS and configure environment variables in your host dashboard; **never commit credentials**. Then open the web app's Settings and enter your public API URL. Account registration and sharing will require that server to be reachable.

### API routes
- `POST /api/auth/register` — `{email,password}`
- `POST /api/auth/login` — returns bearer token
- `POST /api/auth/logout` — revoke session
- `GET /api/entries` — private list for logged-in owner
- `POST /api/entries` — create
- `PUT /api/entries/{id}` — edit own entry
- `DELETE /api/entries/{id}` — delete own entry
- `GET /api/feed` — 50 latest explicitly public entries
- `GET /api/health` — service health

Login sessions are persisted in SQL; access tokens are SHA-256 hashed in database and expire in seven days. Passwords are BCrypt hashed. The web token is held in memory only, so refreshing requires login again.

## Flutter

```sh
cd flutter
flutter create . --platforms=android,ios
flutter pub get
flutter run
```

Set the Spring API HTTPS URL in the app's Settings screen. The Flutter starter supports login, writing, reading and deleting text letters, emotional state, and sharing toggle, but does not yet support the web app's image/drawing/notification features.

## Privacy and production limitations

**Not production-ready for general public signup yet.** Before inviting users:
1. Deploy with persistent database and HTTPS and test account isolation.
2. Add abuse reporting, moderation, spam/rate limits, email verification, account deletion and retention/privacy policy.
3. Add production image object storage; current base64 images occupy database space.
4. Add scheduled push using explicit OS permission, authenticated device tokens and a scheduler; currently no background notifications.
5. Run end-to-end web, mobile and API tests. These tests have not been claimed as completed.

No real user metrics or fictional growth statistics should be added to portfolio material.
