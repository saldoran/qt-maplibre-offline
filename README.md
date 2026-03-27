# MapLibre Native Qt — PoC

Минимальное proof-of-concept приложение: Qt Quick + MapLibre Native for Qt.
Показывает карту с pan/zoom/rotation/pitch, сценарий online и **offline** (локальные тайлы).

---

## Что умеет PoC

| Функция | Статус | Примечание |
|---------|--------|------------|
| Отображение карты (QML) | ✅ | `MapView` из Qt Location |
| Pan / Zoom | ✅ | встроено в `MapView` (gesture) |
| Rotation (bearing) | ✅ | два пальца / `map.bearing` |
| Pitch / Tilt | ✅* | `map.tilt` — зависит от поддержки плагина |
| Offline-режим | ✅ | OSM растровые тайлы + локальный HTTP-сервер |
| Маркер «текущей позиции» | ✅ | фиктивные координаты, фиксированный оверлей |

> *Pitch работает, если плагин `maplibre` объявляет `TiltFeature`.
>  Если `map.tilt` не реагирует — см. раздел «Известные ограничения».

---

## Версии

| Компонент | Версия |
|-----------|--------|
| Qt | **6.5+** (протестировано на 6.6 / 6.7) |
| maplibre-native-qt | последний `main` (или тег `v3.x`) |
| CMake | 3.21+ |
| Python | 3.8+ (только для offline-скриптов) |
| ОС | Windows 10/11, Linux (Ubuntu 22.04+) |

Точный commit maplibre-native-qt записывается в `maplibre-native-qt/.git/HEAD`
после выполнения скрипта `scripts/build_maplibre_qt.sh`.

---

## Структура репозитория

```
PoC_Map/
├── CMakeLists.txt              — CMake проект
├── main.cpp                    — точка входа (Qt Quick + context props)
├── qml/
│   └── main.qml               — карта, toolbar, статус-бар
├── scripts/
│   ├── build_maplibre_qt.sh   — сборка maplibre-native-qt (Linux/macOS)
│   ├── build_maplibre_qt.ps1  — сборка maplibre-native-qt (Windows)
│   ├── download_tiles.py      — загрузка OSM-тайлов для offline
│   └── serve_local.py         — локальный HTTP-сервер тайлов
├── tiles/                     — сюда ложатся {z}/{x}/{y}.png + offline-style.json
│   └── .gitkeep               — директория в git (сами тайлы — в .gitignore)
└── README.md
```

---

## Быстрый старт

### 1. Предварительные требования

**Linux / Ubuntu:**
```bash
sudo apt-get install -y \
    cmake ninja-build git python3 \
    libgl1-mesa-dev libcurl4-openssl-dev libssl-dev \
    ccache pkg-config
# + Qt 6.5+ установить через Qt Installer (онлайн) или пакетный менеджер
```

