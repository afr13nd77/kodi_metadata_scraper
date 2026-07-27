# BL-70 — Technical Design: Язык имён актёров (ru / en)

## Статус: approved
## Версия: v3.19.0
## Дата: 27.07.2026

---

## 1. Архитектура

### 1.1 Затрагиваемые модули

| Модуль | Файл | Тип изменения |
|--------|------|---------------|
| Person model | `shared/models.py` | Добавить метод `display_name(lang)` |
| Settings Manager | `shared/settings_manager.py` | Новый property `actor_name_language` |
| NFO Writer | `shared/nfo_writer.py` | Передать `settings` в `_build_common_elements`, использовать `display_name()` |
| Movie Scraper | `metadata.ums/python/scraper.py` | Использовать `display_name()` вместо `name_ru` |
| TV Scraper | `metadata.tvshows.ums/python/tv_scraper.py` | Использовать `display_name()` вместо `name_ru` |
| Settings XML (movie) | `metadata.ums/resources/settings.xml` | Новая настройка `actor_name_language` |
| Settings XML (TV) | `metadata.tvshows.ums/resources/settings.xml` | Новая настройка `actor_name_language` |
| Strings EN (movie) | `metadata.ums/resources/language/resource.language.en_gb/strings.po` | Label-ы 32260-32263 |
| Strings RU (movie) | `metadata.ums/resources/language/resource.language.ru_ru/strings.po` | Label-ы 32260-32263 |
| Strings EN (TV) | `metadata.tvshows.ums/resources/language/resource.language.en_gb/strings.po` | Label-ы 32260-32263 |
| Strings RU (TV) | `metadata.tvshows.ums/resources/language/resource.language.ru_ru/strings.po` | Label-ы 32260-32263 |

### 1.2 Модули без изменений

| Модуль | Почему не меняется |
|--------|-------------------|
| `shared/kinopoisk_api.py` | Парсинг `name_ru` / `name_en` уже корректен (строки 513-514) |
| `shared/nfo_parser.py` | При чтении NFO имя всегда попадает в `name_ru` — это корректно, NFO содержит имя на том языке, на котором его записали |
| `shared/cache.py` | Кэшируется сырой JSON, выбор языка на этапе вывода |
| `shared/http_client.py` | Без изменений |

### 1.3 Data Flow

```
KP API (/v1/staff)
  │
  ▼
kinopoisk_api.parse_staff()
  │  name_ru = staff["nameRu"] or staff["nameEn"]
  │  name_en = staff["nameEn"] or ""
  ▼
Person(name_ru=..., name_en=...)
  │
  ├──► scraper.py / tv_scraper.py
  │      settings.actor_name_language → "ru" | "en"
  │      person.display_name(lang) → выбор имени
  │      │
  │      ├──► xbmc.Actor(display_name, role, order, photo_url)
  │      ├──► infotag.setDirectors([display_name, ...])
  │      └──► infotag.setWriters([display_name, ...])
  │
  └──► nfo_writer._build_common_elements()
         settings.actor_name_language → "ru" | "en"
         person.display_name(lang) → выбор имени
         │
         ├──► <director>display_name</director>
         ├──► <credits>display_name</credits>
         └──► <actor><name>display_name</name>...</actor>
```

---

## 2. Конкретные изменения

### 2.1 `shared/models.py` — метод `Person.display_name()`

**Решение**: Добавить метод в dataclass `Person`, а не внешний helper в `utils.py`.

**Обоснование**: Логика выбора имени привязана к данным самого Person (его полям `name_ru`, `name_en`). Метод dataclass делает код самодокументируемым и избавляет от необходимости импортировать дополнительный модуль. Все потребители Person (scraper, tv_scraper, nfo_writer) уже импортируют модель.

**Альтернатива (отвергнута)**: Функция `get_display_name(person, lang)` в `shared/utils.py`. Минусы: лишний импорт, разрыв между данными и логикой, utils.py уже содержит несвязанный код (fuzzy matching, транслитерация).

**Изменение** (после строки 52, внутри класса Person):

