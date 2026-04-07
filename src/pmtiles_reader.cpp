// SPDX-License-Identifier: MIT

#include "pmtiles_reader.h"
#include <QDebug>
#include <algorithm>
#include <cstring>
#include <zlib.h>

// ── Hilbert curve (signed int for x/y to avoid underflow in rotation) ────────

static uint64_t hilbertXy2d(int n, int x, int y)
{
    uint64_t d = 0;
    for (int s = n / 2; s > 0; s /= 2) {
        int rx = (x & s) > 0 ? 1 : 0;
        int ry = (y & s) > 0 ? 1 : 0;
        d += static_cast<uint64_t>(s) * s * ((3 * rx) ^ ry);
        if (ry == 0) {
            if (rx == 1) {
                x = s - 1 - x;
                y = s - 1 - y;
            }
            std::swap(x, y);
        }
    }
    return d;
}

static uint64_t zxyToTileId(int z, int x, int y)
{
    if (z == 0)
        return 0;
    uint64_t acc = 0;
    for (int i = 0; i < z; ++i)
        acc += uint64_t(1) << (2 * i);
    return acc + hilbertXy2d(1 << z, x, y);
}

// ── Varint (protobuf-style) ──────────────────────────────────────────────────

static uint64_t readVarint(const uint8_t* data, size_t size, size_t& pos)
{
    uint64_t val = 0;
    int shift = 0;
    while (pos < size) {
        uint8_t b = data[pos++];
        val |= uint64_t(b & 0x7F) << shift;
        if ((b & 0x80) == 0)
            break;
        shift += 7;
    }
    return val;
}

// ── Little-endian uint64 ─────────────────────────────────────────────────────

static uint64_t readU64LE(const uint8_t* p)
{
    uint64_t v = 0;
    for (int i = 7; i >= 0; --i)
        v = (v << 8) | p[i];
    return v;
}

// ── PmtilesReader ────────────────────────────────────────────────────────────

PmtilesReader::~PmtilesReader()
{
    if (m_file.isOpen())
        m_file.close();
}

bool PmtilesReader::open(const QString& path)
{
    m_file.setFileName(path);
    if (!m_file.open(QIODevice::ReadOnly)) {
        qWarning() << "PMTiles: cannot open" << path;
        return false;
    }

    QByteArray hdr = m_file.read(127);
    if (hdr.size() < 127) {
        qWarning() << "PMTiles: file too short";
        return false;
    }

    auto p = reinterpret_cast<const uint8_t*>(hdr.constData());
    if (std::memcmp(p, "PMTiles", 7) != 0 || p[7] != 3) {
        qWarning() << "PMTiles: not a v3 file";
        return false;
    }

    m_header.rootDirOffset       = readU64LE(p +  8);
    m_header.rootDirLength       = readU64LE(p + 16);
    m_header.metadataOffset      = readU64LE(p + 24);
    m_header.metadataLength      = readU64LE(p + 32);
    m_header.leafDirsOffset      = readU64LE(p + 40);
    m_header.leafDirsLength      = readU64LE(p + 48);
    m_header.tileDataOffset      = readU64LE(p + 56);
    m_header.tileDataLength      = readU64LE(p + 64);
    m_header.addressedTiles      = readU64LE(p + 72);
    m_header.tileEntries         = readU64LE(p + 80);
    m_header.tileContents        = readU64LE(p + 88);
    m_header.clustered           = p[96];
    m_header.internalCompression = p[97];
    m_header.tileCompression     = p[98];
    m_header.tileType            = p[99];
    m_header.minZoom             = p[100];
    m_header.maxZoom             = p[101];

    QByteArray rootRaw = readRange(m_header.rootDirOffset, m_header.rootDirLength);
    QByteArray rootDecomp = decompressInternal(rootRaw);
    m_rootDir = parseDirectory(rootDecomp);

    qDebug().noquote()
        << QString("PMTiles: %1  zoom %2-%3  root entries: %4")
               .arg(path)
               .arg(m_header.minZoom)
               .arg(m_header.maxZoom)
               .arg(m_rootDir.size());
    return true;
}

