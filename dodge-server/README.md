# Dodge Final – Java Spring Boot API

Endpoints:
- GET /api/game/health
- POST /api/game/auth/register {username,password,nickname}
- POST /api/game/auth/login {username,password}
- GET /api/game/me (Authorization: Bearer token)
- POST /api/game/auth/logout
- GET /api/game/leaderboard
- POST /api/game/scores {score,survived} (Authorization)

The server stores BCrypt password hashes and SHA-256 hashes of session tokens. Tokens expire after seven days. Each user has one best score. Free users can play without logging in.

## Local run

Java 17 + Maven:

```bash
mvn spring-boot:run
```

By default the server uses **temporary in-memory H2**. Production requires PostgreSQL:
```
SPRING_DATASOURCE_URL=jdbc:postgresql://HOST:5432/DB
SPRING_DATASOURCE_USERNAME=...
SPRING_DATASOURCE_PASSWORD=...
APP_CORS_ORIGINS=https://janginwoo285.github.io
```
Set Render's Docker Root Directory to `dodge-server`. Expose `PORT` automatically.

## IMPORTANT – prototype limitations

Leaderboard scores are submitted by the browser and **cannot be trusted as anti-cheat evidence**. For public competition or prizes, implement server-side run attestation and rate limits before launch. Add account recovery, account deletion, privacy policy and operational monitoring for production. Do not configure an ephemeral H2 database for persistent user accounts. Deploy server and provide its HTTPS URL in web game's Account screen.
