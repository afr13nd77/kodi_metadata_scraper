# Бэклог — Ultimate Movie Scraper

**Версия проекта:** 3.17.0 / 3.17.0 (movie / TV)
**Обновлён:** 10.06.2026

---

## 1. Качество поиска

### 1.1 Идеи

| # | Название | Файл / модуль | Описание |
|---|:---|:---|:---|
| BL-37 | Ручной ввод KP ID | `scraper.py`, `tv_scraper.py`, `nfo_parser.py` | Пользователь указывает KP ID вручную через NFO (`<uniqueid type="kinopoisk">`) или настройку. Критично для редкого контента, где fuzzy-matching ошибается. |
| BL-44 | Поиск по году ± 1 | `kinopoisk_api.py` | Фестивальные фильмы выходят в одном году, в прокат — в следующем. Fallback с tolerance ±1 при 0 результатах с точным годом. |
| BL-45 | Стоп-слова для очистки названия | `utils.py`, `settings_manager.py` | Пользователь задаёт список слов, которые `clean_title()` всегда вырезает (например, `REMUX`, `HDR`, `IMAX`). Особенно нужно для контента с техническими кодировками в именах. |
| BL-46 | Поиск по IMDB ID из имени файла | `utils.py`, `kinopoisk_api.py`, `scraper.py`, `tv_scraper.py` | Если в имени файла есть паттерн `tt\d+`, сразу резолвить через KP API `/v2.2/films?imdbId=tt...`, минуя fuzzy-search полностью. |

### 1.2 Реализовано

| # | Название | Файл / модуль | Описание |
|---|:---|:---|:---|
| BL-02 | Фильтрация по году выпуска | `kinopoisk_api.py:107-109` | Результаты сортируются по совпадению года. Год извлекается из имени файла в `clean_title()`. |
| BL-04 | Транслитерация латиница→кириллица | `utils.py`, `scraper.py`, `tv_scraper.py` | `transliterate_to_cyrillic()` конвертирует латиницу в кириллицу при 0 результатов. Fallback в обоих scraper-ах. |
| BL-05 | Нормализация спецсимволов | `utils.py:125-162` | `clean_title()` заменяет `.` и `_` на пробелы, убирает `[...]` и `(YYYY)`, обрезает `-,`. |
| BL-01 | ✅ Fuzzy-matching | `shared/utils.py`, `shared/kinopoisk_api.py` | `difflib.SequenceMatcher` + 3-уровневая сортировка (year, fuzzy_score, rating). Спецификация: `docs/fuzzy-matching/`. |
| BL-06 | Автовыбор совпадения | `scraper.py:117-127`, `tv_scraper.py:147-157` | Если 1 результат с точным совпадением по названию + году — автовыбор. Настройка `auto_select_exact_match`. |
| BL-03 | ✅ Двойной поиск (рус + ориг) | `shared/utils.py`, `scraper.py`, `tv_scraper.py` | `extract_alt_title()` + `deduplicate_results()` + `_perform_dual_search()`. Спецификация: `docs/dual-title-search/`. |

---

## 2. Обогащение метаданных

### 2.1 Идеи

