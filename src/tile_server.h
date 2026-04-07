// Embedded HTTP tile server — serves PMTiles archives and style JSON
// SPDX-License-Identifier: MIT

#pragma once

#include "pmtiles_reader.h"
#include <QHash>
#include <QObject>
#include <QTcpServer>
#include <memory>

class QTcpSocket;

class TileServer : public QObject {
    Q_OBJECT
public:
    explicit TileServer(QObject* parent = nullptr);

    bool loadArchive(const QString& name, const QString& path);
    bool loadDirectory(const QString& dirPath);
    bool start(quint16 port = 0);
    quint16 port() const;

private slots:
    void onNewConnection();
    void onReadyRead();

private:
    void handleRequest(QTcpSocket* socket, const QByteArray& requestLine);
    void serveTile(QTcpSocket* socket, const QString& archive, int z, int x, int y);
    void serveStyleJson(QTcpSocket* socket, const QString& filename);
    void sendResponse(QTcpSocket* socket, int code,
                      const QByteArray& contentType, const QByteArray& body);
    void sendError(QTcpSocket* socket, int code, const QByteArray& msg);

    QTcpServer m_server;
    QHash<QString, std::shared_ptr<PmtilesReader>> m_archives;
    QHash<QTcpSocket*, QByteArray> m_buffers;
    QString m_tilesDir;
};
