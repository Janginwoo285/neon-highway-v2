import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const DodgeApp());
}

const gameUrl = 'https://janginwoo285.github.io/neon-highway-v2/dodge-online/';

class DodgeApp extends StatelessWidget {
  const DodgeApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: '장애물 피하기',
      theme: ThemeData.dark(useMaterial3: true).copyWith(
        scaffoldBackgroundColor: const Color(0xFF0E1116),
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF0A84FF),
          brightness: Brightness.dark,
        ),
      ),
      home: const GameScreen(),
    );
  }
}

class GameScreen extends StatefulWidget {
  const GameScreen({super.key});

  @override
  State<GameScreen> createState() => _GameScreenState();
}

class _GameScreenState extends State<GameScreen> {
  late final WebViewController controller;
  int progress = 0;
  String? error;

  @override
  void initState() {
    super.initState();
    controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(const Color(0xFF0E1116))
      ..setNavigationDelegate(NavigationDelegate(
        onProgress: (p) => setState(() => progress = p),
        onWebResourceError: (e) {
          if (e.isForMainFrame == true) {
            setState(() => error = e.description);
          }
        },
      ))
      ..loadRequest(Uri.parse(gameUrl));
  }

  Future<void> reload() async {
    setState(() => error = null);
    await controller.reload();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('🚗 장애물 피하기'),
        backgroundColor: const Color(0xFF171B22),
        actions: [
          IconButton(
            tooltip: '새로고침',
            onPressed: reload,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: Stack(children: [
          WebViewWidget(controller: controller),
          if (progress < 100 && error == null)
            LinearProgressIndicator(value: progress / 100),
          if (error != null)
            ColoredBox(
              color: const Color(0xFF0E1116),
              child: Center(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.wifi_off, size: 40),
                      const SizedBox(height: 16),
                      const Text('네트워크를 확인해 주세요.'),
                      const SizedBox(height: 8),
                      Text(error!, textAlign: TextAlign.center),
                      const SizedBox(height: 16),
                      ElevatedButton(
                        onPressed: reload,
                        child: const Text('다시 시도'),
                      ),
                    ],
                  ),
                ),
              ),
            ),
        ]),
      ),
    );
  }
}
