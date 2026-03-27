// MapLibre PoC — minimal Qt Quick application
// SPDX-License-Identifier: MIT

#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QSGRendererInterface>
#include <QStringList>
#include <QUrl>

int main(int argc, char *argv[])
{
    // MapLibre Native requires OpenGL (Metal on macOS/iOS, Vulkan optional on Linux).
    // Force OpenGL on Windows/Linux; on macOS the default Metal works fine too.
#if !defined(Q_OS_MACOS) && !defined(Q_OS_IOS)
    QQuickWindow::setGraphicsApi(QSGRendererInterface::OpenGL);
#endif

    QGuiApplication app(argc, argv);
    app.setApplicationName(QStringLiteral("MapLibre PoC"));
    app.setApplicationVersion(QStringLiteral("0.1.0"));
    app.setOrganizationName(QStringLiteral("PoC"));

    // ── Determine style URL ────────────────────────────────────────────────
    // Default: MapLibre public demo tiles (online, no API key needed)
    // --offline  → http://localhost:8080/offline-style.json
    //              (requires: cd tiles && python3 ../scripts/serve_local.py)
    // <url>      → last non-flag argument used verbatim as style URL

    const QStringList args = app.arguments();
    const bool offlineMode = args.contains(QStringLiteral("--offline"));

    QString styleUrl;
    if (offlineMode) {
        styleUrl = QStringLiteral("http://localhost:8080/offline-style.json");
    } else {
        styleUrl = QStringLiteral("https://demotiles.maplibre.org/style.json");
    }

    // Allow passing a custom style URL as the last argument
    if (args.size() > 1 && !args.last().startsWith(QLatin1Char('-'))) {
        styleUrl = args.last();
    }

    // ── QML engine ────────────────────────────────────────────────────────
    QQmlApplicationEngine engine;

    // Expose to QML
    engine.rootContext()->setContextProperty(QStringLiteral("initialStyleUrl"), styleUrl);
    engine.rootContext()->setContextProperty(QStringLiteral("isOfflineMode"),   offlineMode);

    QObject::connect(
        &engine, &QQmlApplicationEngine::objectCreationFailed,
        &app,    []() { QCoreApplication::exit(-1); },
        Qt::QueuedConnection
    );

    engine.loadFromModule(QStringLiteral("PocMap"), QStringLiteral("main"));

    return app.exec();
}
