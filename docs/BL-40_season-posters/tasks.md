# BL-40 + BL-63: Задачи — Сезонные постеры и названия сезонов

**Дата:** 17.07.2026
**Статус:** done
**Версия:** 3.17.2 → 3.18.0 (TV)

---

## Задачи

```
T-01 [sonnet] — Добавить dataclass SeasonArtInfo в models.py
  Traces to: US-01, US-02
  File: shared/models.py
  Task: Добавить новый dataclass SeasonArtInfo после Season (строка 126).
        Поля: number: int = 0, name: str = "", poster_url: str = "",
        poster_preview_url: str = "".
        Не менять существующий Season.
  Context: SeasonArtInfo — TVMaze-модель для season artwork, отделена от KP-модели Season.
           Используется TvmazeClient.get_seasons() и _apply_season_art() в tv_scraper.py.
  Depends on: none
  Verify: cd metadata.tvshows.ums && python -m pytest tests/ -v
  Live test: python -c "from models import SeasonArtInfo; s = SeasonArtInfo(1, 'Test', 'http://a.jpg', 'http://b.jpg'); print(s)"
  Status: [✓] done
```

```
T-02 [sonnet] — Добавить метод get_seasons() и _seasons_cache в TvmazeClient
  Traces to: US-01, US-02, AC-01, AC-02, AC-07
  File: shared/tvmaze_client.py
  Task: 1) Добавить import SeasonArtInfo (from models import SeasonArtInfo).
        2) Добавить module-level переменные:
           _seasons_cache: dict[int, list[SeasonArtInfo]] = {}
           _TVMAZE_CACHE_MAX_SEASONS = 10
        3) Добавить метод get_seasons(self, show_id: int) -> Optional[list[SeasonArtInfo]]:
           - Проверка _seasons_cache (thread-safe через _tvmaze_cache_lock)
           - HTTP GET /shows/{show_id}/seasons через self._http.get_json()
           - Парсинг: number=item.get("number"), name=item.get("name") or "",
             poster_url=(item.get("image") or {}).get("original", ""),
             poster_preview_url=(item.get("image") or {}).get("medium", "")
           - Пропускать элементы с number=None (warning лог)
           - Кэширование результата (FIFO при переполнении)
           - Обработка ошибок: HttpError, Exception → return None
           - Все логи через f-strings
        Метод размещается после get_episodes() (строка 288).
  Context: API TVMaze GET /shows/{id}/seasons возвращает массив сезонов с image.original/medium.
           Кэш аналогичен _episodes_cache. Rate limiter уже настроен (2 req/s).
           Используется _apply_season_art() из tv_scraper.py.
  Depends on: T-01
  Verify: cd shared && python -m pytest tests/ -v
  Live test: запуск через Python REPL не требуется, проверяется через T-10
  Status: [✓] done
```

```
T-03 [sonnet] — Добавить property use_season_art в SettingsManager
  Traces to: US-03, AC-04
  File: shared/settings_manager.py
  Task: Добавить property после use_tvmaze (строка 36):
        @property
        def use_season_art(self) -> bool:
            return self._addon.getSettingBool("use_season_art")
  Context: Настройка видима при use_tvmaze=true. По умолчанию true.
           Проверяется в _apply_season_art() как gate-условие.
  Depends on: none
  Verify: cd metadata.tvshows.ums && python -m pytest tests/ -v
  Live test: проверяется через T-10
  Status: [✓] done
```

```
T-04 [sonnet] — Добавить настройку use_season_art в settings.xml
  Traces to: US-03, AC-04
  File: metadata.tvshows.ums/resources/settings.xml
  Task: Добавить group id="3ca" ПОСЛЕ group id="3c" (use_tvmaze, строка 64) и ПЕРЕД group id="3d":
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
  Context: Настройка видима только при use_tvmaze=true.
           По умолчанию включена — постеры сезонов загружаются автоматически.
  Depends on: none
  Verify: XML валидность: python -c "import xml.etree.ElementTree as ET; ET.parse('metadata.tvshows.ums/resources/settings.xml')"
  Live test: установить аддон → настройки → видимость use_season_art зависит от use_tvmaze
  Status: [✓] done
```

