// PMTiles v3 reader — reads vector tiles from .pmtiles archives
// Reference: https://github.com/protomaps/PMTiles/blob/main/spec/v3/spec.md
// SPDX-License-Identifier: MIT

#pragma once

#include <QByteArray>
#include <QFile>
#include <QString>
#include <cstdint>
#include <vector>

struct PmtilesHeader {
    uint64_t rootDirOffset   = 0;
    uint64_t rootDirLength   = 0;
    uint64_t metadataOffset  = 0;
    uint64_t metadataLength  = 0;
    uint64_t leafDirsOffset  = 0;
    uint64_t leafDirsLength  = 0;
    uint64_t tileDataOffset  = 0;
    uint64_t tileDataLength  = 0;
    uint64_t addressedTiles  = 0;
    uint64_t tileEntries     = 0;
    uint64_t tileContents    = 0;
    uint8_t  clustered           = 0;
    uint8_t  internalCompression = 0; // 1=none, 2=gzip, 3=br, 4=zstd
    uint8_t  tileCompression     = 0;
    uint8_t  tileType            = 0; // 1=mvt, 2=png, 3=jpeg
    uint8_t  minZoom             = 0;
    uint8_t  maxZoom             = 0;
};

struct DirEntry {
    uint64_t tileId    = 0;
    uint64_t offset    = 0;
    uint32_t length    = 0;
    uint32_t runLength = 0; // 0 = leaf directory pointer
};

class PmtilesReader {
public:
    PmtilesReader() = default;
    ~PmtilesReader();

    PmtilesReader(const PmtilesReader&) = delete;
    PmtilesReader& operator=(const PmtilesReader&) = delete;

    bool open(const QString& path);
    QByteArray getTile(int z, int x, int y);
    const PmtilesHeader& header() const { return m_header; }

private:
    QByteArray readRange(uint64_t offset, uint64_t length);
    QByteArray decompressGzip(const QByteArray& data);
    QByteArray decompressInternal(const QByteArray& data);
    std::vector<DirEntry> parseDirectory(const QByteArray& data);
    const DirEntry* findTile(uint64_t tileId, const std::vector<DirEntry>& dir);

    QFile m_file;
    PmtilesHeader m_header{};
    std::vector<DirEntry> m_rootDir;
};