QByteArray PmtilesReader::getTile(int z, int x, int y)
{
    uint64_t tileId = zxyToTileId(z, x, y);

    const DirEntry* entry = findTile(tileId, m_rootDir);
    if (!entry)
        return {};

    // Direct tile (runLength > 0)
    if (entry->runLength > 0) {
        QByteArray raw = readRange(m_header.tileDataOffset + entry->offset,
                                   entry->length);
        return (m_header.tileCompression == 2) ? decompressGzip(raw) : raw;
    }

    // Leaf directory (runLength == 0) — read, decompress, search again
    QByteArray leafRaw = readRange(m_header.leafDirsOffset + entry->offset,
                                   entry->length);
    auto leafDir = parseDirectory(decompressInternal(leafRaw));

    const DirEntry* leaf = findTile(tileId, leafDir);
    if (!leaf || leaf->runLength == 0)
        return {};

    QByteArray raw = readRange(m_header.tileDataOffset + leaf->offset,
                               leaf->length);
    return (m_header.tileCompression == 2) ? decompressGzip(raw) : raw;
}

// ── Private helpers ──────────────────────────────────────────────────────────

QByteArray PmtilesReader::readRange(uint64_t offset, uint64_t length)
{
    if (!m_file.seek(static_cast<qint64>(offset)))
        return {};
    return m_file.read(static_cast<qint64>(length));
}

QByteArray PmtilesReader::decompressGzip(const QByteArray& data)
{
    if (data.size() < 2)
        return data;

    auto bytes = reinterpret_cast<const uint8_t*>(data.constData());
    if (bytes[0] != 0x1f || bytes[1] != 0x8b)
        return data; // not gzip — return as-is

    z_stream strm{};
    // MAX_WBITS + 16 = decode gzip wrapper
    if (inflateInit2(&strm, MAX_WBITS + 16) != Z_OK)
        return {};

    strm.next_in  = const_cast<Bytef*>(reinterpret_cast<const Bytef*>(data.constData()));
    strm.avail_in = static_cast<uInt>(data.size());

    QByteArray result;
    char buf[65536];
    int ret;
    do {
        strm.next_out  = reinterpret_cast<Bytef*>(buf);
        strm.avail_out = sizeof(buf);
        ret = inflate(&strm, Z_NO_FLUSH);
        if (ret != Z_OK && ret != Z_STREAM_END) {
            inflateEnd(&strm);
            return {};
        }
        result.append(buf, static_cast<int>(sizeof(buf) - strm.avail_out));
    } while (ret != Z_STREAM_END);

    inflateEnd(&strm);
    return result;
}

QByteArray PmtilesReader::decompressInternal(const QByteArray& data)
{
    if (m_header.internalCompression == 2) // gzip
        return decompressGzip(data);
    return data;
}

std::vector<DirEntry> PmtilesReader::parseDirectory(const QByteArray& data)
{
    if (data.isEmpty())
        return {};

    auto p    = reinterpret_cast<const uint8_t*>(data.constData());
    size_t sz = static_cast<size_t>(data.size());
    size_t pos = 0;

    uint64_t n = readVarint(p, sz, pos);
    std::vector<DirEntry> entries(n);

    // Tile IDs — delta-coded
    uint64_t tileId = 0;
    for (uint64_t i = 0; i < n; ++i) {
        tileId += readVarint(p, sz, pos);
        entries[i].tileId = tileId;
    }

    // Run lengths
    for (uint64_t i = 0; i < n; ++i)
        entries[i].runLength = static_cast<uint32_t>(readVarint(p, sz, pos));

    // Lengths
    for (uint64_t i = 0; i < n; ++i)
        entries[i].length = static_cast<uint32_t>(readVarint(p, sz, pos));

    // Offsets — 0 means contiguous with previous entry
    for (uint64_t i = 0; i < n; ++i) {
        uint64_t raw = readVarint(p, sz, pos);
        if (i > 0 && raw == 0)
            entries[i].offset = entries[i - 1].offset + entries[i - 1].length;
        else
            entries[i].offset = (raw > 0) ? raw - 1 : 0;
    }

    return entries;
}

const DirEntry* PmtilesReader::findTile(uint64_t tileId,
                                        const std::vector<DirEntry>& dir)
{
    if (dir.empty())
        return nullptr;

    // upper_bound: first entry with tileId > target, then back one
    auto it = std::upper_bound(dir.begin(), dir.end(), tileId,
                               [](uint64_t id, const DirEntry& e) {
                                   return id < e.tileId;
                               });
    if (it == dir.begin())
        return nullptr;
    --it;

    // Leaf directory pointer
    if (it->runLength == 0)
        return &(*it);

    // Check tile falls within run [tileId .. tileId + runLength)
    if (tileId >= it->tileId && (tileId - it->tileId) < it->runLength)
        return &(*it);

    return nullptr;
}