```
T-05 [sonnet] — Добавить строки локализации 32160-32161 в strings.po (EN + RU)
  Traces to: US-03
  Files:
    - metadata.tvshows.ums/resources/language/resource.language.en_gb/strings.po
    - metadata.tvshows.ums/resources/language/resource.language.ru_ru/strings.po
  Task: Добавить в конец каждого файла:
        EN:
          msgctxt "#32160"
          msgid "Season posters and names"
          msgstr ""

          msgctxt "#32161"
          msgid "Fetch season posters and names from TVMaze (1 extra API request per TV show)"
          msgstr ""

        RU:
          msgctxt "#32160"
          msgid "Постеры и названия сезонов"
          msgstr ""

          msgctxt "#32161"
          msgid "Загружать постеры и названия сезонов из TVMaze (1 дополнительный API-запрос на сериал)"
          msgstr ""
  Context: ID 32160-32161 свободны (между 32151 и 32170).
  Depends on: none
  Verify: grep -n "32160\|32161" metadata.tvshows.ums/resources/language/*/strings.po
  Live test: проверяется через T-04 (настройки показывают текст)
  Status: [✓] done
```

```
T-06 [sonnet] — Добавить функцию _apply_season_art в tv_scraper.py
  Traces to: US-01, US-02, AC-01, AC-02, AC-03, AC-04, AC-05, AC-06
  File: metadata.tvshows.ums/python/tv_scraper.py
  Task: Добавить функцию _apply_season_art() ПОСЛЕ _apply_tvshow_details_to_listitem
        (строка ~1205) и ПЕРЕД _apply_episode_to_listitem (строка 1207).
        Сигнатура: _apply_season_art(imdb_id: str, infotag, settings: SettingsManager, logger: Logger) -> None
        Логика:
        1. Gate: if not settings.use_tvmaze → debug лог, return
        2. Gate: if not settings.use_season_art → debug лог, return
        3. Gate: if not imdb_id → warning лог, return
        4. tvmaze = TvmazeClient(logger)
        5. show_id = tvmaze.lookup_show(imdb_id) → if None: warning, return
        6. seasons = tvmaze.get_seasons(show_id) → if None: warning, return; if empty: info, return
        7. Цикл по seasons:
           - infotag.addSeason(s.number, s.name)
           - if s.poster_url: infotag.addAvailableArtwork(s.poster_url, arttype="poster", preview=s.poster_preview_url, season=s.number)
        8. Итоговый info лог: количество сезонов и постеров
        Все логи через f-strings.
  Context: Функция изолирует TVMaze-логику от KP-маппинга. Graceful degradation — ошибки
           не влияют на остальные метаданные. lookup_show обычно уже в кэше (из get_episode_plot).
           Паттерн из TMDb scraper: _add_season_info() в data_utils.py:162-179.
  Depends on: T-01, T-02, T-03
  Verify: cd metadata.tvshows.ums && python -m pytest tests/ -v
  Live test: проверяется через T-07
  Status: [✓] done
```

```
T-07 [sonnet] — Интегрировать вызов _apply_season_art в _handle_getdetails
  Traces to: AC-01, AC-02
  File: metadata.tvshows.ums/python/tv_scraper.py
  Task: В _handle_getdetails, ПОСЛЕ строки 671 (infotag = listitem.getVideoInfoTag())
        и ПЕРЕД строкой 672 (infotag.setEpisodeGuide(episodeguide)):
        Вставить:
            # --- BL-40/63: Season artwork and names ---
            _apply_season_art(tvshow.imdb_id, infotag, settings, logger)
            # --- end BL-40/63 ---
  Context: К этому моменту tvshow.imdb_id уже заполнен (KP API или Wikidata fallback).
           infotag — VideoInfoTag, поддерживает addSeason() и addAvailableArtwork().
           Вызов после _apply_tvshow_details_to_listitem обеспечивает, что основные
           метаданные уже применены.
  Depends on: T-06
  Verify: cd metadata.tvshows.ums && python -m pytest tests/ -v
  Live test: Kodi → обновить информацию сериала → в логе "applied X seasons, Y posters"
             → сезоны показывают постеры
  Status: [✓] done
```

