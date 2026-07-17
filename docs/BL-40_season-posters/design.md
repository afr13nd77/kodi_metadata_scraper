# BL-40 + BL-63: Технический дизайн — Сезонные постеры и названия сезонов

**Дата:** 17.07.2026
**Статус:** draft
**Версия скрапера:** 3.17.2 (TV)
**Автор:** opus (архитектор)

---

## 1. Архитектура

### 1.1 Затрагиваемые модули

| Модуль | Файл | Тип изменения |
|:---|:---|:---|
| Модель данных | `shared/models.py` | Расширение dataclass `Season` |
| TVMaze клиент | `shared/tvmaze_client.py` | Новый метод `get_seasons()` + кэш |
| TV scraper | `metadata.tvshows.ums/python/tv_scraper.py` | Интеграция в `_handle_getdetails` |
| Настройки XML | `metadata.tvshows.ums/resources/settings.xml` | Новая настройка `use_season_art` |
| Settings Manager | `shared/settings_manager.py` | Новый property `use_season_art` |
| Локализация EN | `metadata.tvshows.ums/resources/language/resource.language.en_gb/strings.po` | Строки 32160-32161 |
| Локализация RU | `metadata.tvshows.ums/resources/language/resource.language.ru_ru/strings.po` | Строки 32160-32161 |

### 1.2 Поток данных

```
_handle_getdetails (tv_scraper.py)
  │
  ├── 1. Получение TVShowDetails из KP API (без изменений)
  ├── 2. Резолвинг IMDB ID (KP → Wikidata fallback, без изменений)
  ├── 3. Обогащение OMDb (без изменений)
  ├── 4. Трейлеры BL-09 (без изменений)
  │
  ├── 5. [НОВОЕ] Сезонный арт + названия (BL-40/63)
  │     ├── Проверка условий: use_tvmaze AND use_season_art AND imdb_id
  │     ├── tvmaze_client.lookup_show(imdb_id) → show_id
  │     ├── tvmaze_client.get_seasons(show_id) → list[SeasonArtInfo]
  │     └── Передача данных в _add_season_art_to_infotag()
  │
  ├── 6. Build episodeguide JSON (без изменений)
  ├── 7. _apply_tvshow_details_to_listitem (без изменений)
  │
  ├── 8. [НОВОЕ] _add_season_art_to_infotag(infotag, season_art_list, logger)
  │     ├── vtag.addSeason(number, name) для каждого сезона
  │     └── vtag.addAvailableArtwork(url, "poster", preview, season=number)
  │
  └── 9. setEpisodeGuide, NFO export, setResolvedUrl (без изменений)
```

**Ключевое решение:** сезонный арт добавляется **после** `_apply_tvshow_details_to_listitem` и получения `infotag`, но **до** `setEpisodeGuide`. Вызовы `addSeason()` и `addAvailableArtwork(..., season=N)` идут напрямую через `infotag` (объект `VideoInfoTag`), а не через `ListItem`.

---

## 2. Изменения в модели данных

### 2.1 Расширение dataclass `Season` (shared/models.py)

Текущее состояние (строки 123-126):
```python
@dataclass
class Season:
    number: int = 0
    episodes: list[Episode] = field(default_factory=list)
```

**Не меняем.** Dataclass `Season` используется для хранения KP-данных об эпизодах по сезонам. Добавлять TVMaze-специфичные поля (poster, name) в KP-модель архитектурно некорректно: это смешение источников данных.

### 2.2 Новый dataclass `SeasonArtInfo` (shared/models.py)

```python
@dataclass
class SeasonArtInfo:
    """Season artwork and name from TVMaze API."""
    number: int = 0
    name: str = ""
    poster_url: str = ""
    poster_preview_url: str = ""
```

**Обоснование:**
- Отдельный dataclass для TVMaze-данных, не связанный с KP-моделью `Season`.
- Минимальный набор полей: только то, что нужно для `addSeason()` и `addAvailableArtwork()`.
- Immutable по природе (не мутируется после создания).
- Отсутствие `poster_url` (пустая строка) означает "нет постера" — не нужен Optional.

---

## 3. Новый метод `TvmazeClient.get_seasons()`

### 3.1 API контракт

```python
def get_seasons(self, show_id: int) -> Optional[list[SeasonArtInfo]]:
    """Fetch season artwork and names from TVMaze.

    API: GET /shows/{show_id}/seasons
    Returns list of SeasonArtInfo or None on error.
    """
```

**Входные данные:** `show_id` (int) — внутренний ID TVMaze, полученный через `lookup_show()`.

