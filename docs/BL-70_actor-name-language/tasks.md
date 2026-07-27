# BL-70 — Tasks: Язык имён актёров (ru / en)

## Статус: done
## Версия: v3.19.0
## Дата: 27.07.2026

---

## Зависимости задач

```
T-01 (models)  ─┬──► T-04 (nfo_writer)
T-02 (settings) ┘
T-03 (settings.xml + strings.po) — независимая

T-01 + T-02 ──► T-05 (scraper) ──► T-07 (тесты scraper)
T-01 + T-02 ──► T-06 (tv_scraper) ──► T-08 (тесты tv_scraper)

[P] T-01, T-02, T-03 — параллельно
[P] T-05, T-06 — параллельно (после T-01 + T-02)
[P] T-07, T-08 — параллельно (после T-05, T-06)
```

---

## T-01 [sonnet] — Добавить метод `Person.display_name()` + unit-тесты

  Traces to: US-01, US-03, AC-01, AC-02, AC-03
  File: `shared/models.py` (строка 52, после `source_id`), `metadata.ums/tests/test_models.py`
  Task: Добавить метод `display_name(self, lang: str = "ru") -> str` в dataclass `Person` (после строки 52, перед пустой строкой 53). Логика:
  - `lang == "en"` и `self.name_en` непустой → вернуть `self.name_en`
  - Иначе → вернуть `self.name_ru`

  Добавить unit-тесты в `metadata.ums/tests/test_models.py` (новый класс `TestPersonDisplayName`):
  - `test_display_name_ru_default`: `Person("Иван", "Ivan").display_name()` == `"Иван"`
  - `test_display_name_ru_explicit`: `Person("Иван", "Ivan").display_name("ru")` == `"Иван"`
  - `test_display_name_en`: `Person("Иван", "Ivan").display_name("en")` == `"Ivan"`
  - `test_display_name_en_fallback_empty`: `Person("Иван", "").display_name("en")` == `"Иван"`
  - `test_display_name_unknown_lang`: `Person("Иван", "Ivan").display_name("de")` == `"Иван"`

  Context: `Person` dataclass на строках 44-52 `shared/models.py`. Уже содержит поля `name_ru` и `name_en`. Метод добавляется для выбора имени на основе настройки языка. Python 3.8 — нужен `from __future__ import annotations` (уже есть в файле).
  Acceptance criteria: AC-01 (en → name_en), AC-02 (ru → name_ru), AC-03 (en + пустой name_en → name_ru)
  Verify: `cd metadata.ums && python -m pytest tests/test_models.py::TestPersonDisplayName -v`
  Live test: нет (чистая логика, без зависимостей от Kodi)
  Depends on: нет
  Status: [✓] done

---

## T-02 [sonnet] — Добавить property `actor_name_language` в SettingsManager

  Traces to: US-01, US-02, AC-01, AC-02, AC-06
  File: `shared/settings_manager.py` (после строки 74, после property `genre_language`)
  Task: Добавить property `actor_name_language` по аналогии с `genre_language` (строки 71-74):
  ```python
  @property
  def actor_name_language(self) -> str:
      value = self._addon.getSettingInt("actor_name_language")
      return self._GENRE_LANGUAGE_MAP.get(value, "ru")
  ```
  Переиспользует существующий `_GENRE_LANGUAGE_MAP = {0: "ru", 1: "en"}`.

  Context: `SettingsManager` в `shared/settings_manager.py`. Карта `_GENRE_LANGUAGE_MAP` объявлена в классе (найти через grep). Паттерн property: строки 71-74 (`genre_language`). Тест: `metadata.ums/tests/test_scraper.py` содержит mock для `SettingsManager` — убедиться что `actor_name_language` замокан в conftest или тестах где нужно.
  Acceptance criteria: AC-06 (default=0 → "ru"), AC-01 (value=1 → "en")
  Verify: `cd metadata.ums && python -m pytest tests/ -v -k "settings"` (если есть тесты settings)
  Live test: нет (property, зависит от Kodi addon API)
  Depends on: нет
  Status: [✓] done

