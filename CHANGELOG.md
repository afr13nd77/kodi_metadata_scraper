# Changelog — Ultimate Movie Scraper (metadata.ums)

## v3.15.0 (08.06.2026) — metadata.ums + metadata.tvshows.ums

### YouTube-трейлеры (BL-09)

- Получение YouTube-трейлеров из Kinopoisk API (`/v2.2/films/{id}/videos`)
- Приоритетный выбор: видео с "трейлер"/"trailer" в названии, fallback на первое YouTube-видео
- Конвертация в Kodi URL: `plugin://plugin.video.youtube/?action=play_video&videoid={ID}`
- `infotag.setTrailer()` в обоих скраперах (movie + TV)
- Кэширование сырого ответа API (`kp_videos_{kp_id}`, TTL 7 дней)
- Graceful degradation: stale cache fallback при ошибке API, degraded mode (5с, 0 retries)
- NFO roundtrip: `<trailer>` пишется в nfo_writer, читается в nfo_parser
- Настройка "Загружать трейлеры" (по умолчанию вкл., 1 доп. API-запрос на фильм/сериал)

### Тесты

- 28 новых тестов: trailer parsing (12), NFO trailer (6), scraper trailer (6), TV scraper trailer (4)
- Всего 641 тестов (515 movie + 126 TV)

## v3.14.2 (08.06.2026) — metadata.ums + metadata.tvshows.ums

- Новые контрастные fanart 1920x1080 для обоих аддонов (тёмно-синий movie, индиго TV)
- Исправлено отображение иконок и fanart в Kodi: добавлена секция `<assets>` в addon.xml

## v3.14.0 (08.06.2026) — metadata.ums + metadata.tvshows.ums

### Graceful Degradation (BL-24)

- Fallback-цепочка при недоступности API Кинопоиска: свежий кэш → API → stale кэш → NFO → hard fail
- Serve-stale-on-error: stale-данные из кэша отдаются при отказе API (cache.py: get_stale)
- Полный парсинг NFO XML: parse_full_movie / parse_full_tvshow (nfo_parser.py)
- Degraded mode: сокращённый таймаут 5с, 0 retries при повторных ошибках API (http_client.py: get_json_degraded)
- Degraded-варианты API-запросов: fetch_details_raw_degraded, fetch_staff_raw_degraded (kinopoisk_api.py)
- Уведомления пользователю при fallback: «Данные из кэша (устаревшие)», «Данные из NFO-файла», «Кинопоиск недоступен»
- Уведомления показываются не более 1 раза за сессию скрейпера
- Быстрый отказ: при первом API-fail последующие вызовы используют degraded mode
- Обратная совместимость: при доступном API поведение идентично 3.13.0

### CI/CD Pipeline (BL-35)

- GitHub Actions для автоматической проверки кода
  - Workflow: ruff lint → pytest (movie + TV параллельно) → build ZIP
  - Авто-релиз: push тега `v*` создаёт GitHub Release с ZIP-архивами
  - Конфигурация ruff: target Python 3.8, line-length 120, правила E/F/W
  - Runner: ubuntu-22.04 (Python 3.8 pre-built)
  - CI badge в README.md
  - Исправлена 21 ошибка линтера в существующем коде

### Детекция дублей Kinopoisk ID (BL-26)

- Новый модуль `shared/duplicate_tracker.py`: персистентный трекинг kp_id → file_path (JSON)
  - Toast notification (xbmcgui, WARNING, 7 сек) при обнаружении дубля
  - Повторный скрапинг того же файла не считается дублем
  - Graceful degradation: ошибки трекинга не блокируют скрапинг
  - Настройка «Обнаружение дубликатов» (по умолчанию вкл.)
  - «Очистить кэш» также очищает трекинг дубликатов
  - Аддоны ведут независимые карты (movie и TV не пересекаются)

### Тесты

- 31 новый тест: cache get_stale (5), nfo_parser parse_full (12), scraper fallback (8), tv_scraper fallback (6)
- 12 тестов DuplicateTracker
- Всего 613 тестов (491 movie + 122 TV)