**Выходные данные:** `list[SeasonArtInfo]` или `None` при ошибке.

**Парсинг ответа TVMaze:**
```python
# Для каждого элемента массива:
SeasonArtInfo(
    number=item.get("number", 0),       # int
    name=item.get("name") or "",         # str, может быть null/""/пробелы
    poster_url=(item.get("image") or {}).get("original", ""),
    poster_preview_url=(item.get("image") or {}).get("medium", ""),
)
```

### 3.2 Фильтрация

- Элементы с `number == 0` (Season 0 / Specials) **включаются** в результат. Kodi поддерживает `addSeason(0, name)` — название Specials-сезона полезно.
- Элементы с `number is None` (бывает при невалидных данных TVMaze) **пропускаются** с warning-логом.

### 3.3 Кэширование

Аналогично `_episodes_cache`:

```python
# Новые module-level переменные:
_seasons_cache: dict[int, list[SeasonArtInfo]] = {}
_TVMAZE_CACHE_MAX_SEASONS = 10
```

- Ключ: `show_id` (int), аналогично `_episodes_cache`.
- Максимум 10 записей (LRU-подобное, FIFO при переполнении — аналогично текущей реализации).
- Thread-safe: использует существующий `_tvmaze_cache_lock`.
- In-memory только (без FileCache) — согласно требованиям (Out of Scope: дисковый кэш).

### 3.4 Обработка ошибок

| Ситуация | Действие |
|:---|:---|
| HTTP 404 | `_log_warning`, return `None` |
| HTTP 429 (rate limit) | `_log_warning`, return `None` (rate limiter уже настроен) |
| HTTP 5xx | `_log_warning`, return `None` |
| Timeout | `_log_warning`, return `None` |
| Невалидный JSON | `_log_warning`, return `None` |
| Пустой массив `[]` | return `[]` (пустой список — валидный ответ) |
| `number is None` в элементе | пропустить элемент с warning |

### 3.5 Логирование

Все логи через f-strings (правило проекта — НИКОГДА %s):

```python
self._log_info(f"TvmazeClient.get_seasons: fetching seasons for show_id={show_id}")
self._log_info(f"TvmazeClient.get_seasons: success for show_id={show_id}, {len(result)} seasons")
self._log_debug(f"TvmazeClient.get_seasons: cache hit for show_id={show_id}")
self._log_warning(f"TvmazeClient.get_seasons: HTTP error for show_id={show_id}: {exc}")
self._log_warning(f"TvmazeClient.get_seasons: skipping season with number=None in show_id={show_id}")
```

### 3.6 Полный метод (псевдокод)

```python
def get_seasons(self, show_id: int) -> Optional[list[SeasonArtInfo]]:
    # 1. Проверка кэша
    with _tvmaze_cache_lock:
        if show_id in _seasons_cache:
            self._log_debug(f"TvmazeClient.get_seasons: cache hit for show_id={show_id}")
            return _seasons_cache[show_id]

    self._log_info(f"TvmazeClient.get_seasons: fetching seasons for show_id={show_id}")

    # 2. HTTP-запрос
    try:
        data = self._http.get_json(f"/shows/{show_id}/seasons")
    except HttpError as exc:
        self._log_warning(f"TvmazeClient.get_seasons: HTTP error for show_id={show_id}: {exc}")
        return None
    except Exception as exc:
        self._log_warning(f"TvmazeClient.get_seasons: unexpected error for show_id={show_id}: {exc}")
        return None

    # 3. Валидация типа
    if not isinstance(data, list):
        self._log_warning(
            f"TvmazeClient.get_seasons: unexpected response type for show_id={show_id}: "
            f"{type(data).__name__}"
        )
        return None

    # 4. Парсинг
    result: list[SeasonArtInfo] = []
    for item in data:
        num = item.get("number")
        if num is None:
            self._log_warning(
                f"TvmazeClient.get_seasons: skipping season with number=None in show_id={show_id}"
            )
            continue
        image = item.get("image") or {}
        result.append(SeasonArtInfo(
            number=int(num),
            name=item.get("name") or "",
            poster_url=image.get("original", ""),
            poster_preview_url=image.get("medium", ""),
        ))

    # 5. Кэширование
    with _tvmaze_cache_lock:
        if len(_seasons_cache) >= _TVMAZE_CACHE_MAX_SEASONS:
            oldest_key = next(iter(_seasons_cache))
            del _seasons_cache[oldest_key]
        _seasons_cache[show_id] = result

    self._log_info(
        f"TvmazeClient.get_seasons: success for show_id={show_id}, {len(result)} seasons"
    )
    return result
```

