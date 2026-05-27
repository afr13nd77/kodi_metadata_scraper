# Kodi Metadata Scraper — Индекс проекта

**Версия**: 3.13.0 / 3.13.0 (movie / TV)
**Статус**: Полностью реализован — Movies + TV Shows (независимые аддоны)
**Обновлён**: 2026-05-27

---

## Технологический стек

| Компонент | Технология | Версия |
|---|---|---|
| Язык | Python | 3.8 (встроен в Kodi v20) |
| Платформа | Kodi | v20 Nexus / v21 Omega |
| API основной | Kinopoisk Unofficial | kinopoiskapiunofficial.tech |
| API дополнительный | OMDb | omdbapi.com (через VPN) |
| API дополнительный | TVMaze | api.tvmaze.com |
| Тип дополнения (фильмы) | xbmc.metadata.scraper.movies | metadata.ums |
| Тип дополнения (ТВ) | xbmc.metadata.scraper.tvshows | metadata.tvshows.ums |
| CI/CD | GitHub Actions | ubuntu-22.04, Python 3.8 |
| Линтер | ruff | target py38, rules E/F/W |

---

## Структура директорий

```
kodi_metadata_scraper/
├── .github/
│   └── workflows/
│       └── ci.yml                      # CI/CD pipeline (GitHub Actions)
├── .venv/                              # Python virtual environment (разработка/тесты)
├── docs/
│   ├── kodi-kinopoisk-scraper/         # Спецификация movie scraper
│   │   ├── requirements.md
│   │   ├── design.md
│   │   ├── algorithm.md
│   │   └── tasks.md
│   ├── tv-shows/                       # Спецификация TV shows scraper
│   │   ├── requirements.md
│   │   ├── design.md
│   │   └── tasks.md
│   ├── addon-split/                    # Спецификация разделения аддонов
│   │   ├── requirements.md
│   │   ├── design.md
│   │   └── tasks.md
│   └── tvmaze-integration/             # Спецификация TVMaze интеграции
│       ├── requirements.md
│       ├── design.md
│       └── tasks.md
├── shared/                             # Общие модули (единый источник правды)
│   ├── cache.py
│   ├── models.py
│   ├── http_client.py
│   ├── nfo_parser.py
│   ├── logger.py
│   ├── settings_manager.py
│   ├── kinopoisk_api.py
│   ├── omdb_client.py
│   ├── utils.py
│   └── nfo_writer.py                       # NFO-экспорт (XML-генерация, запись через xbmcvfs)
├── metadata.ums/                       # Movie scraper addon
│   ├── addon.xml
│   ├── python/
│   │   └── scraper.py
│   ├── resources/
│   │   └── settings.xml
│   └── tests/
├── metadata.tvshows.ums/               # TV scraper addon (независимый)
│   ├── addon.xml
│   ├── python/
│   │   └── tv_scraper.py
│   ├── resources/
│   │   └── settings.xml
│   └── tests/
├── ruff.toml                           # Конфигурация линтера ruff
├── build_zip.py                        # Сборка двух ZIP-пакетов
├── metadata.ums-3.13.0.zip             # ZIP для movie scraper
├── metadata.tvshows.ums-3.13.0.zip     # ZIP для TV shows scraper
└── index.md                            # Этот файл — индекс проекта
```

**Файлов**: 50+ (без .venv, __pycache__)

---

## Структура дополнений

С версии 3.7.0 оба дополнения (movie и TV) **полностью независимы**. Общие модули хранятся в `shared/` и копируются в каждый аддон при сборке:

### Movie Scraper (metadata.ums)

```
metadata.ums/
├── addon.xml                           # Манифест movie scraper
├── python/
│   └── scraper.py                      # Точка входа movie scraper
├── resources/
│   └── settings.xml                    # Собственные настройки
└── tests/
    ├── conftest.py
    ├── __init__.py
    ├── test_scraper.py
    ├── test_utils.py
    ├── test_models.py
    ├── test_http_client.py
    ├── test_kinopoisk_api.py
    ├── test_omdb_client.py
    ├── test_nfo_parser.py
    ├── test_cache.py
    ├── test_collections.py
    ├── test_fuzzy.py
    └── test_nfo_writer.py
```