## v3.13.0 (27.05.2026) — metadata.ums + metadata.tvshows.ums
- NFO-экспорт (BL-25): автоматическая запись .nfo-файлов рядом с видеофайлами после скрапинга
  - Movie: создаёт `<имя_файла>.nfo` рядом с видео (XML Kodi-формат)
  - TV: создаёт `tvshow.nfo` в корневой директории сериала
  - Новый модуль `shared/nfo_writer.py`: генерация XML через ElementTree, запись через xbmcvfs
  - Настройки: «Экспорт NFO» (по умолчанию выкл.), «Перезаписывать NFO» (условная видимость)
  - Полная совместимость с Kodi NFO reader и nfo_parser.py (AC-20)
- Исправлен парсер NFO: regex для `<uniqueid>` теперь поддерживает дополнительные атрибуты (kinopoisk + imdb)
- 36 новых тестов (23 nfo_writer + 13 прочие), всего 570 тестов (454 movie + 116 TV)

## v3.12.0 (24.05.2026) — metadata.ums + metadata.tvshows.ums
- Умный парсинг имён файлов (BL-15): поддержка S01E02, 1x02, кириллических С01Э03, «1 сезон 2 серия» — автоматическое удаление из названия при поиске
- Детекция аниме-сериалов (BL-16): абсолютная нумерация с ведущим нулём (001, 042, 0842) распознаётся как номер эпизода
- Обработка многосерийных фильмов (BL-17): «Часть/Part/Vol/Том» + арабские/римские/русские числительные → два поисковых кандидата (полное + базовое название)
- Поддержка мини-сериалов (BL-18): флаг is_miniseries из KP API type="MINI_SERIES", тег «Мини-сериал»/«Mini-Series» в Kodi
- Исправлена перезапись тегов: details.tags = award_tags → details.tags.extend(award_tags) в обоих scraper-ах
- 25 новых тестов (21 utils + 4 tv_scraper), всего 534+ тестов

## v3.11.4 (24.05.2026) — metadata.tvshows.ums
- Настройка "Очистить кэш" в разделе "Расширенные": очистка FileCache по запросу пользователя

## v3.10.1 (24.05.2026) — metadata.ums
- Настройка "Очистить кэш" в разделе "Расширенные": очистка FileCache по запросу пользователя

## v3.11.3 (24.05.2026) — metadata.tvshows.ums
- Оптимизация: пустые сезоны не кэшируются в FileCache, стейл-кэш удаляется
- Оптимизация: тип kp_id (FILM/TV_SERIES) кэшируется для fallback — без повторных API-запросов

## v3.11.2 (24.05.2026) — metadata.tvshows.ums
- Fallback при 0 сезонов: переиск по title_original, IMDB lookup, проверка типа (FILM vs TV_SERIES)
- Уведомление Kodi при legacy episodeguide с неверным kp_id (тип FILM вместо TV_SERIES)
- Исправлен дубль вызова `_find_episode` в `_handle_getepisodedetails`

## v3.11.1 (24.05.2026) — metadata.tvshows.ums
- Исправлен краш `_handle_getepisodelist`/`_handle_getepisodedetails` при legacy episodeguide: `json.loads("60574")` возвращал `int` вместо `dict`, вызывая `'int' object has no attribute 'get'`

## v3.11.0 (24.05.2026) — metadata.tvshows.ums
- Теги наград (BL-10): парсинг OMDb Awards, теги Оскар/Глобус/Эмми/BAFTA/Канны, `setTags()` в Kodi
- Нормализация жанров (BL-11): маппинг 31 жанра KP рус→англ, настройка "Язык жанров"
- Персистентный кэш (BL-20): `FileCache` с TTL 7 дней, кэш details/staff/seasons/OMDb, 3-уровневый кэш для seasons (memory→file→API)
- Рефакторинг KinopoiskClient: split fetch_raw/parse для кэширования сырого JSON
- Рефакторинг OmdbClient: split fetch_ratings_raw/parse_ratings

