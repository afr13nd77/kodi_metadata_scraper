[![CI](https://github.com/afr13nd77/kodi_metadata_scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/afr13nd77/kodi_metadata_scraper/actions/workflows/ci.yml)
[![Kodi version](https://img.shields.io/badge/kodi%20versions-20--21-blue)](https://kodi.tv/)
[![GitHub release](https://img.shields.io/github/release/afr13nd77/kodi_metadata_scraper.svg)](https://github.com/afr13nd77/kodi_metadata_scraper/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[English version](readme_en.md)

# Ultimate Movie Scraper (UMS) для Kodi

**Версия:** 3.24.0  
**Платформа:** Kodi v20 Nexus / v21 Omega  
**Язык:** Python 3.8  

---

## Описание

Два полностью независимых Python-аддона для Kodi, предназначенных для скрапинга метаданных фильмов и сериалов. Обеспечивают русскоязычные метаданные: названия, описания, актёрский состав с русскими именами и фотографиями. Поддерживают рейтинги из нескольких источников: Кинопоиск, IMDB, Rotten Tomatoes, Metacritic. Интеграция с OMDb опциональна (в некоторых регионах требуется VPN).

---

## Возможности

### metadata.ums -- Movie Scraper

- Поиск фильмов по русскому и английскому названию
- Полные метаданные: название, год, описание, жанры, страны, студии, продолжительность, MPAA
- Актёры и съёмочная группа с русскими именами и фотографиями
- Рейтинги: Кинопоиск, IMDB, Rotten Tomatoes, Metacritic (в рейтинговой базе Kodi + опционально в описании)
- Поддержка NFO-файлов
- Постеры и фанарты
- Fuzzy-matching при поиске с 3-уровневой сортировкой (год, совпадение, рейтинг)
- Двойной поиск: русское + оригинальное название
- Коллекции и саги (наборы фильмов)
- Теги наград (Оскар, Эмми, BAFTA, Канны, Золотой глобус)
- Нормализация жанров (рус→англ)
- Персистентный файловый кэш с TTL 7 дней
- Автовыбор при точном совпадении по названию + году
- Транслитерация латиница→кириллица (fallback)
- NFO-экспорт: автоматическая запись .nfo-файлов рядом с видео
- Детекция дублей Kinopoisk ID с уведомлением в Kodi
- Graceful degradation: работа при недоступном API через stale-кэш и NFO-файлы
- YouTube-трейлеры из Kinopoisk API с кэшированием и graceful degradation
- Wikidata fallback: автоматическое получение IMDB ID через Wikidata SPARQL, когда Кинопоиск не знает его (без API-ключа)
- Автоочистка технических тегов из имён файлов (BDRip, x265, 1080p, HDR, DTS, IMAX и др.)
- Оригинальный язык фильма (setOriginalLanguage, маппинг стран → ISO 639-1)
- FanArt.tv артворк: clearlogo, clearart, banner, landscape, discart (опционально, требуется API-ключ)
- Язык имён актёров и съёмочной группы (русский / английский)
- Автоочистка коллекционных префиксов из имён файлов (MCU150-, SW03-, DC021-)

### metadata.tvshows.ums -- TV Show Scraper

- Поиск сериалов (типы: TV_SERIES, MINI_SERIES, TV_SHOW)
- Полные метаданные сериала с episode guide
- Информация о сезонах и эпизодах
- Описания серий из TVMaze (опционально, на английском, требуется VPN)
- Сезонные постеры и названия сезонов из TVMaze
- Автоматическое получение IMDB ID через TVMaze при отсутствии в Кинопоиске
- Рейтинги эпизодов: Кинопоиск + IMDB votes из OMDb
- Режиссёры и сценаристы эпизодов из TVMaze (опционально, при use_tvmaze=true)
- Рейтинги сериала: Кинопоиск, IMDB, Rotten Tomatoes, Metacritic (в рейтинговой базе Kodi)
- Артворки: постеры и кадры
- Поддержка NFO-файлов
- Умный парсинг имён файлов (S01E02, 1x02, «1 сезон 2 серия»)
- Детекция аниме-сериалов (абсолютная нумерация)
- Поддержка мини-сериалов
- Обработка многосерийных фильмов (Часть/Part/Vol)
- Теги наград, нормализация жанров, персистентный кэш
- Fallback при legacy episodeguide
- NFO-экспорт: автоматическая запись tvshow.nfo в директорию сериала
- Детекция дублей Kinopoisk ID
- Graceful degradation: работа при недоступном API через stale-кэш и NFO-файлы
- YouTube-трейлеры из Kinopoisk API
- Wikidata fallback для IMDB ID (аналогично movie scraper)
- Статус сериала (Returning Series / Ended / и др.) из TVMaze и KP API
- Превью эпизодов из TVMaze (thumbnails)
- Оригинальный язык сериала (setOriginalLanguage)
- FanArt.tv артворк сериалов и сезонов: clearlogo, clearart, banner, landscape, characterart (опционально)
- Язык имён актёров и съёмочной группы (русский / английский)
- Совместимость с TMDb/TVDB: автоматический резолв KP ID при миграции с другого скрапера

### Общее

- Аддоны полностью независимы -- устанавливайте только то, что нужно
- Каждый аддон имеет собственные настройки (API-ключи, параметры)
- Поддержка кодировки cp1251 для кириллицы на Windows
- Rate limiting и retry-логика для API-запросов
- Санитизация API-ключей в логах
- CI/CD: GitHub Actions (ruff lint + pytest + сборка ZIP + авто-релиз по тегу v*)

---

## Установка

### Требования

- Kodi v20 Nexus или v21 Omega

### Шаги

1. Скачайте ZIP-архивы из раздела релизов
2. В Kodi: **Settings** -> **Add-ons** -> **Install from zip file**
3. Установите нужные аддоны:
   - `metadata.ums-3.24.0.zip` -- scraper фильмов
   - `metadata.tvshows.ums-3.24.0.zip` -- scraper сериалов
   - Можно установить оба или только один
4. Откройте настройки установленного аддона и укажите API-ключ Кинопоиска

### Получение API-ключей

- **kinopoiskapiunofficial API** (обязательно): зарегистрируйтесь на `kinopoiskapiunofficial.tech` и получите бесплатный ключ
- **OMDb API** (опционально): зарегистрируйтесь на `omdbapi.com` для получения рейтингов IMDB/RT/Metacritic

---

## Настройки

| Параметр | Описание |
|---|---|
| `kinopoisk_api_key` | API-ключ с kinopoiskapiunofficial.tech (обязательно) |
| `omdb_api_key` | API-ключ OMDb для рейтингов IMDB/RT (опционально) |
| `fanart_api_key` | API-ключ FanArt.tv для дополнительного артворка (опционально) |
| `preferred_rating` | Источник рейтинга по умолчанию: Кинопоиск или IMDB |
| `fetch_actor_photos` | Загружать фотографии актёров с Кинопоиска |
| `show_ratings_in_plot` | Добавлять рейтинги в описание фильма/сериала |
| `use_tvmaze` | Загружать описания серий из TVMaze (только TV scraper, по умолчанию выкл) |
| `use_season_art` | Загружать постеры и названия сезонов из TVMaze (при включённом TVMaze, по умолчанию вкл) |
| `use_fanart` | Загружать артворк из FanArt.tv (по умолчанию выкл) |
| `genre_language` | Язык жанров: русский или английский (по умолчанию: русский) |
| `actor_name_language` | Язык имён актёров: русский или английский (по умолчанию: русский) |
| `auto_select_exact_match` | Автовыбор при точном совпадении по названию и году |
| `enable_collections` | Определять коллекции и саги (по умолчанию вкл) |
| `enable_dual_search` | Двойной поиск по русскому и оригинальному названию (по умолчанию вкл) |
| `enable_award_tags` | Теги наград (Оскар, Эмми, BAFTA и др.) (по умолчанию вкл) |
| `enable_nfo_export` | Экспорт .nfo-файлов рядом с видео после скрапинга (по умолчанию выкл) |
| `nfo_overwrite` | Перезаписывать существующие .nfo-файлы (видно только при включённом экспорте) |
| `enable_duplicate_detection` | Предупреждать при назначении одного Kinopoisk ID разным файлам (по умолчанию вкл) |
| `enable_trailers` | Загружать YouTube-трейлеры из Кинопоиска (по умолчанию вкл) |
| `use_wikidata_fallback` | Получать IMDB ID из Wikidata, когда Кинопоиск не знает его (по умолчанию вкл) |
| `debug_logging` | Включить подробное логирование |
| `clear_cache` | Очистить файловый кэш (в разделе "Расширенные") |

Каждый аддон (movie и TV) имеет свой независимый набор настроек.

---

## Структура проекта

```
shared/                  — общие модули (копируются в каждый аддон при сборке)
metadata.ums/            — movie scraper addon
metadata.tvshows.ums/    — TV show scraper addon
build_zip.py             — сборка обоих ZIP-пакетов
```

Общие модули (`shared/`) включают: HTTP-клиент с retry-логикой, клиент Kinopoisk API, клиент OMDb, клиент TVMaze, клиент Wikidata SPARQL, парсер NFO, NFO-экспорт (генерация XML), менеджер настроек, систему логирования, модели данных, персистентный файловый кэш и трекер дубликатов.

---

## Разработка

### Подготовка окружения

```
python -m venv .venv
.venv\Scripts\activate
pip install pytest
```

### Запуск тестов

```bash
# Тесты movie scraper
cd metadata.ums && python -m pytest tests/ -v

# Тесты TV scraper
cd metadata.tvshows.ums && python -m pytest tests/ -v

# Тесты shared-модулей
cd shared && python -m pytest tests/ -v
```

Всего: **917 тестов** (659 movie + 224 TV + 34 shared).

### Линтинг

```bash
ruff check .
```

### Сборка ZIP-пакетов

```
python build_zip.py
```

Результат: `metadata.ums-3.24.0.zip` и `metadata.tvshows.ums-3.24.0.zip` в корне проекта.

---

## Источники данных

| Источник | Назначение | Статус |
|---|---|---|
| Kinopoisk Unofficial API (`kinopoiskapiunofficial.tech`) | Метаданные, актёры, постеры, сезоны, эпизоды | Основной, обязательный |
| OMDb API (`omdbapi.com`) | Рейтинги IMDB, Rotten Tomatoes, Metacritic (в рейтинговой базе Kodi) | Дополнительный, опциональный |
| TVMaze API (`api.tvmaze.com`) | Описания эпизодов, сезонные постеры, разрешение IMDB ID (TV scraper) | Дополнительный, опциональный |
| Wikidata SPARQL (`query.wikidata.org`) | Fallback для IMDB ID по Kinopoisk ID | Дополнительный, без API-ключа |
| FanArt.tv (`fanart.tv`) | Дополнительный артворк: clearlogo, clearart, banner, landscape, discart | Дополнительный, опциональный |

TMDb **не используется**.

---

## Лицензия

Этот проект лицензирован под [MIT License](LICENSE.txt).
