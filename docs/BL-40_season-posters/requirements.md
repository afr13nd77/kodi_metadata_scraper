# BL-40 + BL-63: Сезонные постеры и названия сезонов

**Дата:** 17.07.2026
**Статус:** draft
**Версия скрапера:** 3.17.2 (TV)

---

## 1.1 Обзор

Добавить поддержку сезонных постеров и названий сезонов в TV scraper. Сейчас UMS не передаёт Kodi информацию о сезонах — папки сезонов остаются без постеров и без названий. Kodi поддерживает нативные API `addSeason(number, name)` и `addAvailableArtwork(url, arttype, season=number)` для этого.

**Кто пользователь?** Пользователь Kodi с библиотекой сериалов, который видит пустые папки сезонов (без постеров) и безымянные заголовки "Season 1" вместо оригинальных названий.

**Какую проблему решаем?** При сканировании библиотеки папки сезонов отображаются без арта (серый значок или дефолтная иконка) и без содержательных названий. Для получения постеров пользователь вынужден вручную загружать изображения.

---

## 1.2 User Stories

```
US-01: Как пользователь Kodi, я хочу видеть постер для каждого сезона в библиотеке,
       чтобы навигация была визуально информативной.

US-02: Как пользователь Kodi, я хочу видеть название сезона (например, "Семья" для
       сезона 1 Silo), чтобы понимать тематику сезона без дополнительного поиска.

US-03: Как пользователь Kodi, я хочу управлять загрузкой сезонных постеров через
       настройки аддона, чтобы экономить API-квоту при необходимости.
```

---

## 1.3 User Flows

```
FLOW-01: Автоматическая загрузка сезонных постеров при сканировании
1. Kodi вызывает getdetails для сериала
2. Скрапер получает TVShowDetails от KP API
3. Скрапер определяет IMDB ID сериала (из KP или Wikidata)
4. Если настройка use_tvmaze = true И use_season_art = true:
   a. Скрапер запрашивает TVMaze GET /shows/{tvmaze_id}/seasons
   b. TVMaze возвращает массив сезонов с полями: number, name, image
   c. Для каждого сезона:
      → vtag.addSeason(number, name)
      → Если image не null: vtag.addAvailableArtwork(image.original, "poster", season=number)
   → SUCCESS: Kodi отображает постеры и названия сезонов
   d. При ошибке TVMaze API:
      → WARNING в лог, продолжить без сезонного арта
      → Остальные метаданные сериала не затрагиваются
5. Если use_tvmaze = false ИЛИ use_season_art = false:
   → Поведение без изменений (как сейчас)

FLOW-02: TVMaze не нашёл сериал
1. Kodi вызывает getdetails
2. Скрапер пытается lookup_show(imdb_id)
3. TVMaze возвращает 404
   → WARNING в лог: "TVMaze show not found for imdb_id=..."
   → Скрапер продолжает без сезонного арта
   → Остальные метаданные заполняются как обычно

FLOW-03: Сезон без изображения
1. TVMaze возвращает сезон с image = null (часто для Season 0 / Specials)
2. Скрапер вызывает vtag.addSeason(number, name) — название ставится
3. addAvailableArtwork НЕ вызывается для этого сезона
   → Kodi покажет название, но без постера (дефолтная иконка)
```

---

## 1.4 Acceptance Criteria

