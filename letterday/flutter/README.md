# Letterday Flutter mobile client

A warm-tone Flutter mobile starter built against the same Spring Boot API as the web version.

## Run locally
Install Flutter SDK and either Android Studio or Xcode. From this directory:

```sh
flutter create . --platforms=android,ios
flutter pub get
flutter run
```

In Settings, enter the URL of the deployed Spring Boot API (HTTPS), then register or log in.

Current Flutter features: registration/login, write letters, mood choice, private/public visibility, your diary list, public feed, delete letters.

Web-only for now: photo attachments, drawings, calendar, opt-in notifications, JSON backup. Flutter is a starter, not a production app. Tokens live only in memory. The Spring backend must be deployed independently.
