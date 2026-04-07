// SPDX-License-Identifier: MIT

#include "tile_server.h"
#include <QDebug>
#include <QDir>
#include <QFile>
#include <QRegularExpression>
#include <QTcpSocket>

TileServer::TileServer(QObject* parent)
    : QObject(parent)
{
    connect(&m_server, &QTcpServer::newConnection,
            this, &TileServer::onNewConnection);
}

bool TileServer::loadArchive(const QString& name, const QString& path)
{
    auto reader = std::make_shared<PmtilesReader>();
    if (!reader->open(path))
        return false;
    m_archives[name] = reader;
    return true;
}

bool TileServer::loadDirectory(const QString& dirPath)
{
    m_tilesDir = dirPath;
    QDir dir(dirPath);
    bool any = false;
    const auto entries = dir.entryInfoList({QStringLiteral("*.pmtiles")}, QDir::Files);
    for (const auto& fi : entries) {
        if (loadArchive(fi.baseName(), fi.absoluteFilePath()))
            any = true;
    }
    return any;
}

bool TileServer::start(quint16 port)
{
    if (!m_server.listen(QHostAddress::LocalHost, port)) {
        qWarning() << "TileServer: listen failed:" << m_server.errorString();
        return false;
    }
    qDebug().noquote()
        << QString("TileServer: http://localhost:%1/").arg(m_server.serverPort());
    return true;
}

quint16 TileServer::port() const
{
    return m_server.serverPort();
}

// ── Connection handling ──────────────────────────────────────────────────────

void TileServer::onNewConnection()
{
    while (auto* sock = m_server.nextPendingConnection()) {
        connect(sock, &QTcpSocket::readyRead, this, &TileServer::onReadyRead);
        connect(sock, &QTcpSocket::disconnected, sock, [this, sock]() {
            m_buffers.remove(sock);
            sock->deleteLater();
        });
    }
}

void TileServer::onReadyRead()
{
    auto* sock = qobject_cast<QTcpSocket*>(sender());
    if (!sock)
        return;

    m_buffers[sock].append(sock->readAll());

    // Process all complete HTTP requests in the buffer
    while (m_buffers[sock].contains("\r\n\r\n")) {
        int end = m_buffers[sock].indexOf("\r\n\r\n");
        QByteArray headers = m_buffers[sock].left(end);
        m_buffers[sock].remove(0, end + 4);

        int lineEnd = headers.indexOf("\r\n");
        QByteArray firstLine = (lineEnd >= 0) ? headers.left(lineEnd) : headers;
        handleRequest(sock, firstLine);
    }
}

// ── Request routing ──────────────────────────────────────────────────────────

void TileServer::handleRequest(QTcpSocket* socket, const QByteArray& requestLine)
{
    auto parts = requestLine.split(' ');
    if (parts.size() < 2) {
        sendError(socket, 400, "Bad Request");
        return;
    }

    QByteArray method = parts[0];
    QString path = QString::fromUtf8(parts[1]);

    if (method == "OPTIONS") {
        sendResponse(socket, 200, "text/plain", {});
        return;
    }
    if (method != "GET") {
        sendError(socket, 405, "Method Not Allowed");
        return;
    }

    // /<archive>/<z>/<x>/<y>
    static const QRegularExpression tileRe(
        QStringLiteral("^/([^/]+)/(\\d+)/(\\d+)/(\\d+)$"));
    auto match = tileRe.match(path);
    if (match.hasMatch()) {
        serveTile(socket,
                  match.captured(1),
                  match.captured(2).toInt(),
                  match.captured(3).toInt(),
                  match.captured(4).toInt());
        return;
    }

    // /*.json — style files with port substitution
    if (path.endsWith(QLatin1String(".json")) && !path.contains(QLatin1String(".."))) {
        serveStyleJson(socket, path.mid(1)); // strip leading /
        return;
    }

    sendError(socket, 404, "Not Found");
}

void TileServer::serveTile(QTcpSocket* socket, const QString& archive,
                           int z, int x, int y)
{
    auto it = m_archives.find(archive);
    if (it == m_archives.end()) {
        sendError(socket, 404, "Archive not found");
        return;
    }

    QByteArray tile = it->get()->getTile(z, x, y);
    if (tile.isEmpty()) {
        sendResponse(socket, 204, "application/x-protobuf", {});
        return;
    }

    sendResponse(socket, 200, "application/x-protobuf", tile);
}

void TileServer::serveStyleJson(QTcpSocket* socket, const QString& filename)
{
    QFile f(m_tilesDir + QStringLiteral("/") + filename);
    if (!f.open(QIODevice::ReadOnly)) {
        sendError(socket, 404, "Style not found");
        return;
    }

    QString json = QString::fromUtf8(f.readAll());
    // Replace any localhost:PORT with our actual port
    json.replace(QRegularExpression(QStringLiteral("localhost:\\d+")),
                 QStringLiteral("localhost:%1").arg(m_server.serverPort()));

    sendResponse(socket, 200, "application/json", json.toUtf8());
}

// ── HTTP response ────────────────────────────────────────────────────────────

void TileServer::sendResponse(QTcpSocket* socket, int code,
                              const QByteArray& contentType,
                              const QByteArray& body)
{
    const char* status;
    switch (code) {
    case 200: status = "OK"; break;
    case 204: status = "No Content"; break;
    case 400: status = "Bad Request"; break;
    case 404: status = "Not Found"; break;
    case 405: status = "Method Not Allowed"; break;
    default:  status = "Error"; break;
    }

    QByteArray resp;
    resp.reserve(256 + body.size());
    resp.append("HTTP/1.1 ");
    resp.append(QByteArray::number(code));
    resp.append(' ');
    resp.append(status);
    resp.append("\r\nContent-Type: ");
    resp.append(contentType);
    resp.append("\r\nContent-Length: ");
    resp.append(QByteArray::number(body.size()));
    resp.append("\r\nAccess-Control-Allow-Origin: *"
                "\r\nAccess-Control-Allow-Methods: GET, OPTIONS"
                "\r\nConnection: keep-alive"
                "\r\n\r\n");
    resp.append(body);

    socket->write(resp);
    socket->flush();
}

void TileServer::sendError(QTcpSocket* socket, int code, const QByteArray& msg)
{
    sendResponse(socket, code, "text/plain", msg);
}
