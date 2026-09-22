# CLAUDE.md — api/ (Spring Boot)

Spring Boot 4.1 on Java 25 with Gradle. This is the only service the browser talks to. It owns users, documents, ingest jobs, summaries, conversations, chat messages and quizzes, and it proxies AI work to FastAPI after checking ownership. The repo-wide architecture is in `../CLAUDE.md`.

## Commands

```bash
./gradlew test                                                  # all tests
./gradlew test --tests 'com.learnassist.api.service.StreakTest' # one class
./gradlew test --tests '*StreakTest.someMethod'                 # one method
./gradlew bootRun                                               # local run on :8081 against compose Postgres (localhost:55432)
```

- `ApiApplicationTests` is a bare `@SpringBootTest` without Testcontainers wiring. It needs the Compose Postgres running on `localhost:55432`, where Flyway migrates and Hibernate validates. The other tests are plain unit tests. Testcontainers (`postgresql`) is on the test classpath if you need an isolated database.
- The Docker image builds with `gradle bootJar -x test`. Rebuild the container after code changes: `docker compose up -d --build api`.
- Configuration is in `src/main/resources/application.yml` and bound to `config/AppProperties` (`app.*`). Compose overrides it through env vars, including `SERVER_PORT=8080` inside the container.

## Structure

`com.learnassist.api`:
- `domain/`: JPA entities and enums (`DocType`, `DocumentStatus`, `IngestStage`).
- `repository/`: Spring Data repositories.
- `service/`: business logic. `DocumentService` covers upload, ingest and download. `ConversationService` covers chats, attachments and asking. There are also `QuizService`, `DashboardService` (aggregate queries in the student's time zone), `StorageService` (S3 presigning), `AiClient` (HTTP to FastAPI) and `RateLimiter`.
- `web/`: controllers, `dto/Dtos.java` and `dto/QuizDtos.java` (records), `ApiException`, `GlobalExceptionHandler` and `RequestIdFilter` (MDC `requestId`, forwarded to FastAPI as `X-Request-Id`).
- `security/`: stateless JWT (jjwt). `JwtAuthFilter` puts the `User` entity in as the principal. Get it with `CurrentUser.require()`. `/api/auth/**` and the actuator health endpoints are public, and everything else needs authentication.

**Upload flow:** `POST /api/documents` creates the row and returns a presigned PUT URL. The browser uploads straight to RustFS. Then `POST /api/documents/{id}/ingest` makes `AiClient.startIngest` call FastAPI `/ingest`, which returns 202. FastAPI then updates `ingest_jobs`/`documents` itself, and the client polls `GET /api/documents/{id}`. Links (web or YouTube) go through `POST /api/documents/links`, with no upload.

## Rules to keep

- **Ownership is part of the lookup:** use `findByIdAndOwnerId(id, CurrentUser.require().getId())`. Don't load by id and compare owners afterwards. Dashboard aggregates put the owner filter in every `WHERE`, including joins.
- **Schema changes are Flyway migrations** (`src/main/resources/db/migration/V{n}__name.sql`, next number after the highest). `ddl-auto=validate`, so a changed entity without a migration fails at boot. Tables that only Python uses (`chunks`) are also migrated here. **Don't add a JPA entity for `chunks`.** The pgvector extension comes from `../db/init`, not a migration.
- **Errors:** throw `ApiException(HttpStatus, message)`. `GlobalExceptionHandler` turns it into the `{message}` body the web client displays.
- **DTOs are records in `web/dto`.** Never serialise entities directly. `QuestionResponse` has no answer fields, and the answer key appears only in `GradeResponse` after submission.
- **`AiClient` request records** serialise as camelCase and must match the FastAPI `ServiceRequest` models field for field. The AI timeout is 600 s because local LLM calls are slow.
- **S3:** `StorageConfig` builds two clients. The server-side client uses `app.s3.endpoint` and the presigner uses `app.s3.public-endpoint`. Both use path-style addressing. Don't merge them.
- **`RateLimiter`** is in-memory and per-instance.
- **Slide decks** (`SlideService`) generate on a virtual-thread executor: `AiClient.generateSlides` → `SlidesClient.render` → READY. Decks left GENERATING/RENDERING are failed at startup. The built site is streamed from RustFS by `SlideController#view`, the only route outside JWT auth (see its own `SecurityFilterChain`, `@Order(1)`). It answers 404 with `setStatus`, not `sendError`, because an error dispatch would land in the JWT chain and turn into a 401.
- **CORS** allows exactly one origin, `app.cors-origin`, on `/api/**`.