```
AC-01 (US-01):
  GIVEN: сериал с IMDB ID, use_tvmaze=true, use_season_art=true
  WHEN: Kodi вызывает getdetails
  THEN: для каждого сезона с image != null в TVMaze
        вызывается vtag.addAvailableArtwork(image_url, arttype="poster", season=number)
        AND постер сезона отображается в библиотеке Kodi

AC-02 (US-02):
  GIVEN: сериал с IMDB ID, use_tvmaze=true, use_season_art=true
  WHEN: Kodi вызывает getdetails
  THEN: для каждого сезона вызывается vtag.addSeason(number, name)
        AND в Kodi отображается название сезона из TVMaze

AC-03 (US-01):
  GIVEN: сериал с IMDB ID, use_tvmaze=true, use_season_art=true,
         TVMaze возвращает сезон с image=null
  WHEN: Kodi вызывает getdetails
  THEN: vtag.addSeason(number, name) вызывается (название есть)
        AND vtag.addAvailableArtwork НЕ вызывается для этого сезона

AC-04 (US-03):
  GIVEN: use_tvmaze=false ИЛИ use_season_art=false
  WHEN: Kodi вызывает getdetails
  THEN: TVMaze seasons API НЕ вызывается
        AND поведение идентично текущей версии

AC-05 (US-01):
  GIVEN: сериал без IMDB ID (нет ни в KP, ни в Wikidata)
  WHEN: Kodi вызывает getdetails
  THEN: TVMaze seasons API НЕ вызывается (невозможен lookup)
        AND WARNING в лог
        AND остальные метаданные загружаются как обычно

AC-06 (US-01):
  GIVEN: сериал с IMDB ID, use_tvmaze=true, use_season_art=true
  WHEN: TVMaze API возвращает ошибку (таймаут, 500, 429)
  THEN: WARNING в лог с описанием ошибки
        AND остальные метаданные загружаются как обычно (graceful degradation)

AC-07 (US-01):
  GIVEN: повторное сканирование сериала в течение TTL кэша
  WHEN: Kodi вызывает getdetails
  THEN: TVMaze seasons API НЕ вызывается повторно (данные из кэша)
```

---

## 1.5 Out of Scope

- Постеры сезонов из KP API (API не поддерживает per-season images)
- Сезонный fanart / banner / landscape (только poster)
- Постеры эпизодов (отдельная задача BL-41)
- Season 0 / Specials (отдельная задача BL-53)
- Кэширование ответов TVMaze на диск (используем in-memory кэш TvmazeClient)
- Ручной выбор постера сезона пользователем (нативная функция Kodi)

---

## 1.6 Зависимости

| Зависимость | Описание |
|:---|:---|
| TVMaze API | `GET /shows/{id}/seasons` — бесплатный, без ключа, rate limit 2 req/s |
| `TvmazeClient` | Существующий клиент (`shared/tvmaze_client.py`), нужен новый метод `get_seasons()` |
| `use_tvmaze` | Существующая настройка (по умолч. выкл.), переиспользуется как gate |
| `settings.xml` | Новая настройка `use_season_art` (по умолч. вкл. при use_tvmaze=true) |
| IMDB ID | Нужен для TVMaze lookup; берётся из KP или Wikidata fallback |
| Kodi API | `VideoInfoTag.addSeason(number, name)`, `addAvailableArtwork(url, arttype, season=N)` — доступны с Kodi v20 |

---

## Источник данных: TVMaze API

### Endpoint: `GET /shows/{id}/seasons`

Возвращает массив сезонов:
```json
[
  {
    "id": 1,
    "url": "...",
    "number": 1,
    "name": "Season 1",
    "episodeOrder": 10,
    "premiereDate": "2023-05-05",
    "endDate": "2023-06-30",
    "network": {...},
    "image": {
      "medium": "https://static.tvmaze.com/uploads/images/medium_portrait/...",
      "original": "https://static.tvmaze.com/uploads/images/original_untouched/..."
    },
    "summary": "..."
  },
  {
    "id": 2,
    "number": 2,
    "name": "",
    "image": null,
    ...
  }
]
```

**Ключевые поля:**
- `number` — номер сезона (int)
- `name` — название сезона (string, может быть пустым)
- `image.original` — полноразмерный постер (string или null)
- `image.medium` — превью постера для preview (string или null)

**Rate limit:** 2 запроса/секунду (уже настроено в `_tvmaze_limiter`).