| # | Название | Файл / модуль | Описание |
|---|:---|:---|:---|
| BL-42 | TMDB ID lookup | `kinopoisk_api.py`, `models.py`, `scraper.py` | Резолвинг TMDB ID через бесплатный TMDb API (find by IMDB ID). Нужен для совместимости со скинами Kodi, подтягивающими доп. контент по TMDB ID. |
| BL-47 | Биографии актёров | `kinopoisk_api.py`, `models.py` | KP API `/v1/staff/{id}` отдаёт краткое `description`. Kodi показывает его в карточке актёра при клике. |
| BL-48 | Язык оригинала | `kinopoisk_api.py`, `models.py`, `scraper.py`, `tv_scraper.py` | На основе `countries` / `productionCountries` из KP API проставлять тег языка оригинала. Полезно для фильтрации иностранного контента. |
| BL-49 | Теги тематики (keywords) | `kinopoisk_api.py`, `scraper.py`, `tv_scraper.py` | KP возвращает `keywords` для части фильмов. Добавлять как дополнительные `setTags()` рядом с тегами наград. |
| BL-63 | Названия сезонов (addSeason) | `tv_scraper.py`, `tvmaze_client.py` | KP API `/seasons` НЕ отдаёт названия сезонов. Требуется TVMaze как источник (отдельное исследование). Передавать через нативный `addSeason(number, name)`. |
| BL-64 | Режиссёры и сценаристы эпизодов | `tv_scraper.py`, `tvmaze_client.py` | TVMaze отдаёт crew для каждого эпизода. Передавать через `setDirectors()` и `setWriters()` на уровне эпизода. Сейчас эти поля заполняются только на уровне сериала. |
| BL-65 | Сортировка по оригинальному названию (setSortTitle) | `scraper.py`, `tv_scraper.py` | Передавать `title_original` через `setSortTitle()`, чтобы фильмы сортировались по оригинальному названию (латиницей), а отображались по-русски. |

### 2.2 Закрыто

| # | Название | Причина |
|---|:---|:---|
| BL-12 | ~~OpenSubtitles~~ | `won't do` — без скачивания субтитров ценности мало. Информация о наличии языков без возможности загрузки не оправдывает доп. API-ключ и запросы. Для скачивания есть `service.subtitles.opensubtitles-com`. |
| BL-43 | ~~Бюджет и сборы в описании~~ | `won't do` — Kodi не имеет нативных полей для бюджета/сборов (нет `setBudget()`, `setRevenue()` в InfoTagVideo, нет колонок в MyVideos.db). Добавление в plot засоряет описание. |
| BL-62 | ~~Позиция в TOP-250 (setTop250)~~ | `won't do` — KP API endpoint `/v2.2/films/top?type=TOP_250_BEST_FILMS` не содержит позицию фильма. Для определения позиции нужно загрузить все 13 страниц (250 фильмов) — нецелесообразно при лимите 500 req/day. |

### 2.3 Реализовано

| # | Название | Файл / модуль | Описание |
|---|:---|:---|:---|
| BL-07 | Возрастной рейтинг MPAA | `kinopoisk_api.py:30-36` | `_AGE_LIMIT_TO_MPAA` + `ratingMpaa`. Спецификация: `docs/mpaa-rating/requirements.md`. |
| BL-13 | Фото актёров и режиссёров | `kinopoisk_api.py:173-213` | `photo_url` загружается через `get_staff()`. |
| BL-08 | ✅ Коллекции и саги | `scraper.py`, `kinopoisk_api.py`, `utils.py` | `get_sequels()` + `extract_franchise_name()` + `setSet()`. Спецификация: `docs/collections-sagas/`. |
| BL-14 | Агрегация рейтингов | `omdb_client.py`, `scraper.py`, `tv_scraper.py` | KP + IMDb + RT + MC в одной записи через `setRatings()`. |
| BL-10 | ✅ Теги наград | `omdb_client.py`, `scraper.py`, `tv_scraper.py` | Парсинг OMDb Awards → теги Оскар/Глобус/Эмми/BAFTA/Канны → `setTags()`. Спецификация: `docs/award-tags/`. |
| BL-11 | ✅ Нормализация жанров | `kinopoisk_api.py`, `settings_manager.py` | Маппинг 31 жанра KP рус→англ, настройка "Язык жанров". Спецификация: `docs/genre-normalization/`. |
| BL-09 | ✅ Трейлеры YouTube | `kinopoisk_api.py`, `scraper.py`, `tv_scraper.py`, `nfo_writer.py`, `nfo_parser.py` | YouTube-трейлеры из KP API `/v2.2/films/{id}/videos` → `setTrailer()`. Кэш, graceful degradation, NFO roundtrip. Спецификация: `docs/youtube-trailers/`. |
| BL-61 | ✅ Краткое описание (setPlotOutline) | `kinopoisk_api.py`, `models.py`, `scraper.py`, `tv_scraper.py`, `nfo_writer.py`, `nfo_parser.py` | Поле `shortDescription` из KP API → `setPlotOutline()`. NFO roundtrip через `<outline>`. Спецификация: `docs/native-kodi-fields/`. |
| BL-60 | ✅ Дата премьеры (setPremiered) | `kinopoisk_api.py`, `models.py`, `scraper.py`, `tv_scraper.py`, `nfo_writer.py`, `nfo_parser.py` | Дата из `/v2.2/films/{id}/distributions` → `setPremiered()`. Приоритет: WORLD_PREMIER > Россия > PREMIERE. Кэш, graceful degradation. NFO roundtrip через `<premiered>`. Спецификация: `docs/native-kodi-fields/`. |