### TV Scraper (metadata.tvshows.ums)

```
metadata.tvshows.ums/
├── addon.xml                           # Манифест TV scraper (независимый, БЕЗ зависимости от metadata.ums)
├── python/
│   └── tv_scraper.py                   # Точка входа TV scraper
├── resources/
│   └── settings.xml                    # Собственные настройки
└── tests/
    ├── conftest.py
    ├── __init__.py
    └── test_tv_scraper.py
```

### Общие модули (shared/)

Все модули, не специфичные для конкретного аддона, хранятся в `shared/`:

```
shared/
├── cache.py                            # Персистентный файловый кэш (FileCache, TTL 7 дней, xbmcvfs/stdlib fallback)
├── models.py                           # Датаклассы (MovieDetails, TVShowDetails, Season, Episode, Person, Artwork, Rating)
├── http_client.py                      # HTTP-слой (urllib, retry, rate limiting)
├── nfo_parser.py                       # Парсинг NFO-файлов (film + series URLs)
├── logger.py                           # Обёртка над xbmc.log (автодетект ADDON_ID)
├── settings_manager.py                 # Типизированный доступ к настройкам
├── kinopoisk_api.py                    # Клиент Kinopoisk API (search, get_details, get_staff, get_seasons, get_images, get_sequels)
├── omdb_client.py                      # Клиент OMDb API (get_ratings, get_episode_rating)
├── tvmaze_client.py                    # Клиент TVMaze API (описания эпизодов)
├── utils.py                            # Общие утилиты (get_params, clean_title, extract_ids, fuzzy_score, extract_franchise_name)
└── nfo_writer.py                       # NFO-экспорт (write_movie_nfo, write_tvshow_nfo, XML-генерация)
```

Каждый ZIP-архив содержит полный набор shared-модулей, делая оба аддона полностью самостоятельными.

---

## Ключевые архитектурные решения

### Два полностью независимых дополнения

Kodi требует **отдельные addon ID** для movie и TV scrapers:
- **metadata.ums** — scraper для фильмов (тип: `xbmc.metadata.scraper.movies`)
- **metadata.tvshows.ums** — scraper для ТВ-сериалов (тип: `xbmc.metadata.scraper.tvshows`)

С версии 3.6.0 оба аддона полностью независимы:
- Каждый имеет свои настройки (независимые section id в settings.xml)
- TV scraper НЕ зависит от movie scraper: `settings = SettingsManager()` (читает свой аддон)
- Логирование автоматически определяет ADDON_ID через `xbmcaddon.Addon().getAddonInfo('id')`
- Общий код хранится в `shared/` и копируется в каждый ZIP при сборке

**Следствие**: Пользователи могут устанавливать только нужный им аддон без зависимостей.

### Фильтрация типов контента

- **Movie scraper**: `type_filter=["FILM"]`
- **TV scraper**: `type_filter=["TV_SERIES", "MINI_SERIES", "TV_SHOW"]`

### Поток поиска ТВ-сериалов

1. **find** — поиск по названию, возврат первого результата
2. **getdetails** — получение информации + установка `episodelist_url` в `setEpisodeGuide()`
3. **getepisodelist** — парсинг сезонов из JSON по URL
4. **getepisodedetails** — данные по серии (название, описание, дата)
5. **getartwork** — постеры, фанарты, логотипы

### Кэширование

Двухуровневый кэш:
- **FileCache** (`shared/cache.py`): персистентный JSON-кэш с TTL 7 дней. Кэширует details, staff, images, sequels, seasons, OMDb. Пустые результаты не кэшируются. Настройка "Очистить кэш" в UI.
- **In-memory LRU** (TV scraper): thread-safe dict + threading.Lock, max 10 записей. Кэш сезонов внутри сессии.
- **3-уровневый кэш сезонов** (TV): memory → FileCache → API.