```python
def display_name(self, lang: str = "ru") -> str:
    """Return person name for the given language with fallback.

    Args:
        lang: "ru" or "en"

    Returns:
        name_en if lang=="en" and name_en is not empty, otherwise name_ru.
    """
    if lang == "en" and self.name_en:
        return self.name_en
    return self.name_ru
```

**Поведение**:
- `lang="ru"` → всегда `name_ru` (текущее поведение, обратная совместимость)
- `lang="en"` + `name_en` непустой → `name_en`
- `lang="en"` + `name_en` пустой → `name_ru` (fallback, AC-03)

### 2.2 `shared/settings_manager.py` — property `actor_name_language`

**Паттерн**: аналогичен `genre_language` (строки 72-74). Используется тот же `_GENRE_LANGUAGE_MAP` (0→"ru", 1→"en"), так как значения идентичны.

**Изменение** (после строки 74, после property `genre_language`):

```python
@property
def actor_name_language(self) -> str:
    value = self._addon.getSettingInt("actor_name_language")
    return self._GENRE_LANGUAGE_MAP.get(value, "ru")
```

**Примечание**: Переиспользование `_GENRE_LANGUAGE_MAP` допустимо — карта {0: "ru", 1: "en"} универсальна для любого language-toggle. Если в будущем появится третий язык, можно создать отдельный map.

### 2.3 `metadata.ums/python/scraper.py` — выбор имени (строки 782-793)

**Текущий код** (строки 782-793):
```python
infotag.setDirectors([p.name_ru for p in details.directors])
infotag.setWriters([p.name_ru for p in details.writers])

kodi_cast = []
for person in details.cast:
    kodi_cast.append(xbmc.Actor(
        person.name_ru,
        person.role,
        person.order,
        person.photo_url
    ))
```

**Новый код**:
```python
actor_lang = settings.actor_name_language

infotag.setDirectors([p.display_name(actor_lang) for p in details.directors])
infotag.setWriters([p.display_name(actor_lang) for p in details.writers])

kodi_cast = []
for person in details.cast:
    kodi_cast.append(xbmc.Actor(
        person.display_name(actor_lang),
        person.role,
        person.order,
        person.photo_url
    ))
```

**Примечание**: `settings` уже доступен в контексте вызова (передаётся как аргумент функции). Переменная `actor_lang` читается один раз и переиспользуется — нет лишних вызовов `getSettingInt`.

### 2.4 `metadata.tvshows.ums/python/tv_scraper.py` — выбор имени (строки 1177-1188)

**Изменение**: идентично 2.3 — те же самые строки, тот же паттерн. Код полностью зеркальный.

**Текущий код** (строки 1177-1188):
```python
infotag.setDirectors([p.name_ru for p in details.directors])
infotag.setWriters([p.name_ru for p in details.writers])

kodi_cast = []
for person in details.cast:
    kodi_cast.append(xbmc.Actor(
        person.name_ru,
        person.role,
        person.order,
        person.photo_url
    ))
```

**Новый код** — аналогичен 2.3 (с `actor_lang = settings.actor_name_language`).

### 2.5 `shared/nfo_writer.py` — передача настройки в XML-билдер

#### 2.5.1 Изменение сигнатур

Текущая цепочка вызовов:
```
write_movie_nfo(details, file_path, settings, logger)
  → _build_movie_xml(details, logger)           # settings не передаётся
    → _build_common_elements(root, details, logger)
```

`settings` уже есть в `write_movie_nfo` / `write_tvshow_nfo`, но не пробрасывается в `_build_movie_xml` → `_build_common_elements`. Нужно добавить параметр `settings` в цепочку.

**Изменения сигнатур**:

```python
# строка 46: вызов _build_movie_xml
xml_content = _build_movie_xml(details, settings, logger)

# строка 88: вызов _build_tvshow_xml
xml_content = _build_tvshow_xml(details, settings, logger)

# строка 105: сигнатура _build_movie_xml
def _build_movie_xml(details: MovieDetails, settings: SettingsManager, logger: Logger | None = None) -> str:

# строка 108: вызов _build_common_elements
_build_common_elements(root, details, settings, logger)

# строка 115: сигнатура _build_tvshow_xml
def _build_tvshow_xml(details: TVShowDetails, settings: SettingsManager, logger: Logger | None = None) -> str:

# строка 118: вызов _build_common_elements
_build_common_elements(root, details, settings, logger)

# строка 122: сигнатура _build_common_elements
def _build_common_elements(
    parent: ET.Element,
    details: "MovieDetails | TVShowDetails",
    settings: SettingsManager,
    logger: Logger | None = None,
) -> None:
```