---

## 3. ТВ-шоу и сериалы

### 3.1 Идеи

| # | Название | Файл / модуль | Описание |
|---|:---|:---|:---|
| BL-38 | Статус сериала (setTvShowStatus) | `models.py`, `tv_scraper.py` | KP API отдаёт `productionStatus` (`ENDED`, `CANCELED`, `IN_PRODUCTION` и др.). Передавать через нативный `setTvShowStatus()`. Отображается в карточке сериала. |
| BL-40 | Сезонные постеры | `kinopoisk_api.py`, `tv_scraper.py` | KP API и TVMaze отдают постеры на уровне сезона. Kodi поддерживает season artwork через `setSeason()`. |
| BL-41 | Превью эпизодов из TVMaze (addAvailableArtwork) | `tvmaze_client.py`, `tv_scraper.py` | TVMaze возвращает `image.medium` для каждого эпизода. Передавать через нативный `addAvailableArtwork()` на уровне эпизода. Работает при включённом `use_tvmaze`. |
| BL-52 | Сортировка по absolute order (аниме) | `tv_scraper.py`, `settings_manager.py` | Для аниме нумерация KP и TVMaze часто расходится. Настройка `episode_order: absolute / aired` по аналогии с TheTVDB. |
| BL-53 | Специальные эпизоды (Season 0) | `tv_scraper.py`, `kinopoisk_api.py`, `tvmaze_client.py` | KP и TVMaze отдают specials отдельно. Сейчас они теряются. Kodi поддерживает Season 0 для спешлов. |

### 3.2 Реализовано

| # | Название | Файл / модуль | Описание |
|---|:---|:---|:---|
| BL-36 | ✅ Fallback при legacy episodeguide | `tv_scraper.py` | `_fallback_seasons_search()`: переиск по title_original, IMDB lookup, проверка типа kp_id (FILM vs TV_SERIES). Уведомление при неверном ID. |
| BL-15 | ✅ Улучшенный парсинг имени файла | `shared/utils.py` | S01E02, 1x02, С01Э03, «1 сезон 2 серия» — удаляются из названия, год из хвоста сохраняется. Спецификация: `docs/smart-parsing/`. |
| BL-16 | ✅ Детекция аниме-сериалов | `shared/utils.py` | Абсолютная нумерация с ведущим нулём (001, 042) = номер эпизода, не год. Спецификация: `docs/smart-parsing/`. |
| BL-17 | ✅ Обработка многосерийных фильмов | `shared/utils.py` | «Часть/Part/Vol/Том» → два кандидата (полное + базовое). Спецификация: `docs/smart-parsing/`. |
| BL-18 | ✅ Поддержка мини-сериалов | `shared/models.py`, `tv_scraper.py` | `is_miniseries` из KP API type="MINI_SERIES", тег «Мини-сериал». Спецификация: `docs/smart-parsing/`. |

---

## 4. Производительность и надёжность

### 4.1 Идеи