---

## T-03 [sonnet] — Настройка в settings.xml + strings.po (оба аддона)

  Traces to: US-01, US-02, AC-06
  Files:
  - `metadata.ums/resources/settings.xml` (после строки 98, между group `3g` и `3h`)
  - `metadata.tvshows.ums/resources/settings.xml` (после строки 108, между group `3g` и `3h`)
  - `metadata.ums/resources/language/resource.language.en_gb/strings.po` (в конец)
  - `metadata.ums/resources/language/resource.language.ru_ru/strings.po` (в конец)
  - `metadata.tvshows.ums/resources/language/resource.language.en_gb/strings.po` (в конец)
  - `metadata.tvshows.ums/resources/language/resource.language.ru_ru/strings.po` (в конец)

  Task:
  **settings.xml** — вставить новый group `3ga` после закрывающего `</group>` группы `3g` (genre_language) и перед `<group id="3h">` (enable_nfo_export). В обоих аддонах одинаковый блок:
  ```xml
      <group id="3ga">
        <setting id="actor_name_language" type="integer" label="32260" help="32261">
          <level>0</level>
          <default>0</default>
          <constraints>
            <options>
              <option label="32262">0</option>
              <option label="32263">1</option>
            </options>
          </constraints>
          <control type="spinner" format="string"/>
        </setting>
      </group>
  ```

  **strings.po** — добавить в конец каждого из 4 файлов строки 32260-32263:

  EN (оба аддона):
  ```
  msgctxt "#32260"
  msgid "Person name language"
  msgstr ""

  msgctxt "#32261"
  msgid "Language for actor, director, and writer names. English improves compatibility with other scrapers (TMDb, TVDB)"
  msgstr ""

  msgctxt "#32262"
  msgid "Russian"
  msgstr ""

  msgctxt "#32263"
  msgid "English"
  msgstr ""
  ```

  RU (оба аддона):
  ```
  msgctxt "#32260"
  msgid "Person name language"
  msgstr "Язык имён (актёры, режиссёры)"

  msgctxt "#32261"
  msgid "Language for actor, director, and writer names. English improves compatibility with other scrapers (TMDb, TVDB)"
  msgstr "Язык отображения имён актёров, режиссёров и сценаристов. Английский улучшает совместимость с другими скраперами (TMDb, TVDB)"

  msgctxt "#32262"
  msgid "Russian"
  msgstr "Русский"

  msgctxt "#32263"
  msgid "English"
  msgstr "English"
  ```

  Context: Паттерн настройки аналогичен `genre_language` (group `3g`, label 32190-32193). Последний используемый label ID: 32251 (трейлеры). Диапазон 32260-32263 свободен.
  Acceptance criteria: AC-06 (default=0 = русский)
  Verify: `ruff check metadata.ums/resources/ metadata.tvshows.ums/resources/` (XML — ruff не проверяет, но убедиться что файлы валидны)
  Live test: установить аддон в Kodi → Settings → Configure → секция «Метаданные» → появился spinner «Язык имён (актёры, режиссёры)» с вариантами Русский/English
  Depends on: нет
  Status: [✓] done

---

