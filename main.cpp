// MapLibre PoC — minimal Qt Quick application with embedded tile server
// SPDX-License-Identifier: MIT

#include <QDir>
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QSGRendererInterface>
#include <QUrl>

#include "tile_server.h"

// Search for tiles/ directory containing .pmtiles files
static QString findTilesDir()
{
    for (const char* candidate : {"tiles", "../tiles", "../../tiles"}) {
        QDir dir(candidate);
        if (dir.exists() && !dir.entryList({QStringLiteral("*.pmtiles")}).isEmpty())
            return dir.absolutePath();
    }
    return {};
}

int main(int argc, char *argv[])
{
    // MapLibre Native requires OpenGL (Metal on macOS/iOS).
#if !defined(Q_OS_MACOS) && !defined(Q_OS_IOS)
    QQuickWindow::setGraphicsApi(QSGRendererInterface::OpenGL);
#endif

    QGuiApplication app(argc, argv);
    app.setApplicationName(QStringLiteral("MapLibre PoC"));
    app.setApplicationVersion(QStringLiteral("0.1.0"));
    app.setOrganizationName(QStringLiteral("PoC"));

    // ── Embedded tile server ─────────────────────────────────────────────────
    TileServer tileServer;
    QString styleUrl;

    QString tilesDir = findTilesDir();
    if (!tilesDir.isEmpty() && tileServer.loadDirectory(tilesDir)) {
        tileServer.start(0); // OS picks a free port
        quint16 port = tileServer.port();
        styleUrl = QStringLiteral("http://localhost:%1/vector-style.json").arg(port);
        qDebug().noquote()
            << "Style URL:" << styleUrl;
    } else {
        // Fallback: MapLibre public demo tiles (online)
        styleUrl = QStringLiteral(
            "https://demotiles.maplibre.org/style.json");
        qWarning() << "No .pmtiles found — using online demo tiles";
    }

    // ── QML engine ───────────────────────────────────────────────────────────
    QQmlApplicationEngine engine;

    engine.rootContext()->setContextProperty(
        QStringLiteral("initialStyleUrl"), styleUrl);
    engine.rootContext()->setContextProperty(
        QStringLiteral("isOfflineMode"), !tilesDir.isEmpty());

    QObject::connect(
        &engine, &QQmlApplicationEngine::objectCreationFailed,
        &app,    []() { QCoreApplication::exit(-1); },
        Qt::QueuedConnection);

    engine.load(QUrl(QStringLiteral("qrc:/PocMap/qml/main.qml")));

    return app.exec();
}