---

## Ключевые зависимости

- **Kinopoisk Unofficial API**: бесплатный, требует регистрации на kinopoiskapiunofficial.tech
  - Авторизация: заголовок `X-API-KEY`
  - Лимит: 20 req/sec
- **OMDb API**: опциональный (get_ratings, get_episode_rating), доступен только через VPN
  - Регистрация: omdbapi.com
  - Авторизация: параметр `apikey` в URL
- **TVMaze API**: бесплатный, без ключа, api.tvmaze.com
  - Описания эпизодов (на английском)
  - Требуется VPN в некоторых регионах
- **Kodi**: встроенный Python 3.8, модули xbmc, xbmcaddon, xbmcgui, xbmcplugin
- **Зависимости кода**: нет внешних pip-пакетов (используются только встроенные модули)

### Референсные реализации (только для изучения)

- [metadata.themoviedb.org.python](https://github.com/xbmc/metadata.themoviedb.org.python) — официальный Python-scraper TMDb от Team Kodi
- [afedchin/metadata.kinopoisk.ru](https://github.com/afedchin/metadata.kinopoisk.ru) — существующий Kodi scraper Кинопоиска (C++)

---

## Команды

| Команда | Описание |
|---|---|
| `cd metadata.ums && python -m pytest tests/ -v` | Запуск юнит-тестов (454 теста) |
| `cd metadata.tvshows.ums && python -m pytest tests/ -v` | Запуск юнит-тестов TV (116 тестов) |
| `python build_zip.py` | Сборка обоих ZIP-пакетов (metadata.ums и metadata.tvshows.ums) |
| `ruff check .` | Проверка стиля кода (ruff, target: Python 3.8) |

---

## Пайплайн спецификации

### Movie Scraper (kodi-kinopoisk-scraper)

| Фаза | Документ | Статус |
|---|---|---|
| 1. Требования | `docs/kodi-kinopoisk-scraper/requirements.md` | ✅ approved |
| 2. Технический дизайн | `docs/kodi-kinopoisk-scraper/design.md` | ✅ approved |
| 3. Алгоритм | `docs/kodi-kinopoisk-scraper/algorithm.md` | ✅ done |
| 4. Разбивка на задачи | `docs/kodi-kinopoisk-scraper/tasks.md` | ✅ done (12/12) |

### TV Shows Scraper (tv-shows)

| Фаза | Документ | Статус |
|---|---|---|
| 1. Требования | `docs/tv-shows/requirements.md` | ✅ approved |
| 2. Технический дизайн | `docs/tv-shows/design.md` | ✅ approved |
| 3. Разбивка на задачи | `docs/tv-shows/tasks.md` | ✅ done (17/17) |

### Разделение аддонов (addon-split)

| Фаза | Документ | Статус |
|---|---|---|
| 1. Требования | `docs/addon-split/requirements.md` | ✅ approved |
| 2. Технический дизайн | `docs/addon-split/design.md` | ✅ approved |
| 3. Разбивка на задачи | `docs/addon-split/tasks.md` | ✅ done (9/9) |

### TVMaze Integration (tvmaze-integration)

| Фаза | Документ | Статус |
|---|---|---|
| 1. Требования | `docs/tvmaze-integration/requirements.md` | ✅ approved |
| 2. Технический дизайн | `docs/tvmaze-integration/design.md` | ✅ approved |
| 3. Разбивка на задачи | `docs/tvmaze-integration/tasks.md` | ✅ done (9/9) |

### OMDb Ratings (omdb-ratings)

| Фаза | Документ | Статус |
|---|---|---|
| 1. Требования | `docs/omdb-ratings/requirements.md` | ✅ approved |
| 2. Технический дизайн | `docs/omdb-ratings/design.md` | ✅ approved |
| 3. Разбивка на задачи | `docs/omdb-ratings/tasks.md` | ✅ done (9/9) |

### MPAA / Возрастной рейтинг (mpaa-rating) — v3.9.0

| Фаза | Документ | Статус |
|---|---|---|
| 1. Требования | `docs/mpaa-rating/requirements.md` | ✅ approved |
| 2. Технический дизайн | — | ⏳ pending |
| 3. Разбивка на задачи | — | ⏳ pending |

### Автовыбор совпадения (auto-select) — v3.9.0

| Фаза | Документ | Статус |
|---|---|---|
| 1. Требования | `docs/auto-select/requirements.md` | ✅ approved |
| 2. Технический дизайн | — | ⏳ pending |
| 3. Разбивка на задачи | — | ⏳ pending |

### Транслитерация фолбэк (transliteration-fallback) — v3.9.0

| Фаза | Документ | Статус |
|---|---|---|
| 1. Требования | `docs/transliteration-fallback/requirements.md` | ✅ approved |
| 2. Технический дизайн | — | ⏳ pending |
| 3. Разбивка на задачи | — | ⏳ pending |

### Fuzzy-matching (fuzzy-matching) — v3.9.0

| Фаза | Документ | Статус |
|---|---|---|
| 1. Требования | `docs/fuzzy-matching/requirements.md` | ✅ approved |
| 2. Технический дизайн | `docs/fuzzy-matching/design.md` | ✅ approved |
| 3. Разбивка на задачи | `docs/fuzzy-matching/tasks.md` | ✅ done (5/5) |

### Двойной поиск (dual-title-search) — v3.9.0

| Фаза | Документ | Статус |
|---|---|---|
| 1. Требования | `docs/dual-title-search/requirements.md` | ✅ approved |
| 2. Технический дизайн | `docs/dual-title-search/design.md` | ✅ approved |
| 3. Разбивка на задачи | `docs/dual-title-search/tasks.md` | ✅ done |

### Коллекции и саги (collections-sagas) — v3.9.0

| Фаза | Документ | Статус |
|---|---|---|
| 1. Требования | `docs/collections-sagas/requirements.md` | ✅ approved |
| 2. Технический дизайн | `docs/collections-sagas/design.md` | ✅ approved |
| 3. Разбивка на задачи | `docs/collections-sagas/tasks.md` | ✅ done (4/4) |

### Теги наград (award-tags) — v3.10.0 / v3.11.0

| Фаза | Документ | Статус |
|---|---|---|
| 1. Требования | `docs/award-tags/requirements.md` | ✅ approved |
| 2. Технический дизайн | `docs/award-tags/design.md` | ✅ approved |
| 3. Разбивка на задачи | `docs/award-tags/tasks.md` | ✅ done |

### Нормализация жанров (genre-normalization) — v3.10.0 / v3.11.0

| Фаза | Документ | Статус |
|---|---|---|
| 1. Требования | `docs/genre-normalization/requirements.md` | ✅ approved |
| 2. Технический дизайн | `docs/genre-normalization/design.md` | ✅ approved |
| 3. Разбивка на задачи | `docs/genre-normalization/tasks.md` | ✅ done |

### Персистентный кэш (persistent-cache) — v3.10.0 / v3.11.0

| Фаза | Документ | Статус |
|---|---|---|
| 1. Требования | `docs/persistent-cache/requirements.md` | ✅ approved |
| 2. Технический дизайн | `docs/persistent-cache/design.md` | ✅ approved |
| 3. Разбивка на задачи | `docs/persistent-cache/tasks.md` | ✅ done |

### Умный парсинг и детекция контента (smart-parsing) — v3.12.0

| Фаза | Документ | Статус |
|---|---|---|
| 1. Требования | `docs/smart-parsing/requirements.md` | ✅ approved |
| 2. Технический дизайн | `docs/smart-parsing/design.md` | ✅ approved |
| 3. Разбивка на задачи | `docs/smart-parsing/tasks.md` | ✅ done (12/12) |

### NFO-экспорт (nfo-export) — v3.13.0

| Фаза | Документ | Статус |
|---|---|---|
| 1. Требования | `docs/nfo-export/requirements.md` | ✅ approved |
| 2. Технический дизайн | `docs/nfo-export/design.md` | ✅ approved |
| 3. Разбивка на задачи | `docs/nfo-export/tasks.md` | ✅ done (8/8) |

### CI/CD Pipeline (ci-cd) — BL-35

| Фаза | Документ | Статус |
|---|---|---|
| 1. Требования | `docs/ci-cd/requirements.md` | ✅ done |
| 2. Технический дизайн | `docs/ci-cd/design.md` | ✅ done |
| 3. Разбивка на задачи | `docs/ci-cd/tasks.md` | ✅ done |

---

## Текущая версия

**Movie 3.13.0 / TV 3.13.0** — NFO-экспорт (BL-25): автоматическая запись .nfo рядом с видео, настройки enable/overwrite. + Умный парсинг имён файлов (BL-15), детекция аниме (BL-16), multi-part фильмы (BL-17), мини-сериалы (BL-18), теги наград (BL-10), нормализация жанров (BL-11), персистентный кэш (BL-20). 570 тестов (454 movie + 116 TV).

---

## Логирование

Все функции имеют логирование успеха и ошибки. Логирование происходит:
- На уровне каждого HTTP-запроса (метод, URL, статус)
- На уровне каждого вызова API (параметры, результат)
- На уровне обработки результатов (валидация, трансформация)
- На уровне обработки ошибок (исключение, трассировка стека)

API keys санитизируются перед логированием через `logger.py`.

---

## Статус реализации

✅ **Movie Scraper (metadata.ums)**
- поиск фильмов по названию
- получение полной информации (постер, описание, рейтинг, жанры, страны, год, продолжительность, актёры, режиссёр)
- поддержка NFO-файлов для ускорения поиска
- персистентный файловый кэш с TTL и настройкой очистки
- теги наград (Оскар, Эмми, BAFTA, Канны, Золотой глобус)
- нормализация жанров (рус→англ)
- NFO-экспорт (автоматическая запись .nfo рядом с видео)
- 454 юнит-теста

✅ **TV Scraper (metadata.tvshows.ums)**
- поиск сериалов по названию
- получение информации о сериале
- получение списка сезонов
- получение списка серий по сезону
- получение полной информации по серии (название, описание, дата, рейтинг)
- поддержка NFO-файлов
- описания серий из TVMaze (опционально)
- теги наград, нормализация жанров
- персистентный кэш (3-уровневый для сезонов)
- fallback при legacy episodeguide
- NFO-экспорт (автоматическая запись tvshow.nfo)
- 116 юнит-тестов (всего 570)

✅ **OMDb интеграция**
- получение рейтингов фильмов (IMDB Rating)
- получение рейтингов серий (IMDB Rating per episode)
- сохранение рейтингов RT/MC в рейтинговую базу Kodi (setRatings)

✅ **Общие компоненты**
- HTTP клиент с retry-логикой и rate limiting
- парсинг NFO-файлов (film + series)
- менеджер настроек с типизацией
- логирование с санитизацией ключей API
- модели данных (dataclasses)
- NFO-экспорт (`nfo_writer.py`, XML-генерация через ElementTree)

---

## Установка в Kodi

**С версии 3.7.0 аддоны полностью независимы — порядок установки не важен.**

1. Kodi → Settings → Add-ons → Install from zip file
2. Установить `metadata.ums-3.13.0.zip` (movie scraper) — ОПЦИОНАЛЬНО
   или `metadata.tvshows.ums-3.13.0.zip` (TV scraper) — ОПЦИОНАЛЬНО
   или оба архива
3. Выбрать scraper в Settings → Media → Movies / TV Shows → Metadata providers

Каждый аддон имеет свои настройки (API ключи, опции) — они независимы.