## v3.10.0 (24.05.2026) — metadata.ums
- Теги наград (BL-10): парсинг OMDb Awards, теги Оскар/Глобус/Эмми/BAFTA/Канны, `setTags()` в Kodi
- Нормализация жанров (BL-11): маппинг 31 жанра KP рус→англ, настройка "Язык жанров"
- Персистентный кэш (BL-20): `FileCache` с TTL 7 дней, кэш details/staff/images/sequels/OMDb
- Рефакторинг KinopoiskClient: split fetch_raw/parse для кэширования сырого JSON
- Рефакторинг OmdbClient: split fetch_ratings_raw/parse_ratings

## v3.10.1 (24.05.2026) — metadata.tvshows.ums
- Исправлен двойной вызов dual search: `_perform_dual_search()` вызывался дважды при найденных результатах (лишний API-запрос)

## v3.9.1 (24.05.2026) — metadata.ums
- Исправлен двойной вызов dual search: `_perform_dual_search()` вызывался дважды при найденных результатах (лишний API-запрос)

## v3.10.0 (24.05.2026) — metadata.tvshows.ums
- Двойной поиск: дополнительный поиск по альтернативному названию для TV-сериалов
- type_filter для TV (TV_SERIES, MINI_SERIES, TV_SHOW) сохраняется при втором поиске
- Настройка "Двойной поиск (рус + ориг)" — включение/выключение (по умолчанию вкл.)
- Unit-тесты: 11 интеграционных тестов _perform_dual_search() для TV scraper

## v3.9.0 (24.05.2026) — metadata.ums
- Fuzzy-matching: 3-уровневая сортировка результатов (совпадение года, fuzzy score, рейтинг)
- Новые утилиты `normalize_for_matching()`, `fuzzy_score()`, `best_fuzzy_score()` в utils.py
- Предупреждение в логе при низком качестве совпадений (все scores ниже порога 0.6)
- Двойной поиск: дополнительный поиск по альтернативному названию (русскому или оригинальному)
- Новые утилиты `extract_alt_title()`, `deduplicate_results()`, `_has_cyrillic()` в utils.py
- Дедупликация результатов по kinopoisk_id при объединении двух поисков
- Настройка "Двойной поиск (рус + ориг)" — включение/выключение (по умолчанию вкл.)

## v3.8.1 (22.05.2026)
- Коллекции и саги: автоматическая группировка фильмов-франшиз в Kodi movie sets
- Новый API-метод `get_sequels()` — запрос связанных фильмов через Kinopoisk API v2.1
- Алгоритм определения франшизы: LCP заголовков + fallback по текущему названию
- Настройка "Определять коллекции" — включение/выключение в settings.xml
- Приоритет русских названий (nameRu), fallback на nameOriginal
- Ремейки (relationType=REMAKE) исключаются из расчёта коллекции
- Graceful degradation: ошибки API sequels не блокируют остальные метаданные

## v3.0.0 (21.05.2026)
- Поддержка сериалов: новый extension point `xbmc.metadata.scraper.tvshows`
- Новый модуль `tv_scraper.py` — полный цикл скрапинга сериалов (поиск, детали, эпизоды, NFO)
- Поиск сериалов через Kinopoisk API с фильтрацией по типу (TV_SERIES, MINI_SERIES, TV_SHOW)
- Episodeguide: автоматическое получение данных сезонов и эпизодов через `/api/v2.2/films/{id}/seasons`
- In-memory LRU кэш данных сезонов (10 записей, thread-safe) — один API-запрос на сериал
- Рейтинги эпизодов из OMDb API (опционально, graceful failure)
- NFO парсинг: поддержка URL `kinopoisk.ru/series/NNN`
- Рефакторинг: общие утилиты вынесены в `utils.py` (get_params, clean_title, extract IDs)
- Фильтрация типов: movie scraper теперь возвращает только фильмы (type_filter=FILM)
- Обновлены summary и description аддона — "фильмы и сериалы"