## T-04 [sonnet] — NFO Writer: использовать `display_name()` для имён

  Traces to: US-01, AC-04
  File: `shared/nfo_writer.py`
  Task: Пробросить `settings` через цепочку вызовов и использовать `person.display_name(actor_lang)` вместо `person.name_ru`.

  **Изменения сигнатур**:
  1. Строка 46: `xml_content = _build_movie_xml(details, logger)` → `xml_content = _build_movie_xml(details, settings, logger)`
  2. Строка 88: `xml_content = _build_tvshow_xml(details, logger)` → `xml_content = _build_tvshow_xml(details, settings, logger)`
  3. Строка 105: `def _build_movie_xml(details: MovieDetails, logger: Logger | None = None) -> str:` → `def _build_movie_xml(details: MovieDetails, settings, logger: Logger | None = None) -> str:`
  4. Строка 108: `_build_common_elements(root, details, logger)` → `_build_common_elements(root, details, settings, logger)`
  5. Строка 115: `def _build_tvshow_xml(details: TVShowDetails, logger: Logger | None = None) -> str:` → `def _build_tvshow_xml(details: TVShowDetails, settings, logger: Logger | None = None) -> str:`
  6. Строка 118: `_build_common_elements(root, details, logger)` → `_build_common_elements(root, details, settings, logger)`
  7. Строка 122-126: сигнатура `_build_common_elements` — добавить `settings` после `details`:
     ```python
     def _build_common_elements(
         parent: ET.Element,
         details: "MovieDetails | TVShowDetails",
         settings,
         logger: Logger | None = None,
     ) -> None:
     ```

  **Изменения в `_build_common_elements`**:
  8. Перед строкой 198 добавить: `actor_lang = settings.actor_name_language`
  9. Строка 199: `person.name_ru` → `person.display_name(actor_lang)`
  10. Строка 202: `person.name_ru` → `person.display_name(actor_lang)`
  11. Строка 206: `person.name_ru` → `person.display_name(actor_lang)`

  **Обновить тесты**: `metadata.ums/tests/test_nfo_writer.py` — все вызовы `_build_movie_xml(details, logger)` и `_build_tvshow_xml(details, logger)` нужно обновить, добавив mock `settings` с `actor_name_language = "ru"`. Добавить 2 новых теста:
  - `test_nfo_writer_actor_lang_en`: settings.actor_name_language="en" → XML содержит English имена
  - `test_nfo_writer_actor_lang_ru`: settings.actor_name_language="ru" → XML содержит русские имена

  Context: `settings` уже передаётся в `write_movie_nfo()` и `write_tvshow_nfo()` (параметр функции), но не пробрасывается дальше. NFO parser (`nfo_parser.py`) НЕ меняется — чтение всегда в `name_ru`.
  Acceptance criteria: AC-04
  Verify: `cd metadata.ums && python -m pytest tests/test_nfo_writer.py -v`
  Live test: включить NFO export + actor_name_language=en → скрапить фильм → открыть .nfo → имена на английском
  Depends on: T-01 (display_name), T-02 (settings property)
  Status: [✓] done

---

## T-05 [sonnet] — Movie Scraper: использовать `display_name()`

  Traces to: US-01, US-02, US-03, AC-01, AC-02, AC-03
  File: `metadata.ums/python/scraper.py` (строки 782-793)
  Task: Заменить `person.name_ru` на `person.display_name(actor_lang)` в трёх местах.

  **Изменения**:
  1. Перед строкой 782 добавить: `actor_lang = settings.actor_name_language`
  2. Строка 782: `[p.name_ru for p in details.directors]` → `[p.display_name(actor_lang) for p in details.directors]`
  3. Строка 783: `[p.name_ru for p in details.writers]` → `[p.display_name(actor_lang) for p in details.writers]`
  4. Строка 788: `person.name_ru,` → `person.display_name(actor_lang),`

  **Логирование fallback** (AC-03): после строки с setCast, добавить debug-лог для актёров без English имени:
  ```python
  if actor_lang == "en":
      no_en = [p for p in details.cast if not p.name_en]
      if no_en:
          logger.debug(
              f"_handle_getdetails: {len(no_en)} actors without English name, "
              f"fallback to Russian"
          )
  ```

  Context: `settings` доступен как переменная в scope функции `_handle_getdetails`. `logger` тоже доступен. `details` — объект `MovieDetails` со списками `directors`, `writers`, `cast` (все содержат `Person`).
  Acceptance criteria: AC-01, AC-02, AC-03
  Verify: `cd metadata.ums && python -m pytest tests/test_scraper.py -v`
  Live test: установить аддон → actor_name_language=en → скрапить фильм → в Kodi Information → имена актёров на английском
  Depends on: T-01 (display_name), T-02 (settings property)
  Status: [✓] done