| # | Название | Файл / модуль | Описание |
|---|:---|:---|:---|
| BL-39 | Ротация нескольких API-ключей KP | `http_client.py`, `settings_manager.py` | Поддержка до 3 KP API-ключей. Round-robin при 429 или исчерпании дневной квоты (500 req/day на бесплатном тарифе). Снимает ограничения для больших библиотек. |
| BL-50 | Мониторинг здоровья API | `http_client.py`, `logger.py` | Периодическая проверка доступности `kinopoiskapiunofficial.tech`. Toast-уведомление при деградации: пользователь понимает, что проблема на стороне API, а не аддона. |
| BL-51 | Настраиваемый TTL кэша | `cache.py`, `settings_manager.py` | Сейчас TTL = 7 дней hardcoded. Вынести в настройку: 1 / 7 / 14 / 30 дней. Пользователи с нестабильной библиотекой выбирают меньше, с большой — больше. |
| BL-58 | NFO: поиск видеофайла в директории | `nfo_writer.py`, `scraper.py` | Когда `ListItem.FileNameAndPath` возвращает директорию (автосканирование), найти видеофайл внутри через `xbmcvfs.listdir()` и создать `<filename>.nfo`. Улучшение к BL-57 fix (guard). **Риск:** увеличение времени сканирования на больших библиотеках, особенно когда все файлы хранятся в 1 директории (listdir на сетевом хранилище может быть медленным). |

### 4.3 Закрыто

| # | Название | Причина |
|---|:---|:---|
| BL-21 | ~~Батчевый скрейпинг~~ | `won't do` — Kodi вызывает скрейпер по одному файлу, нет API для батчевого режима. Rate limiter общий (18 req/s), FileCache не потокобезопасен. Параллелизм невозможен внутри аддона. |

### 4.2 Реализовано

| # | Название | Файл / модуль | Описание |
|---|:---|:---|:---|
| BL-19 | Кэш сезонов (In-memory LRU) | `tv_scraper.py:33-43` | Max 10 записей, thread-safe. Избегает повторных API-запросов. |
| BL-22 | Retry с exponential backoff | `http_client.py:57-59` | 3 попытки, backoff base=1.0, multiplier=2.0. Retryable: 429, 5xx. |
| BL-23 | Rate limiting | `http_client.py:12-37` | Token bucket `RateLimiter`, thread-safe. KP: 18 req/s, staff: 9 req/s. |
| BL-20 | ✅ Персистентный кэш | `shared/cache.py`, `scraper.py`, `tv_scraper.py` | `FileCache` с TTL 7 дней, кэш details/staff/images/sequels/seasons/OMDb. Пустые результаты не кэшируются. Настройка "Очистить кэш". Спецификация: `docs/persistent-cache/`. |
| BL-24 | ✅ Graceful degradation | `scraper.py`, `tv_scraper.py`, `cache.py`, `nfo_parser.py`, `http_client.py`, `kinopoisk_api.py` | Fallback-цепочка: свежий кэш → API → stale кэш → NFO → hard fail. Degraded mode (5с, 0 retries). Уведомления. Спецификация: `docs/graceful-degradation/`. |
| BL-56 | ✅ Wikidata fallback для IMDB ID | `shared/wikidata_client.py`, `scraper.py`, `tv_scraper.py`, `settings_manager.py` | При пустом `imdbId` от KP API → SPARQL-запрос к Wikidata (P2603→P345). Кэширование результатов (включая пустые), degraded mode после 3 ошибок, stale cache fallback. Настройка `use_wikidata_fallback` (по умолч. вкл.). Спецификация: `docs/wikidata-fallback/`. |
| BL-57 | ✅ NFO guard для директорий | `shared/nfo_writer.py`, `scraper.py` | Guard в `_get_movie_nfo_path` — если путь без расширения (директория при автосканировании), NFO не создаётся. Предотвращает скрытые `.nfo` файлы. |

---

## 5. Пользовательский опыт

### 5.1 Идеи