**Windows:**
- Visual Studio 2019/2022 (workload «Desktop development with C++»)
- Qt 6.5+ MSVC build — [qt.io/download](https://www.qt.io/download)
- CMake 3.21+ (входит в VS или `winget install Kitware.CMake`)
- Git, Python 3.8+

---

### 2. Сборка maplibre-native-qt

> Это **одноразовый шаг**. Занимает 10–40 минут.
> Результат кешируется в `maplibre-install/`.

**Linux / macOS:**
```bash
bash scripts/build_maplibre_qt.sh
```

**Windows (PowerShell, запускать из Developer PowerShell for VS):**
```powershell
# Если Qt не в PATH, задай путь явно:
.\scripts\build_maplibre_qt.ps1 -QtDir "C:\Qt\6.6.0\msvc2019_64\lib\cmake\Qt6"
```

После завершения скрипт выведет путь `QMapLibre_DIR`.

---

### 3. Сборка PoC

```bash
cmake -B build -DQMapLibre_DIR="<path>/maplibre-install/lib/cmake/QMapLibre"
cmake --build build
# Windows:
cmake --build build --config Release
```

> **Проверка:** `cmake -B build && cmake --build build` должны завершиться без ошибок.

---

### 4. Запуск — Online-режим

```bash
# Linux
./build/poc_map

# Windows
.\build\Release\poc_map.exe
```

Карта загружается с `https://demotiles.maplibre.org/style.json` — публичный демо-стиль MapLibre, **API-ключ не нужен**.

---

### 5. Подготовка данных для Offline

#### 5a. Скачать OSM-тайлы

```bash
# По умолчанию: центр Варшавы, радиус 4 км, zoom 5-13
python3 scripts/download_tiles.py

# Кастомный регион (lat lon radius_km max_zoom):
python3 scripts/download_tiles.py 50.0647 19.9450 5 13   # Краков
python3 scripts/download_tiles.py 48.8566 2.3522 3 12    # Париж
```

Скрипт:
- Рассчитывает нужные тайлы, показывает количество и примерный размер
- Запрашивает подтверждение перед загрузкой
- Скачивает с `tile.openstreetmap.org` с ограничением 1 запрос/с
- Генерирует `tiles/offline-style.json` (MapLibre стиль с `localhost:8080`)
- Пропускает уже скачанные тайлы (повторный запуск безопасен)

**Примерный размер и время:**

| Регион | zoom 5-13 | Тайлов | Размер | Время |
|--------|-----------|--------|--------|-------|
| 4 km² (центр города) | 5-13 | ~1 400 | ~35 MB | ~25 мин |
| 10 km² | 5-13 | ~3 000 | ~75 MB | ~55 мин |

#### 5b. Запустить локальный тайл-сервер

```bash
# Из папки PoC_Map:
python3 scripts/serve_local.py
# Сервер стартует на http://localhost:8080
```

#### 5c. Запустить PoC в offline-режиме

```bash
# Отключи интернет (или просто убедись, что сервер запущен)
./build/poc_map --offline
```

Карта загрузится **без интернета** с локального сервера.

---

### 6. Кастомный стиль / тайлы (альтернативы)

Можно передать любой URL стиля как аргумент:

```bash
# Свой стиль (файл или URL)
./build/poc_map "file:///home/user/my-style.json"
./build/poc_map "http://localhost:8080/my-custom-style.json"
```

**Альтернативные источники тайлов (vector tiles):**

| Источник | Формат | Бесплатно |
|----------|--------|-----------|
| [openfreemap.org](https://openfreemap.org) | PMTiles / MBTiles (planet) | ✅ |
| [Geofabrik](https://download.geofabrik.de) + [tilemaker](https://github.com/systemed/tilemaker) | PBF → MBTiles | ✅ |
| [MapTiler](https://cloud.maptiler.com) | MBTiles (city extracts) | Freemium |

Для **vector tiles** нужен сервер, поддерживающий MBTiles (например [Martin](https://github.com/maplibre/martin) или [TileServer GL](https://github.com/maptiles/tileserver-gl)), и соответствующий `style.json` с OpenMapTiles-совместимыми слоями.

---

## Управление в приложении

| Действие | Управление |
|----------|------------|
| Pan | Mouse drag / Touch drag |
| Zoom in / out | Scroll wheel / Pinch / Кнопки `+` / `−` |
| Rotation | Two-finger rotate / Ctrl+drag (зависит от платформы) |
| Pitch toggle 0° / 45° | Кнопка **Tilt** в тулбаре |
| Reset bearing | Кнопка **⊕ N** |
| Reset view (Варшава) | Кнопка **⌂** |

---

## Как это работает (архитектура)

```
main.cpp
  → устанавливает QSGRendererInterface::OpenGL
  → читает --offline / style URL из аргументов
  → передаёт в QML через rootContext()->setContextProperty(...)

qml/main.qml
  → Plugin { name: "maplibre"; PluginParameter { name: "maplibre.map.styles" } }
  → MapView { map.plugin: mapPlugin; map.tilt; map.bearing }
  → Toolbar с кнопками управления
  → Status overlay (lat/lon/bearing/tilt в реальном времени)

Offline:
  tiles/{z}/{x}/{y}.png  ←  download_tiles.py (OSM)
  tiles/offline-style.json  ←  генерируется download_tiles.py
  serve_local.py  →  http://localhost:8080/  (Python SimpleHTTPRequestHandler + CORS)
  poc_map --offline  →  MapLibre обращается к localhost:8080
```

---

## Известные ограничения

1. **Pitch/Tilt**: `map.tilt` в Qt Location API работает, если плагин Qt Location объявляет поддержку `TiltFeature`. MapLibre Native поддерживает pitch, но конкретная реализация Qt Location plugin может не экспортировать эту возможность в свойство `map.tilt`. Если кнопка «Tilt» не меняет отображение — это ограничение Qt Location wrapper'а, а не самой MapLibre.
   **Workaround**: использовать `MapLibre` (standalone QML component из `QMapLibre::Quick` модуля) вместо `MapView`, там pitch доступен напрямую через C++ callback.

2. **Offline: только растровые тайлы**: PoC использует PNG тайлы с OSM, а не векторные. Для векторных тайлов (полноценный MapLibre стиль с кастомными слоями) нужен MBTiles + совместимый сервер + полный `style.json` с OpenMapTiles слоями и глифами.

3. **Сборка maplibre-native-qt**: первая сборка занимает 10-40 минут и требует ~3-5 GB свободного места (исходники + сборочные артефакты).

4. **Переключение Online/Offline в рантайме**: не реализовано — `Plugin.name` нельзя менять после инициализации. Нужен перезапуск или `Loader { active: false }` + `active: true`.

5. **Глифы и метки в offline**: текстовые метки требуют PBF шрифтов. В растровом PoC они не нужны. Для vector tiles нужно либо бандлить шрифты, либо держать их на локальном сервере.

---

## Место на диске

| Артефакт | Размер |
|----------|--------|
| maplibre-native-qt исходники + вендор | ~500 MB |
| maplibre-build/ (build tree) | ~1-3 GB |
| maplibre-install/ (установленные библиотеки) | ~50-150 MB |
| tiles/ (Варшава, r=4km, zoom 5-13) | ~35 MB |

---

## Ссылки

- [maplibre-native-qt на GitHub](https://github.com/maplibre/maplibre-native-qt)
- [Документация maplibre-native-qt](https://maplibre.org/maplibre-native-qt/docs/)
- [MapLibre Style Spec](https://maplibre.org/maplibre-style-spec/)
- [Qt Location — Map QML type](https://doc.qt.io/qt-6/qml-qtlocation-map.html)
- [OSM Tile Usage Policy](https://operations.osmfoundation.org/policies/tiles/)