---

## 4. Интеграция в tv_scraper.py

### 4.1 Точка вставки

В `_handle_getdetails`, **между** строкой 669 (`_apply_tvshow_details_to_listitem`) и строкой 671 (`infotag = listitem.getVideoInfoTag()`).

Текущий код (строки 668-676):
```python
    listitem = xbmcgui.ListItem(offscreen=True)
    _apply_tvshow_details_to_listitem(tvshow, listitem, settings, logger)

    infotag = listitem.getVideoInfoTag()
    infotag.setEpisodeGuide(episodeguide)

    write_tvshow_nfo(tvshow, video_file_path, settings, logger)

    xbmcplugin.setResolvedUrl(handle, True, listitem)
```

Новый код (вставка после строки 671, после получения `infotag`):
```python
    listitem = xbmcgui.ListItem(offscreen=True)
    _apply_tvshow_details_to_listitem(tvshow, listitem, settings, logger)

    infotag = listitem.getVideoInfoTag()

    # --- BL-40/63: Season artwork and names ---
    _apply_season_art(tvshow.imdb_id, infotag, settings, logger)
    # --- end BL-40/63 ---

    infotag.setEpisodeGuide(episodeguide)

    write_tvshow_nfo(tvshow, video_file_path, settings, logger)

    xbmcplugin.setResolvedUrl(handle, True, listitem)
```

### 4.2 Новая функция `_apply_season_art`

Размещается в секции `# ListItem mapping helpers` (после `_apply_tvshow_details_to_listitem`, перед `_apply_episode_to_listitem`).

```python
def _apply_season_art(
    imdb_id: str,
    infotag,
    settings: SettingsManager,
    logger: Logger,
) -> None:
    """Fetch and apply season artwork and names from TVMaze (BL-40/63).

    Calls vtag.addSeason(number, name) and
    vtag.addAvailableArtwork(url, "poster", preview, season=number)
    for each season with artwork in TVMaze.
    """
    # Gate: три условия должны быть выполнены
    if not settings.use_tvmaze:
        logger.debug("_apply_season_art: use_tvmaze=false, skipping")
        return
    if not settings.use_season_art:
        logger.debug("_apply_season_art: use_season_art=false, skipping")
        return
    if not imdb_id:
        logger.warning("_apply_season_art: no IMDB ID, cannot fetch season art")
        return

    logger.info(f"_apply_season_art: fetching season art for imdb_id={imdb_id}")

    tvmaze = TvmazeClient(logger)

    # 1. Получить show_id (используется общий кэш, повторный lookup бесплатен)
    show_id = tvmaze.lookup_show(imdb_id)
    if show_id is None:
        logger.warning(f"_apply_season_art: TVMaze show not found for imdb_id={imdb_id}")
        return

    # 2. Получить сезоны
    seasons = tvmaze.get_seasons(show_id)
    if seasons is None:
        logger.warning(f"_apply_season_art: failed to fetch seasons for show_id={show_id}")
        return
    if not seasons:
        logger.info(f"_apply_season_art: no seasons returned for show_id={show_id}")
        return

    # 3. Применить к infotag
    art_count = 0
    for s in seasons:
        infotag.addSeason(s.number, s.name)
        if s.poster_url:
            infotag.addAvailableArtwork(
                s.poster_url,
                arttype="poster",
                preview=s.poster_preview_url,
                season=s.number,
            )
            art_count += 1

    logger.info(
        f"_apply_season_art: applied {len(seasons)} seasons, "
        f"{art_count} posters for imdb_id={imdb_id}"
    )
```

### 4.3 Логика условий (gate)

Три условия, проверяемые последовательно:

1. `settings.use_tvmaze == True` — TVMaze включён глобально.
2. `settings.use_season_art == True` — сезонный арт включён (подчинён use_tvmaze).
3. `tvshow.imdb_id` не пустой — без IMDB ID невозможен lookup в TVMaze.

При невыполнении любого условия — ранний return с debug/warning логом. Остальные метаданные сериала не затрагиваются (graceful degradation).

### 4.4 Повторный lookup

`tvmaze.lookup_show(imdb_id)` к моменту вызова `_apply_season_art` уже мог быть вызван ранее (для эпизодов). Благодаря `_show_cache` повторный вызов обслуживается из in-memory кэша без HTTP-запроса. Создание нового экземпляра `TvmazeClient` безопасно — кэш module-level, общий для всех экземпляров.

---

## 5. Настройки

### 5.1 settings.xml (metadata.tvshows.ums/resources/settings.xml)

