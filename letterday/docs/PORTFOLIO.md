# Letterday — Portfolio Case Study (work in progress)

## 01. Problem / hypothesis
Existing diary tools can feel like rigid forms, while some users want a gentle, letter-like writing experience and the choice to share selected entries. This is a **product hypothesis**, not a measured market research finding.

## 02. Proposed audience
People who want a calm, warm place to write a short letter to themselves and occasionally share writing with others.

## 03. Service principles
- **Write first:** one screen with date, title, body and mood.
- **Private by default:** no automatic publishing; public visibility explicitly selected.
- **Permission first:** reminder OFF until a user chooses to enable it and browser approves notification permission.
- **Expressive:** attach a photo and draw with a pointer/touch canvas.
- **Portable:** local backup as JSON and responsive layout.

## 04. User flow
Start -> Compose letter -> Choose mood -> Optional image/drawing -> Choose private/public -> Save -> My Letters -> Calendar / Edit / Delete. Shared feed: connect Spring server -> register/login -> intentionally publish -> public feed.

## 05. Technology architecture
- Web: HTML, CSS, vanilla JavaScript, Canvas 2D, LocalStorage, Fetch API, Web Notifications.
- Backend: Java 17, Spring Boot REST, BCrypt passwords, opaque bearer tokens, JDBC and PostgreSQL.
- Mobile: Flutter and Dart, consuming the same API.
- GitHub: source control and static Pages candidate.

## 06. Acceptance tests (to execute, not yet verified)
1. Write a private letter and reopen it from My Letters.
2. Edit and delete a letter.
3. Change month: calendar highlights the dates with entries.
4. Attach JPEG/PNG/WebP under 1MB; draw strokes with touch.
5. On first visit, notification permission is not requested; only requested after clicking opt-in.
6. Without server login, public publishing is rejected.
7. With two real accounts and persistent server, private entries never appear in another account's private list.
8. Only public entries appear in shared feed; changing a post to private removes it from the feed.
9. Check 360px mobile width, keyboard navigation, and reload behavior.
10. Confirm GitHub Pages, deployed API and Flutter build using actual devices.

## 07. Measurable outcomes to collect
- Number of usability testers (actual count)
- Number of observed task completions / failures
- Changes made after feedback
- Actual deployment URLs and screenshots

Do not claim satisfaction improvements, customer growth or usage counts without measurement.

## 08. Next production milestones
- Authentication hardening and email verification
- Content reporting, moderation and user blocking
- Image storage in cloud object storage
- True background push notifications with explicit consent
- Flutter feature parity for photos, drawing, calendar and reminders
- Automated tests and accessibility review
