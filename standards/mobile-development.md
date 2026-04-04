# Mobile Development

## Framework Selection

| Framework | Language | When to use |
|-----------|----------|-------------|
| React Native | TypeScript | Web team building mobile. Shared logic with web app. Large ecosystem |
| Flutter | Dart | Performance-critical UI, custom rendering, design-heavy apps |
| SwiftUI (iOS) | Swift | iOS-only app, deep platform integration, ARKit/HealthKit |
| Jetpack Compose (Android) | Kotlin | Android-only app, deep platform integration |
| Kotlin Multiplatform | Kotlin | Shared business logic with native UI per platform |

**Default rule**: use React Native when the team already knows TypeScript and the app does not require heavy native rendering. Use native when platform-specific APIs are core to the experience.

## Project Structure

- Separate business logic from platform code. Business logic in a shared module, platform-specific code in platform directories
- Feature-based folder structure over layer-based. `features/auth/`, `features/orders/` over `screens/`, `services/`, `models/`
- One component per file. Export the component as default

## Navigation

- Use a typed navigation library. React Navigation with TypeScript types for React Native. Navigation Compose for Jetpack Compose
- Define all routes in a single file or enum. No magic strings for screen names
- Deep links map to routes. Every screen reachable by deep link must handle being the entry point (no assumed navigation stack)
- Handle back navigation explicitly. The Android back button and iOS swipe-back gesture must work correctly on every screen

## Offline Support

Mobile apps must handle network unavailability gracefully.

| Strategy | When to use |
|----------|-------------|
| Cache-first | Read-heavy screens. Show cached data, refresh in background |
| Network-first with fallback | Data must be fresh when available. Show cached only when offline |
| Offline queue | Write operations. Queue mutations locally, sync when online |

- Store pending writes in a persistent local queue (SQLite, MMKV, AsyncStorage)
- Sync queue on connectivity change. Resolve conflicts with last-write-wins or server-wins strategy
- Show sync status to the user. "Saved locally, syncing..." is better than silent background sync that may fail

## Performance

- **Startup time**: cold start under 2 seconds. Defer non-critical initialization. Lazy-load feature modules
- **List rendering**: use virtualized lists (FlatList, LazyColumn) for any list over 20 items. Never render all items at once
- **Image loading**: use progressive loading (blur placeholder, then full image). Cache images on disk. Resize to the display size, not the original resolution
- **Bundle size**: monitor APK/IPA size. Large bundles increase install abandonment. Use code splitting and tree shaking
- **Memory**: profile memory usage on low-end devices. A 2GB device has different constraints than a flagship
- **Animations**: run at 60fps. Offload animations to the native thread (Reanimated, LayoutAnimation). Never animate on the JS thread

## Push Notifications

- Request permission at a contextually appropriate moment, not on first launch. Explain the value before asking
- Handle notification payloads in both foreground and background states
- Deep link from notifications to the relevant screen with full context
- Support notification channels (Android) for user-controlled granularity
- Handle token refresh. Device tokens change. Update the server on every app launch

## App Store Compliance

| Platform | Key requirements |
|----------|-----------------|
| iOS | Privacy nutrition labels, ATT (App Tracking Transparency) prompt, no private API usage, review guidelines compliance |
| Android | Data safety section, target API level requirements, permissions must be justified, Play Store policies |

- Test on the minimum supported OS version, not just the latest
- Handle permission denials gracefully. The app must work (with reduced functionality) when the user denies camera, location, or notifications
- Over-the-air updates (CodePush, Expo Updates) for JS bundle changes. Native code changes require a store submission

## Testing

- **Unit tests**: business logic, state management, data transformations. No device needed
- **Component tests**: render individual screens with mock data. Verify layout and interaction
- **Integration tests**: test navigation flows and API integration against a test server
- **E2E tests**: Detox (React Native) or Maestro for full device automation
- **Device matrix**: test on at least 3 screen sizes (small phone, large phone, tablet) and 2 OS versions (current, minimum supported)
- **Performance tests**: measure startup time, scroll performance, and memory on a low-end device. CI should fail if metrics regress

## Related Standards

- `standards/frontend.md`: Frontend Design
- `standards/authentication.md`: Authentication
- `standards/performance-budgets.md`: Performance Budgets