Новая группа `3ca` вставляется **после** группы `3c` (`use_tvmaze`) — логически связана:

```xml
<group id="3ca">
  <setting id="use_season_art" type="boolean" label="32160" help="32161">
    <level>0</level>
    <default>true</default>
    <dependencies>
      <dependency type="visible" setting="use_tvmaze">true</dependency>
    </dependencies>
    <control type="toggle"/>
  </setting>
</group>
```

**Поведение:**
- Настройка **видима** только при `use_tvmaze = true` (dependency `visible`).
- По умолчанию **включена** (`true`) — если пользователь включил TVMaze, сезонные постеры работают автоматически.
- При `use_tvmaze = false` настройка скрыта и не влияет на поведение (gate в коде проверяет оба флага).

### 5.2 Строки локализации

**ID 32160-32161** (свободный диапазон между 32151 и 32170):

EN (`resource.language.en_gb/strings.po`):
```
msgctxt "#32160"
msgid "Season posters and names"
msgstr ""

msgctxt "#32161"
msgid "Fetch season posters and names from TVMaze (uses 1 extra API request per TV show)"
msgstr ""
```

RU (`resource.language.ru_ru/strings.po`):
```
msgctxt "#32160"
msgid "Постеры и названия сезонов"
msgstr ""

msgctxt "#32161"
msgid "Загружать постеры и названия сезонов из TVMaze (1 дополнительный API-запрос на сериал)"
msgstr ""
```

### 5.3 settings_manager.py (shared/settings_manager.py)

Новый property после `use_tvmaze` (строка 37):

```python
@property
def use_season_art(self) -> bool:
    return self._addon.getSettingBool("use_season_art")
```

---

## 6. Кэширование

### 6.1 Стратегия

| Кэш | Ключ | Размер | Scope | Обоснование |
|:---|:---|:---|:---|:---|
| `_show_cache` | imdb_id/name -> show_id | 20 | module-level | Уже есть, переиспользуется |
| `_seasons_cache` | show_id -> list[SeasonArtInfo] | 10 | module-level | **Новый**, аналогично `_episodes_cache` |

### 6.2 TTL

In-memory кэш не имеет TTL — живёт до перезагрузки Kodi. Это приемлемо:
- Постеры сезонов меняются крайне редко (раз в год при выходе нового сезона).
- При обновлении библиотеки Kodi перезапускает скрапер, но данные ещё в памяти — экономим HTTP-запрос.
- Полная инвалидация происходит при перезапуске Kodi (new process).

### 6.3 Дисковый кэш

**Не используется** (явно указано в Out of Scope). `FileCache` применяется только для KP API, где TTL = 7 дней критичен для оффлайн-работы. TVMaze-данные — опциональное обогащение, потеря при рестарте допустима.

### 6.4 Потоко-безопасность

Новый `_seasons_cache` защищён существующим `_tvmaze_cache_lock`. Не требуется новый lock — все TVMaze-кэши логически связаны и не создают contention (Kodi обычно скрапит последовательно).

---

## 7. Альтернативы

### 7.1 Почему TVMaze, а не KP API

| Критерий | TVMaze | KP API |
|:---|:---|:---|
| Per-season images | Есть (`image.original`, `image.medium`) | **Нет** (API не возвращает постеры по сезонам) |
| Season names | Есть (`name`) | Нет |
| Стоимость | Бесплатный, без ключа | Требует API-ключ, лимиты |
| Rate limit | 2 req/s (настроен) | 18 req/s (настроен) |
| Покрытие | Хорошее для западных сериалов | Хорошее для русскоязычного контента |

**Вывод:** KP API не предоставляет per-season artwork и season names. TVMaze — единственный доступный источник в рамках текущего стека (TMDb исключён — правило проекта).

### 7.2 Почему отдельная функция, а не расширение `_apply_tvshow_details_to_listitem`

- `_apply_tvshow_details_to_listitem` маппит KP-данные на ListItem. Добавлять TVMaze HTTP-вызовы внутрь — нарушение SRP.
- Отдельная функция `_apply_season_art` изолирует TVMaze-логику, упрощает тестирование и отладку.
- Graceful degradation: ошибка в `_apply_season_art` не влияет на основной маппинг.

### 7.3 Почему SeasonArtInfo, а не расширение Season

- `Season` — KP-модель с episodes. Она используется в `_handle_getepisodelist`.
- Season artwork приходит из TVMaze, существует в другом lifecycle (getdetails, не getepisodelist).
- Смешение источников в одном dataclass создаёт путаницу: какие поля заполнены из KP, какие из TVMaze?

