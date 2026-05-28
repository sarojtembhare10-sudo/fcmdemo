import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/services.dart';

// IMPORTANT: This file will be generated when you run `flutterfire configure`.
// We use a try/catch below in case you haven't run it yet, so the app still compiles.
import 'firebase_options.dart' if (dart.library.html) 'firebase_options.dart';

// Background message handler
@pragma('vm:entry-point')
Future<void> _firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  if (defaultTargetPlatform == TargetPlatform.android && !kIsWeb) {
    await Firebase.initializeApp();
  } else {
    await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);
  }
  print("Handling a background message: ${message.messageId}");
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  try {
    if (defaultTargetPlatform == TargetPlatform.android && !kIsWeb) {
      // On Android, rely entirely on the native google-services.json
      await Firebase.initializeApp();
    } else {
      await Firebase.initializeApp(
        options: DefaultFirebaseOptions.currentPlatform,
      );
    }
    FirebaseMessaging.onBackgroundMessage(_firebaseMessagingBackgroundHandler);
  } catch (e) {
    print('\n=============================================');
    print('ERROR INITIALIZING FIREBASE!');
    print('Have you run `flutterfire configure` yet?');
    print('Error details: $e');
    print('=============================================\n');
  }

  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'FCM PoC',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepPurple),
        useMaterial3: true,
      ),
      home: const FcmHomePage(),
    );
  }
}

class FcmHomePage extends StatefulWidget {
  const FcmHomePage({super.key});

  @override
  State<FcmHomePage> createState() => _FcmHomePageState();
}

class _FcmHomePageState extends State<FcmHomePage> {
  String? _token;
  String _messageText = "Waiting for messages...";
  String _registrationStatus = "Not registered yet";

  @override
  void initState() {
    super.initState();
    _setupFCM();
  }

  /// Saves the FCM token to Firestore so the server can discover it automatically.
  /// Uses the token string as the document ID — idempotent (safe to call multiple times).
  Future<void> _registerTokenToFirestore(String token) async {
    try {
      final String platform;
      if (defaultTargetPlatform == TargetPlatform.android) {
        platform = 'android';
      } else if (defaultTargetPlatform == TargetPlatform.iOS) {
        platform = 'ios';
      } else {
        platform = 'unknown';
      }

      await FirebaseFirestore.instance
          .collection('device_tokens')
          .doc(token) // Use token as doc ID to prevent duplicates
          .set({
        'token': token,
        'platform': platform,
        'lastSeen': FieldValue.serverTimestamp(),
        'createdAt': FieldValue.serverTimestamp(),
      }, SetOptions(merge: true)); // merge: true preserves 'createdAt' on updates

      print("✅ Token registered to Firestore successfully.");
      if (mounted) {
        setState(() {
          _registrationStatus = "✅ Registered to server";
        });
      }
    } catch (e) {
      print("❌ Failed to register token to Firestore: $e");
      if (mounted) {
        setState(() {
          _registrationStatus = "❌ Registration failed";
        });
      }
    }
  }

  Future<void> _setupFCM() async {
    try {
      FirebaseMessaging messaging = FirebaseMessaging.instance;

      NotificationSettings settings = await messaging.requestPermission(
        alert: true,
        announcement: false,
        badge: true,
        carPlay: false,
        criticalAlert: false,
        provisional: false,
        sound: true,
      );

      print('User granted permission: ${settings.authorizationStatus}');

      if (settings.authorizationStatus == AuthorizationStatus.authorized) {
        // 1. Listen for token refreshes — re-register whenever the token changes
        messaging.onTokenRefresh.listen((newToken) {
          print("FCM TOKEN REFRESHED: $newToken");
          if (mounted) {
            setState(() {
              _token = newToken;
              _registrationStatus = "Re-registering...";
            });
          }
          _registerTokenToFirestore(newToken);
        });

        // 2. Get the device token with a 3-attempt retry loop
        String? token;
        int retries = 3;
        while (retries > 0) {
          try {
            token = await messaging.getToken();
            break;
          } catch (e) {
            retries--;
            if (retries == 0) {
              print("FCM Setup Error: $e");
              if (mounted) {
                setState(() {
                  _messageText = "Connecting to Google Play Services...\n(Waiting for background sync)";
                  _registrationStatus = "Waiting for token...";
                });
              }
              return;
            }
            await Future.delayed(const Duration(seconds: 3));
          }
        }

        print("\n=======================");
        print("FCM DEVICE TOKEN:");
        print(token);
        print("=======================\n");

        setState(() {
          _token = token;
          _registrationStatus = "Registering...";
        });

        // 3. Register the token to Firestore
        if (token != null) {
          await _registerTokenToFirestore(token);
        }

        // 4. Handle foreground messages
        FirebaseMessaging.onMessage.listen((RemoteMessage message) {
          print('Got a message whilst in the foreground!');
          print('Message data: ${message.data}');

          if (message.notification != null) {
            print('Message also contained a notification: ${message.notification}');
            
            final time = message.sentTime ?? DateTime.now();
            final timeString = "${time.hour}:${time.minute.toString().padLeft(2, '0')}:${time.second.toString().padLeft(2, '0')}";
            
            setState(() {
              _messageText = "🔔 Received at: $timeString\n\nTitle: ${message.notification?.title}\nBody: ${message.notification?.body}";
            });
            
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('Received: ${message.notification?.title}')),
            );
          }
        });
      }
    } catch (e) {
       setState(() {
          _messageText = "Error: $e";
       });
       print("FCM Setup Error: $e");
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Android FCM PoC'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'FCM Device Token:',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.blueGrey.shade50,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.blueGrey.shade200),
                ),
                child: SelectableText(
                  _token ?? 'Loading token or Firebase not configured...',
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 13, color: Colors.blueGrey, fontFamily: 'monospace'),
                ),
              ),
              const SizedBox(height: 8),
              // Registration status badge
              Center(
                child: Chip(
                  label: Text(
                    _registrationStatus,
                    style: const TextStyle(fontSize: 12),
                  ),
                  backgroundColor: _registrationStatus.startsWith('✅')
                      ? Colors.green.shade100
                      : _registrationStatus.startsWith('❌')
                          ? Colors.red.shade100
                          : Colors.orange.shade100,
                ),
              ),
              const SizedBox(height: 8),
              ElevatedButton.icon(
                onPressed: () {
                  if (_token != null) {
                    Clipboard.setData(ClipboardData(text: _token!));
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Token copied to clipboard!')),
                    );
                  }
                },
                icon: const Icon(Icons.copy),
                label: const Text('Copy Token'),
              ),
              const SizedBox(height: 32),
              Container(
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: Colors.green.shade50,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.green.shade200),
                ),
                child: Column(
                  children: [
                    const Icon(Icons.message, color: Colors.green, size: 32),
                    const SizedBox(height: 12),
                    Text(
                      _messageText,
                      textAlign: TextAlign.center,
                      style: const TextStyle(fontSize: 16, color: Colors.green),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