```
T-08 [sonnet] — Добавить import SeasonArtInfo в tv_scraper.py
  Traces to: US-01
  File: metadata.tvshows.ums/python/tv_scraper.py
  Task: В строке 24-27 (import из models), добавить SeasonArtInfo:
        from models import (
            TVShowDetails, Season, Episode, SeasonArtInfo,
            ArtworkType, DataSource, Rating
        )
  Context: SeasonArtInfo используется аннотацией типов в _apply_season_art.
           При Python 3.8 с `from __future__ import annotations` (строка 1)
           аннотации являются строками и не требуют runtime import,
           но для единообразия добавляем в блок imports.
  Depends on: T-01
  Verify: cd metadata.tvshows.ums && python -m pytest tests/ -v
  Live test: не требуется отдельно
  Status: [✓] done
```

```
T-09 [sonnet] — Написать тесты для TvmazeClient.get_seasons()
  Traces to: AC-01, AC-03, AC-06, AC-07
  File: shared/tests/test_tvmaze_client.py (новый файл, если не существует)
  Task: Написать unit-тесты:
        1. test_get_seasons_success — мок HTTP ответа с 3 сезонами, проверить парсинг SeasonArtInfo
        2. test_get_seasons_cache_hit — второй вызов берёт из кэша
        3. test_get_seasons_http_error — мок HttpError 500, return None
        4. test_get_seasons_season_null_image — сезон с image=null → poster_url=""
        5. test_get_seasons_season_null_number — элемент с number=None пропускается
        6. test_get_seasons_empty_list — пустой массив → return []
  Context: Моки: patch _http.get_json. Кэш: чистить _seasons_cache перед каждым тестом.
           Аналогично существующим тестам для get_episodes (если есть).
  Depends on: T-02
  Verify: cd shared && python -m pytest tests/ -v
  Live test: не требуется (unit-тесты)
  Status: [✓] done
```

```
T-10 [sonnet] — Написать тесты для _apply_season_art()
  Traces to: AC-01, AC-02, AC-03, AC-04, AC-05, AC-06
  File: metadata.tvshows.ums/tests/test_season_art.py (новый файл)
  Task: Написать unit-тесты:
        1. test_apply_season_art_success — мок lookup_show + get_seasons,
           проверить addSeason и addAvailableArtwork вызваны
        2. test_apply_season_art_tvmaze_disabled — use_tvmaze=false → ничего не вызвано
        3. test_apply_season_art_season_art_disabled — use_season_art=false → ничего не вызвано
        4. test_apply_season_art_no_imdb_id — imdb_id="" → ничего не вызвано
        5. test_apply_season_art_show_not_found — lookup_show returns None → ничего не сломалось
        6. test_apply_season_art_seasons_error — get_seasons returns None → graceful degradation
        7. test_apply_season_art_season_without_poster — season с poster_url="" → addSeason вызван,
           addAvailableArtwork НЕ вызван
  Context: Моки: TvmazeClient (lookup_show, get_seasons), SettingsManager (use_tvmaze, use_season_art),
           infotag (MagicMock с addSeason, addAvailableArtwork).
           Аналогично существующим тестам в tests/.
  Depends on: T-06
  Verify: cd metadata.tvshows.ums && python -m pytest tests/ -v
  Live test: не требуется (unit-тесты)
  Status: [✓] done
```

---

## Порядок выполнения

```
Параллельно: T-01, T-03, T-04, T-05 (независимые)
      ↓
T-02 (зависит от T-01)
T-08 (зависит от T-01)
      ↓
T-06 (зависит от T-01, T-02, T-03)
      ↓
T-07 (зависит от T-06)
      ↓
Параллельно: T-09 (зависит от T-02), T-10 (зависит от T-06)
```

## Граф зависимостей

```
T-01 ─┬──→ T-02 ──→ T-09
      ├──→ T-08
      └──→ T-06 ──→ T-07
T-03 ──┘        └──→ T-10
T-04 (независимая)
T-05 (независимая)
```

## Результаты полного test suite (Phase 4.1)

- **TV scraper:** 145 passed, 0 failed
- **Shared:** 6 passed, 0 failed  
- **Movie scraper:** 564 passed, 6 failed (pre-existing: Wikidata live-тесты, сетевые)
- **New failures:** 0
- **Критерий закрытия:** выполнен