#### 2.5.2 Использование `display_name()` в `_build_common_elements`

**Текущий код** (строки 198-211):
```python
for person in details.directors:
    ET.SubElement(parent, "director").text = person.name_ru

for person in details.writers:
    ET.SubElement(parent, "credits").text = person.name_ru

for person in details.cast:
    actor_elem = ET.SubElement(parent, "actor")
    ET.SubElement(actor_elem, "name").text = person.name_ru
    ...
```

**Новый код**:
```python
actor_lang = settings.actor_name_language

for person in details.directors:
    ET.SubElement(parent, "director").text = person.display_name(actor_lang)

for person in details.writers:
    ET.SubElement(parent, "credits").text = person.display_name(actor_lang)

for person in details.cast:
    actor_elem = ET.SubElement(parent, "actor")
    ET.SubElement(actor_elem, "name").text = person.display_name(actor_lang)
    ...
```

### 2.6 Settings XML — оба аддона

#### 2.6.1 Label ID allocation

Используемые ID:
- 32001-32014: API-ключи
- 32100-32193: Метаданные (последний: 32193 = "English" для genre_language)
- 32200-32251: Расширенные + кэш + NFO + дубликаты + трейлеры

**Следующий свободный диапазон в категории Metadata**: 32260-32263.

| ID | EN | RU |
|----|----|----|
| 32260 | Person name language | Язык имён (актёры, режиссёры) |
| 32261 | Language for actor, director, and writer names. English improves compatibility with other scrapers (TMDb, TVDB) | Язык отображения имён актёров, режиссёров и сценаристов. Английский улучшает совместимость с другими скраперами (TMDb, TVDB) |
| 32262 | Russian | Русский |
| 32263 | English | English |

**Примечание**: Значения 32262/32263 совпадают с 32192/32193 (genre_language), но переиспользовать нельзя — Kodi привязывает `<formatlabel>` / `<option label>` к контексту конкретного setting, и при будущей локализации на третий язык тексты могут разойтись.

#### 2.6.2 XML для `metadata.ums/resources/settings.xml`

Вставить новый `<group>` после `genre_language` (group `3g`, строка 98) и перед `enable_nfo_export` (group `3h`, строка 99):

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

**Размещение**: между `</group>` (строка 98, конец group 3g/genre_language) и `<group id="3h">` (строка 99, enable_nfo_export). Group ID `3ga` — между `3g` и `3h`, соответствует паттерну проекта (3ca, 3d, 3e...).

#### 2.6.3 XML для `metadata.tvshows.ums/resources/settings.xml`

Аналогичная вставка после group `3g` (строка 108) и перед group `3h` (строка 109). Тот же XML-блок с group id `3ga`.

### 2.7 Strings.po — все 4 файла

#### `metadata.ums/resources/language/resource.language.en_gb/strings.po`

Добавить в конец файла:
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

#### `metadata.ums/resources/language/resource.language.ru_ru/strings.po`

Добавить в конец файла:
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

#### TV-аддон (`metadata.tvshows.ums`) — оба языка

Тот же набор строк 32260-32263 добавляется в оба файла strings.po TV-аддона по аналогии.

---

## 3. Технические решения и альтернативы

### 3.1 Метод в dataclass vs. helper-функция

| Критерий | `Person.display_name()` | `get_display_name(person, lang)` в utils.py |
|----------|------------------------|---------------------------------------------|
| Инкапсуляция | Данные + логика вместе | Разрыв данные/логика |
| Импорты | Не нужен доп. импорт | Нужен `from utils import get_display_name` |
| Тестируемость | `Person("Иван", "Ivan").display_name("en")` | `get_display_name(Person("Иван", "Ivan"), "en")` |
| Расширяемость | Можно добавить логику в Person | utils.py захламляется |
| Совместимость с Python 3.8 | Dataclass поддерживает методы | N/A |

