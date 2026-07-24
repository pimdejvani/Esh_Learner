/// App-session UI toggles that don't warrant DB persistence.
///
/// [autoKeyboardEnabled] (item 13, 2026-07-24): typed-answer games focus
/// the answer field on load so the on-screen keyboard opens automatically
/// (and a desktop user can just start typing). The player can flip it from
/// the keyboard icon in any typed game's top bar; the choice lasts the app
/// session.
library;

import 'package:flutter/foundation.dart';

final ValueNotifier<bool> autoKeyboardEnabled = ValueNotifier<bool>(true);