---

## 8. Security / Edge cases

### 8.1 Rate limiting

TVMaze rate limit: 2 req/s. Уже настроен через `_tvmaze_limiter = RateLimiter(2.0)`. Новый запрос `get_seasons` проходит через тот же `HttpClient` с тем же limiter — автоматически соблюдается.

**Дополнительная нагрузка:** 1 HTTP-запрос на сериал (при cache miss). При повторном сканировании — 0 запросов (cache hit по show_id). Lookup_show обычно уже закэширован (если TVMaze использовался для эпизодов).

### 8.2 Отсутствие image

TVMaze может вернуть `"image": null` для сезона (часто для Season 0 / Specials, или для будущих сезонов без промо-арта).

**Обработка:**
- `(item.get("image") or {}).get("original", "")` безопасно возвращает `""`.
- В `_apply_season_art`: `if s.poster_url:` — `addAvailableArtwork` не вызывается.
- `addSeason(number, name)` вызывается **всегда** — даже без постера, название сезона полезно.

### 8.3 Season 0 (Specials)

Включён в обработку. `addSeason(0, "Specials")` — валидный вызов для Kodi. Если image есть — добавляется. Если нет — только название.

**Примечание:** BL-53 (отдельная задача) может в будущем добавить специальную обработку Specials. Текущая реализация не конфликтует — Specials обрабатываются наравне с другими сезонами.

### 8.4 Пустое имя сезона

TVMaze может вернуть `"name": ""` или `"name": null`. В обоих случаях `item.get("name") or ""` даёт пустую строку. `addSeason(1, "")` — валидный вызов. Kodi покажет дефолтное "Season 1".

### 8.5 Большое число сезонов

Некоторые шоу (soap operas) могут иметь 30+ сезонов. Каждый вызов `addSeason` + `addAvailableArtwork` — легковесная операция (запись в метаданные). Нет риска performance degradation.

### 8.6 Конкурентные вызовы

Kodi вызывает `getdetails` последовательно (один сериал за раз). Но `_tvmaze_cache_lock` гарантирует thread-safety на случай параллельных вызовов.

### 8.7 Fallback при ошибке TVMaze

Если `get_seasons()` возвращает `None` (любая ошибка), `_apply_season_art` логирует warning и возвращается. Все остальные метаданные сериала уже применены через `_apply_tvshow_details_to_listitem`. Graceful degradation полностью изолирована.

---

## 9. Импакт на тесты

### 9.1 Новые тесты (metadata.tvshows.ums/tests/)

1. **`test_apply_season_art`** — unit-тест `_apply_season_art`:
   - Мок `TvmazeClient.lookup_show`, `get_seasons`.
   - Проверка: `addSeason` вызван для каждого сезона.
   - Проверка: `addAvailableArtwork` вызван только для сезонов с `poster_url`.
   - Проверка: при `use_tvmaze=false` ничего не вызывается.
   - Проверка: при пустом `imdb_id` ничего не вызывается.
   - Проверка: при ошибке TVMaze — graceful degradation.

2. **`test_get_seasons`** — unit-тест `TvmazeClient.get_seasons` (в shared/tests/):
   - Мок HTTP-ответа.
   - Проверка: парсинг сезонов, кэширование, обработка ошибок.
   - Проверка: season с `number=None` пропускается.
   - Проверка: season с `image=null` — `poster_url=""`.

### 9.2 Существующие тесты

Изменения не должны затронуть существующие тесты. `_handle_getdetails` получает новый вызов, но он изолирован в отдельной функции с early return при отключённых настройках.

---

## 10. Чек-лист для tasks.md

- [ ] T-01: Добавить `SeasonArtInfo` dataclass в `shared/models.py`
- [ ] T-02: Добавить `_seasons_cache` и `get_seasons()` в `shared/tvmaze_client.py`
- [ ] T-03: Добавить property `use_season_art` в `shared/settings_manager.py`
- [ ] T-04: Добавить настройку `use_season_art` в `metadata.tvshows.ums/resources/settings.xml`
- [ ] T-05: Добавить строки 32160-32161 в strings.po (EN + RU)
- [ ] T-06: Добавить функцию `_apply_season_art` в `tv_scraper.py`
- [ ] T-07: Интегрировать вызов `_apply_season_art` в `_handle_getdetails`
- [ ] T-08: Добавить import `SeasonArtInfo` в `tv_scraper.py`
- [ ] T-09: Написать тесты для `get_seasons()`
- [ ] T-10: Написать тесты для `_apply_season_art()`
