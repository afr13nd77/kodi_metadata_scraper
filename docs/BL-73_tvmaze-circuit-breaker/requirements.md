# BL-73: Circuit breaker и кэширование lookup для TVMaze

## 1.1 Обзор

При недоступности api.tvmaze.com (SSL handshake timeout) сканирование 2 серий занимает ~5 минут вместо ~20 секунд. Причина: каждый вызов TVMaze делает 3 retry по ~6 сек, а на один эпизод приходится 6 HTTP-запросов (3 функции × 2 попытки: lookup + search fallback). Нет механизма прекращения попыток после первого полного провала.

## 1.2 User Stories

```
US-01: Как пользователь, я хочу чтобы сканирование сериала не зависало на минуты,
       когда TVMaze недоступен, а продолжало работу с данными из Kinopoisk и OMDb.

US-02: Как пользователь, я хочу чтобы при доступном TVMaze скрапер не делал
       лишних HTTP-запросов для одного и того же сериала.
```

## 1.3 Требования

### R-01: Circuit breaker для TVMaze (CRITICAL)

После N последовательных неудачных HTTP-вызовов к TVMaze — автоматически пропускать все оставшиеся вызовы в текущей сессии скрапера (один invocation Python).

- N = 2 (два полных провала = 6 retry — достаточно для уверенности)
- Счётчик — модульная переменная в `tvmaze_client.py` (thread-safe)
- Успешный вызов сбрасывает счётчик
- При срабатывании circuit breaker логировать WARNING один раз
- Все методы TvmazeClient должны проверять circuit breaker до HTTP-вызова
- Возвращать fallback-значения (None, "", ([], []), ("", "")) без сетевого вызова

### R-02: Рефакторинг get_show_status — использовать lookup_show (HIGH)

`get_show_status()` делает прямой `self._http.get_json("/lookup/shows?imdb=...")`, обходя `lookup_show()` и его `_show_cache`. Нужно:

- Переписать на использование `lookup_show()` + `search_show()` для получения show_id
- Отдельным вызовом получать полные данные шоу (или сохранять status из lookup response)
- Кэшировать результат в `_status_cache` (уже есть)

### R-03: Рефакторинг get_tvdb_id — использовать lookup_show (HIGH)

Аналогичная проблема: `get_tvdb_id()` делает прямой HTTP-вызов, обходя кэш. Нужно:

- Переписать на использование `lookup_show()` + `search_show()` для получения show_id
- Для TVDB ID: хранить полный response в кэше или делать отдельный вызов по show_id
- Устранить дублирование HTTP-вызовов с `lookup_show()`

### R-04: Кэширование полного TVMaze response (MEDIUM)

`lookup_show()` сейчас возвращает только show_id (int), а `get_show_status` и `get_tvdb_id` нуждаются в полном JSON-ответе (status, externals.thetvdb). Варианты:

- Кэшировать полный response в отдельном dict `_show_data_cache`
- Или расширить `lookup_show()` чтобы возвращал весь dict, а show_id извлекался позже

Выбор подхода: кэширование полного response (минимальные изменения API).

## 1.4 Acceptance Criteria

```
AC-01 (R-01):
  GIVEN: TVMaze API недоступен (timeout на всех запросах)
  WHEN: сканируется сериал с 2 эпизодами, use_tvmaze=true
  THEN: после 2 полных провалов все последующие вызовы TVMaze пропускаются
        AND в логе появляется WARNING "circuit breaker tripped"
        AND сканирование завершается без 5-минутного ожидания

AC-02 (R-02, R-03):
  GIVEN: TVMaze API доступен
  WHEN: вызываются get_show_status() и get_tvdb_id() для одного imdb_id
  THEN: lookup HTTP-запрос делается максимум 1 раз (второй берётся из кэша)

AC-03 (R-01):
  GIVEN: TVMaze API доступен
  WHEN: сканируется сериал с эпизодами
  THEN: circuit breaker не срабатывает, все TVMaze данные получены
        AND счётчик неудач = 0

AC-04 (R-04):
  GIVEN: вызван get_show_status(), затем get_tvdb_id() для того же imdb_id
  WHEN: TVMaze доступен
  THEN: второй вызов не делает HTTP-запрос к TVMaze (берёт из кэша full response)
```

## 1.5 Вне скоупа

- Изменение timeout'ов HTTP-клиента (5 сек — адекватно)
- Изменение количества retry (3 — адекватно)
- Persistent circuit breaker (между запусками Kodi) — не нужен, каждая сессия начинается чистой

## 1.6 Зависимости

- `shared/tvmaze_client.py` — основной файл изменений
- `shared/http_client.py` — без изменений (circuit breaker на уровне клиента TVMaze, не HTTP)
- `metadata.tvshows.ums/tests/test_tvmaze_client.py` — новые тесты