| # | Название | Файл / модуль | Описание |
|---|:---|:---|:---|
| BL-27 | Режим только-обновление | `scraper.py`, `tv_scraper.py` | Скрейпить только файлы без постера или описания. Экономия API-квоты. |
| BL-28 | Dry-run режим | `scraper.py`, `tv_scraper.py` | Показать результаты без записи в БД Kodi. Отладка и проверка. |
| BL-29 | CLI-утилита | — (новый скрипт) | Скрейпинг одного файла → stdout (JSON). Тестирование вне Kodi. |
| BL-54 | Версия API в логах | `logger.py`, `kinopoisk_api.py` | При запуске логировать версию KP API endpoint и дату последнего успешного запроса. Упрощает диагностику при смене контракта API. |
| BL-55 | Экспорт статистики | `scraper.py`, `tv_scraper.py`, `cache.py` | Количество скрапированных файлов, cache hits, ошибок API — в виде toast или лог-файла. Полезно для диагностики на больших библиотеках. |

### 5.2 Реализовано

| # | Название | Файл / модуль | Описание |
|---|:---|:---|:---|
| BL-25 | ✅ NFO-экспорт | `shared/nfo_writer.py`, `scraper.py`, `tv_scraper.py` | Автоматическая запись .nfo-файлов рядом с видео после скрапинга. XML-формат Kodi, настройки enable/overwrite. Спецификация: `docs/nfo-export/`. |
| BL-26 | ✅ Детекция дублей | `shared/duplicate_tracker.py` | Персистентный трекинг kp_id → file_path, toast notification при дубле. Спецификация: `docs/duplicate-detection/`. |

---

## 6. Интеграции и совместимость

### 6.1 Идеи

| # | Название | Файл / модуль | Описание |
|---|:---|:---|:---|
| BL-30 | Letterboxd / TMDB ID | `models.py`, `scraper.py` | Дополнительные внешние ID для совместимости с другими Kodi-аддонами. Перекрыто BL-42 (TMDB ID lookup). |
| BL-31 | Кинопоиск watchlist | — (новый модуль) | Импорт «Буду смотреть» в Kodi-плейлист. Требует OAuth/cookies. |
| BL-59 | Совместимость с STRM файлами (Elementum / LibreELEC) | `scraper.py`, `tv_scraper.py` | Проверить и гарантировать работу скрапера с STRM файлами (Elementum, Jackett и др.) на LibreELEC 12 / Kodi 21 Omega. На Windows проблем нет, но на LibreELEC есть известный баг Kodi 21 ([xbmc/xbmc#24015](https://github.com/xbmc/xbmc/issues/24015)). Требуется тестирование на реальном LibreELEC. BUG-006. |

---

## 7. Тестирование и DevOps

### 7.1 Идеи

| # | Название | Файл / модуль | Описание |
|---|:---|:---|:---|
| BL-32 | Интеграционные тесты с реальным API | `tests/` | Тесты с живым API КП по расписанию (не в CI). Проверка актуальности контрактов. |
| BL-33 | Mock-сервер Кинопоиска | `tests/` | WireMock/json-server для unit-тестов без сети. Детерминированные результаты. |
| BL-34 | Метрики качества поиска | `tests/` | % точных совпадений на фикстурном наборе. Трекер регрессий алгоритма. |

### 7.2 Реализовано

| # | Название | Файл / модуль | Описание |
|---|:---|:---|:---|
| BL-35 | ✅ CI/CD pipeline | `.github/workflows/ci.yml`, `ruff.toml` | GitHub Actions: ruff lint + pytest (movie + TV) + build ZIP + auto-release по тегу v*. Спецификация: `docs/ci-cd/`. |

---

## 8. Сводка

| Статус | Кол-во | Пункты |
|:---|:---|:---|
| ✅ Реализовано | 30 | BL-01..BL-11, BL-13..BL-20, BL-22..BL-26, BL-35, BL-36, BL-56, BL-57, BL-60, BL-61 |
| 💡 Идея | 30 | BL-27..BL-34, BL-37..BL-42, BL-44..BL-55, BL-58, BL-59, BL-63..BL-65 |
| ❌ Закрыто | 4 | BL-12, BL-21, BL-43, BL-62 |
| **Итого** | **64** | |