**Выбор**: `Person.display_name()` — чище, проще, не засоряет utils.py.

### 3.2 Один spinner вместо трёх отдельных

Требования (раздел 1.5 Out of Scope) явно исключают раздельные настройки для актёров, режиссёров и сценаристов. Одна настройка `actor_name_language` управляет языком для всех трёх типов Person.

### 3.3 Переиспользование `_GENRE_LANGUAGE_MAP`

Map `{0: "ru", 1: "en"}` одинаков для `genre_language` и `actor_name_language`. Создание второго идентичного map — бессмысленная дупликация. Если в будущем значения разойдутся (добавится третий язык жанров, но не имён), создать отдельный map будет тривиально.

---

## 4. Security & Edge Cases

### 4.1 Fallback при пустом `name_en`

KP API часто возвращает пустой `nameEn` для малоизвестных российских актёров. `display_name("en")` всегда возвращает `name_ru` если `name_en` пустой — имя никогда не будет пустой строкой (AC-03).

### 4.2 Fallback при пустом `name_ru`

Теоретически `name_ru` тоже может быть пустым, если API вернул только `nameEn`. Парсинг в `kinopoisk_api.py` (строка 513) уже обрабатывает это:
```python
name_ru=staff.get("nameRu", "") or staff.get("nameEn", ""),
```
Если `nameRu` пустой, `name_ru` заполняется из `nameEn`. Таким образом, `name_ru` всегда содержит хотя бы одно имя.

### 4.3 Default value = "ru"

При первой установке или обновлении, когда `actor_name_language` отсутствует в настройках, `getSettingInt` вернёт `0`, что map-ится в `"ru"`. Поведение идентично текущему — имена на русском (AC-02, AC-06).

### 4.4 Некорректное значение настройки

Если `getSettingInt` вернёт значение вне map (например, -1 или 99 из-за повреждённых настроек), `.get(value, "ru")` вернёт `"ru"` по умолчанию. Безопасный fallback.

### 4.5 Логирование fallback-а

По AC-03 требуется логирование предупреждения при пустом `name_en`. Это можно реализовать в вызывающем коде (scraper / nfo_writer), а не в `display_name()`, чтобы метод оставался чистой функцией без side effects:

```python
actor_lang = settings.actor_name_language
for person in details.cast:
    name = person.display_name(actor_lang)
    if actor_lang == "en" and not person.name_en:
        logger.debug(
            f"actor name fallback to ru: "
            f"name_ru={person.name_ru} source_id={person.source_id}"
        )
```

**Решение**: логирование fallback-а реализуется в scraper.py и tv_scraper.py, уровень `debug` (не `warning` — это ожидаемое поведение, не ошибка). NFO writer: аналогично, через `logger.debug` в `_build_common_elements`.

### 4.6 Производительность

`display_name()` — простой if/return, O(1). На фильм с 50 актёрами = 50 вызовов, пренебрежимо мало.

---

## 5. NFO Roundtrip

### 5.1 Запись (write)

NFO writer записывает имя на выбранном языке (`display_name(actor_lang)`). В XML-теги `<director>`, `<credits>`, `<actor><name>` попадает конкретное имя — русское или английское.

### 5.2 Чтение (read)

`nfo_parser.py` при чтении NFO всегда записывает имя в `Person.name_ru` (строки 163-164, 207, 215):
```python
person = Person(name_ru=name_elem.text.strip())
```

Это корректно и не требует изменений:
- NFO — flat формат, не хранит оба варианта имени одновременно.
- При чтении NFO мы не знаем, на каком языке записано имя — это просто текст.
- `name_ru` в данном контексте — это "основное имя", а не "русское имя". Переименование поля выходит за scope BL-70.
- При последующей пересканировке через KP API оба поля (`name_ru`, `name_en`) заполнятся заново из API.

### 5.3 Сценарий переключения языка

1. Пользователь скрапит с `actor_name_language=ru` → NFO содержит "Брэд Питт"
2. Пользователь переключает на `en` → при пересканировании NFO перезаписывается (если `nfo_overwrite=true`) с "Brad Pitt"
3. Если `nfo_overwrite=false` — старый NFO сохраняется с русским именем. Это ожидаемое поведение: настройка overwrite контролирует перезапись.

