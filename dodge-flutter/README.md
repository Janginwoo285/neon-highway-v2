# Dodge Racer — Flutter Mobile App

This is a Flutter Android/iOS wrapper around the actual HTML canvas game hosted at:
https://janginwoo285.github.io/neon-highway-v2/dodge-online/

The Flutter app uses `webview_flutter`, so the **game engine remains JavaScript** and is not rewritten in Dart. Account login and online leaderboard use the Spring Boot service configured inside the web game.

## Build
Install Flutter and Android Studio or Xcode on your development computer.

```bash
cd dodge-flutter
flutter create . --platforms=android,ios
flutter pub get
flutter run
```

Android requires internet permission; confirm `android/app/src/main/AndroidManifest.xml` contains `<uses-permission android:name="android.permission.INTERNET" />` inside `<manifest>` before building.

## Status
- Source code exists, but APK/IPA has not been built or device-tested.
- HTML game works as a static page; account and global ranking need a deployed Spring API.
- This wrapper needs an internet connection to load the game.
