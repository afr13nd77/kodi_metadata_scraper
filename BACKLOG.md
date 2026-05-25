# Бэклог — Ultimate Movie Scraper

**Версия проекта:** 3.12.0 / 3.12.0 (movie / TV)
**Обновлён:** 2026-05-24

---

## 1. Качество поиска

### 1.1 Реализовано

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
| BL-09 | Трейлеры YouTube | `scraper.py`, `tv_scraper.py` | Ссылка на трейлер YouTube из KP → `setTrailer()`. Kodi воспроизводит YouTube нативно. |
| BL-12 | OpenSubtitles | — (новый модуль) | Интеграция OpenSubtitles API: языки субтитров, хеши файлов. |

### 2.2 Реализовано

| # | Название | Файл / модуль | Описание |
|---|:---|:---|:---|
| BL-07 | Возрастной рейтинг MPAA | `kinopoisk_api.py:30-36` | `_AGE_LIMIT_TO_MPAA` + `ratingMpaa`. Спецификация: `docs/mpaa-rating/requirements.md`. |
| BL-13 | Фото актёров и режиссёров | `kinopoisk_api.py:173-213` | `photo_url` загружается через `get_staff()`. |
| BL-08 | ✅ Коллекции и саги | `scraper.py`, `kinopoisk_api.py`, `utils.py` | `get_sequels()` + `extract_franchise_name()` + `setSet()`. Спецификация: `docs/collections-sagas/`. |
| BL-14 | Агрегация рейтингов | `omdb_client.py`, `scraper.py`, `tv_scraper.py` | KP + IMDb + RT + MC в одной записи через `setRatings()`. |
| BL-10 | ✅ Теги наград | `omdb_client.py`, `scraper.py`, `tv_scraper.py` | Парсинг OMDb Awards → теги Оскар/Глобус/Эмми/BAFTA/Канны → `setTags()`. Спецификация: `docs/award-tags/`. |
| BL-11 | ✅ Нормализация жанров | `kinopoisk_api.py`, `settings_manager.py` | Маппинг 31 жанра KP рус→англ, настройка "Язык жанров". Спецификация: `docs/genre-normalization/`. |

---

## 3. ТВ-шоу и сериалы

### 3.1 Идеи

| # | Название | Файл / модуль | Описание |
|---|:---|:---|:---|

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
| BL-21 | Батчевый скрейпинг | `scraper.py`, `tv_scraper.py` | Параллельный скрейпинг N файлов. Асинхронный HTTP или потоковый пул. |
| BL-24 | Graceful degradation | `scraper.py`, `tv_scraper.py` | API недоступен → кэш или NFO как fallback. Работа офлайн. |

### 4.2 Реализовано

| # | Название | Файл / модуль | Описание |
|---|:---|:---|:---|
| BL-19 | Кэш сезонов (In-memory LRU) | `tv_scraper.py:33-43` | Max 10 записей, thread-safe. Избегает повторных API-запросов. |
| BL-22 | Retry с exponential backoff | `http_client.py:57-59` | 3 попытки, backoff base=1.0, multiplier=2.0. Retryable: 429, 5xx. |
| BL-23 | Rate limiting | `http_client.py:12-37` | Token bucket `RateLimiter`, thread-safe. KP: 18 req/s, staff: 9 req/s. |
| BL-20 | ✅ Персистентный кэш | `shared/cache.py`, `scraper.py`, `tv_scraper.py` | `FileCache` с TTL 7 дней, кэш details/staff/images/sequels/seasons/OMDb. Пустые результаты не кэшируются. Настройка "Очистить кэш". Спецификация: `docs/persistent-cache/`. |

---

## 5. Пользовательский опыт

### 5.1 Идеи

| # | Название | Файл / модуль | Описание |
|---|:---|:---|:---|
| BL-25 | NFO-экспорт | `nfo_parser.py` (+ новый код) | Экспорт метаданных в .nfo рядом с видео. Парсинг есть, нужен обратный экспорт. |
| BL-26 | Детекция дублей | — (новая логика) | Два файла с одинаковым kp_id → предупреждение пользователю. |
| BL-27 | Режим только-обновление | `scraper.py`, `tv_scraper.py` | Скрейпить только файлы без постера или описания. Экономия API-квоты. |
| BL-28 | Dry-run режим | `scraper.py`, `tv_scraper.py` | Показать результаты без записи в БД Kodi. Отладка и проверка. |
| BL-29 | CLI-утилита | — (новый скрипт) | Скрейпинг одного файла → stdout (JSON). Тестирование вне Kodi. |

---

## 6. Интеграции и совместимость

### 6.1 Идеи

| # | Название | Файл / модуль | Описание |
|---|:---|:---|:---|
| BL-30 | Letterboxd / TMDB ID | `models.py`, `scraper.py` | Дополнительные внешние ID для совместимости с другими Kodi-аддонами. |
| BL-31 | Кинопоиск watchlist | — (новый модуль) | Импорт «Буду смотреть» в Kodi-плейлист. Требует OAuth/cookies. |

---

## 7. Тестирование и DevOps

### 7.1 Идеи

| # | Название | Файл / модуль | Описание |
|---|:---|:---|:---|
| BL-32 | Интеграционные тесты с реальным API | `tests/` | Тесты с живым API КП по расписанию (не в CI). Проверка актуальности контрактов. |
| BL-33 | Mock-сервер Кинопоиска | `tests/` | WireMock/json-server для unit-тестов без сети. Детерминированные результаты. |
| BL-34 | Метрики качества поиска | `tests/` | % точных совпадений на фикстурном наборе. Трекер регрессий алгоритма. |
| BL-35 | CI/CD pipeline | — | Lint + unit tests на каждый PR. Требует инициализации git + GitHub Actions. |

---

## 8. Сводка

| Статус | Кол-во | Пункты |
|:---|:---|:---|
| ✅ Реализовано | 21 | BL-01, BL-02, BL-03, BL-04, BL-05, BL-06, BL-07, BL-08, BL-10, BL-11, BL-13, BL-14, BL-15, BL-16, BL-17, BL-18, BL-19, BL-20, BL-22, BL-23, BL-36 |
| 💡 Идея | 14 | BL-09, BL-12, BL-21, BL-24..BL-35 |
| **Итого** | **36** | |