**Важно**: Kodi использует данные из infotag (из xbmc.Actor), а не из NFO-файлов. NFO — это бэкап/портабельность. Переключение языка начнёт работать сразу при пересканировании, даже если NFO не перезаписан.

---

## 6. Integration Points

### 6.1 Связь с `genre_language`

Настройка `actor_name_language` **полностью независима** от `genre_language`. Пользователь может иметь жанры на русском и имена на английском или наоборот. Это разные use case:
- `genre_language=en` — для совместимости со Smart Playlists
- `actor_name_language=en` — для совместимости с другими скраперами (TMDb)

### 6.2 Связь с `fetch_actor_photos`

Настройка `actor_name_language` не влияет на загрузку фотографий. Фото привязано к объекту Person, а не к имени.

### 6.3 Связь с `enable_collections`

Коллекции используют `set_name` (название франшизы), не имена людей. Без влияния.

### 6.4 Связь с `enable_nfo_export`

Если NFO export отключён, настройка языка всё равно влияет на xbmc.Actor / setDirectors / setWriters (Kodi-метаданные). NFO writer проверяет `enable_nfo_export` до записи — без изменений этой логики.

---

## 7. Тестирование

### 7.1 Unit-тесты (новые)

| Тест | Модуль | Что проверяет |
|------|--------|---------------|
| `test_display_name_ru_default` | models | `Person("Иван", "Ivan").display_name()` == "Иван" |
| `test_display_name_ru_explicit` | models | `Person("Иван", "Ivan").display_name("ru")` == "Иван" |
| `test_display_name_en` | models | `Person("Иван", "Ivan").display_name("en")` == "Ivan" |
| `test_display_name_en_fallback` | models | `Person("Иван", "").display_name("en")` == "Иван" |
| `test_display_name_unknown_lang` | models | `Person("Иван", "Ivan").display_name("de")` == "Иван" |
| `test_actor_name_language_default` | settings_manager | `actor_name_language` == "ru" при default=0 |
| `test_actor_name_language_en` | settings_manager | `actor_name_language` == "en" при value=1 |
| `test_nfo_writer_actor_lang_en` | nfo_writer | NFO XML содержит английские имена |
| `test_nfo_writer_actor_lang_ru` | nfo_writer | NFO XML содержит русские имена (обратная совместимость) |

### 7.2 Существующие тесты

Существующие тесты в `metadata.ums/tests/` и `metadata.tvshows.ums/tests/` используют `person.name_ru` напрямую. Они не ломаются — метод `display_name()` добавляется, а поле `name_ru` остаётся.

Тесты NFO writer (`shared/tests/`) могут потребовать обновления, если мокают `_build_common_elements` или проверяют содержимое XML. При изменении сигнатуры `_build_movie_xml(details, settings, logger)` — тесты, вызывающие её, нужно обновить.

### 7.3 Live-тест

1. Установить скрапер в Kodi
2. Настройка `actor_name_language=ru` (по умолчанию) → скрапить фильм → проверить что имена на русском
3. Переключить на `en` → пересканировать тот же фильм → проверить что имена на английском
4. Найти фильм с актёром без `nameEn` → убедиться в fallback на русское имя
5. Включить NFO export → убедиться что NFO содержит имена на выбранном языке

---

## 8. Порядок реализации

Рекомендуемая последовательность задач:

1. **T-01**: `Person.display_name()` в `shared/models.py` + unit-тесты
2. **T-02**: `actor_name_language` property в `shared/settings_manager.py`
3. **T-03**: Strings.po (все 4 файла) + settings.xml (оба аддона)
4. **T-04**: `shared/nfo_writer.py` — пробросить settings, использовать `display_name()`
5. **T-05**: `metadata.ums/python/scraper.py` — использовать `display_name()`
6. **T-06**: `metadata.tvshows.ums/python/tv_scraper.py` — использовать `display_name()`

T-01, T-02, T-03 можно выполнять параллельно.
T-04, T-05, T-06 зависят от T-01 и T-02.