## v2.1.2 (21.05.2026)
- Диагностические логи (`repr`, `raw argv2`) понижены до `LOGDEBUG`
- Невозможность декодирования значения — `LOGWARNING`
- Продовый билд: убран лишний вывод из INFO-логов

## v2.1.1 (21.05.2026)
- Рейтинг Кинопоиска добавлен в описание фильма (plot)
- Все рейтинги отображаются в одной строке: `KP: 8.5 | IMDb: 8.1 | RT: 90% | MC: 84`
- Рейтинг KP виден всегда, независимо от настройки preferred rating
- Если OMDb ключ не указан — показываются KP и IMDb из Kinopoisk API

## v2.1.0 (21.05.2026)
- Интеграция с OMDb API для получения рейтингов Rotten Tomatoes и Metacritic
- Новый модуль `omdb_client.py` — таймаут 3 сек, 1 retry, все ошибки подавляются
- Рейтинги дописываются в описание фильма (plot)
- Новые настройки: API-ключ OMDb (опционально), переключатель "Показывать рейтинги в описании"
- OMDb сбой не влияет на основные данные Kinopoisk

## v2.0.3 (21.05.2026)
- Исправлена кодировка кириллицы: Kodi на Windows передаёт title в cp1251 percent-encoding
- `parse_qsl` теперь парсит через `encoding='latin-1'` (passthrough байтов)
- `_decode_value()` определяет кодировку: UTF-8 → cp1251 → fallback
- Добавлены диагностические логи для отладки encoding

## v2.0.2 (21.05.2026)
- Диагностический билд: все логи encoding повышены до LOGINFO
- Добавлен `repr()` в логи для анализа реальных байтов

## v2.0.1 (21.05.2026)
- Попытка исправить кодировку через mojibake detection (`_fix_encoding`)
- Не решило проблему — корневая причина была в `parse_qsl` encoding

## v2.0.0 (21.05.2026)
- Переименование: `metadata.kinopoisk` → `metadata.ums` (Ultimate Movie Scraper)
- Addon ID: `metadata.ums`, display name: "Ultimate Movie Scraper"
- Мажорная версия — Kodi воспринимает как новый аддон

## v1.0.5 (20.05.2026)
- `_clean_title()` обрабатывает точечные имена файлов (`The.Chronicles.of.Riddick.2004.HDTVRip...`)
- Замена точек и подчёркиваний на пробелы
- Обнаружение года без скобок (19xx/20xx) с отсечением мусора после года

## v1.0.4 (20.05.2026)
- `_clean_title()` — очистка грязных названий от Kodi: `[Open Matte]`, `(2003)`, разделение по `/`
- Поддержка нескольких кандидатов: `Люди Икс 2 / X-Men 2` → поиск каждого по очереди
- Извлечение года из скобок для fallback-поиска

## v1.0.3 (20.05.2026)
- Год выпуска отображается в списке результатов поиска: `Название (2003)`

## v1.0.2 (20.05.2026)
- Исправлен `setRuntime()` → `setDuration(seconds)` (Kodi v20 API)
- Данные фильма корректно передаются в профиль

## v1.0.1 (20.05.2026)
- Python 3.8 совместимость: `from __future__ import annotations` во всех файлах
- Исправлен `get_params()`: `sys.argv[1]` = handle (int), `sys.argv[2]` = query string
- URL в `addDirectoryItem` = `json.dumps(uniqueids)`, не `urlencode()`
- `uniqueIDs` (camelCase) от Kodi
- Исправлен формат `settings.xml`: `version="1"`, section ID = addon ID

## v1.0.0 (20.05.2026)
- Первый релиз
- Поиск фильмов через Kinopoisk Unofficial API
- Получение метаданных: название, описание, год, жанры, страны, студии
- Рейтинги Кинопоиска и IMDB
- Актёры, режиссёры, сценаристы с русскими именами
- Постеры и фанарт
- Парсинг NFO файлов (kinopoisk.ru и imdb.com ссылки)
- Rate limiting (token bucket) для API
- Санитизация API-ключей в логах