---

## T-06 [sonnet] — TV Scraper: использовать `display_name()`

  Traces to: US-01, US-02, US-03, AC-01, AC-02, AC-03, AC-05
  File: `metadata.tvshows.ums/python/tv_scraper.py` (строки 1177-1188)
  Task: Зеркальные изменения к T-05.

  **Изменения**:
  1. Перед строкой 1177 добавить: `actor_lang = settings.actor_name_language`
  2. Строка 1177: `[p.name_ru for p in details.directors]` → `[p.display_name(actor_lang) for p in details.directors]`
  3. Строка 1178: `[p.name_ru for p in details.writers]` → `[p.display_name(actor_lang) for p in details.writers]`
  4. Строка 1183: `person.name_ru,` → `person.display_name(actor_lang),`

  **Логирование fallback**: аналогично T-05.

  Context: Код TV scraper зеркалит movie scraper в этом месте. `settings` и `logger` доступны в scope `_handle_getdetails`. `details` — объект `TVShowDetails`.
  Acceptance criteria: AC-05 (TV scraper идентичен movie scraper по поведению)
  Verify: `cd metadata.tvshows.ums && python -m pytest tests/test_tv_scraper.py -v`
  Live test: установить TV аддон → actor_name_language=en → скрапить сериал → в Kodi Information → имена на английском
  Depends on: T-01 (display_name), T-02 (settings property)
  Status: [✓] done

---

## T-07 [sonnet] — Тесты Movie Scraper: покрытие `actor_name_language`

  Traces to: AC-01, AC-02, AC-03
  File: `metadata.ums/tests/test_scraper.py`
  Task: Добавить тесты для поведения с `actor_name_language`. Новый класс `TestActorNameLanguage`:
  - `test_directors_use_english_names`: settings.actor_name_language="en", Person с name_en → setDirectors получает English имена
  - `test_directors_fallback_to_russian`: settings.actor_name_language="en", Person с name_en="" → setDirectors получает Russian имена
  - `test_actors_use_english_names`: settings.actor_name_language="en" → xbmc.Actor получает English имя
  - `test_default_russian_names`: settings.actor_name_language="ru" → всё на русском (обратная совместимость)

  Убедиться что mock `settings` в conftest/fixtures включает `actor_name_language` property (по умолчанию "ru") — иначе существующие тесты сломаются.

  Context: Тесты в `metadata.ums/tests/test_scraper.py` используют mock для SettingsManager. Прочитать `conftest.py` чтобы найти mock settings и добавить `actor_name_language`.
  Acceptance criteria: AC-01, AC-02, AC-03
  Verify: `cd metadata.ums && python -m pytest tests/test_scraper.py -v -k "ActorNameLanguage"`
  Live test: нет (unit-тесты)
  Depends on: T-05
  Status: [✓] done

---

## T-08 [sonnet] — Тесты TV Scraper: покрытие `actor_name_language`

  Traces to: AC-01, AC-02, AC-05
  File: `metadata.tvshows.ums/tests/test_tv_scraper.py`
  Task: Зеркальные тесты к T-07 для TV scraper. Новый класс `TestActorNameLanguage`:
  - `test_directors_use_english_names`
  - `test_actors_use_english_names`
  - `test_default_russian_names`

  Убедиться что mock `settings` в TV conftest включает `actor_name_language` property.

  Context: Зеркалит T-07 для TV. Прочитать `metadata.tvshows.ums/tests/conftest.py`.
  Acceptance criteria: AC-05
  Verify: `cd metadata.tvshows.ums && python -m pytest tests/test_tv_scraper.py -v -k "ActorNameLanguage"`
  Live test: нет (unit-тесты)
  Depends on: T-06
  Status: [✓] done
