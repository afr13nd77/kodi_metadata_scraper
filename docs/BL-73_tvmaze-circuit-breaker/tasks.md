# BL-73: Задачи

## T-01 [opus] — Circuit breaker в TvmazeClient
  Traces to: US-01, AC-01, AC-03, R-01
  File: shared/tvmaze_client.py
  Task: Добавить circuit breaker механизм:
    1. Модульные переменные `_circuit_failures` (int) и `_circuit_open` (bool), защищённые `_tvmaze_cache_lock`
    2. Константа `_CIRCUIT_BREAKER_THRESHOLD = 2`
    3. Приватный метод `_check_circuit()` → bool (True = circuit open, skip call)
    4. Метод `_record_failure()` — инкрементирует счётчик, при >= threshold устанавливает `_circuit_open = True` и логирует WARNING один раз
    5. Метод `_record_success()` — сбрасывает `_circuit_failures = 0`, `_circuit_open = False`
    6. Интегрировать во все методы, делающие HTTP: lookup_show, search_show, search_imdb_id, get_show_status, get_episodes, get_seasons, get_episode_crew (HTTP часть)
    7. При circuit open — возвращать fallback: None для lookup_show/search_show/get_episodes/get_seasons, "" для get_show_status/search_imdb_id, ([], []) для get_episode_crew
  Context: Каждый неудачный вызов — 3 retry × ~6 сек timeout = ~18 сек. При 6 вызовах на эпизод = ~108 сек на эпизод впустую. Circuit breaker отсекает после 2 полных провалов (36 сек).
  Acceptance criteria: AC-01, AC-03
  Depends on: нет
  Status: [✓] done

## T-02 [opus] — Кэширование полного TVMaze response + рефакторинг get_show_status и get_tvdb_id
  Traces to: US-02, AC-02, AC-04, R-02, R-03, R-04
  File: shared/tvmaze_client.py
  Task:
    1. Добавить `_show_data_cache: dict[str, dict] = {}` — кэш полных JSON-ответов TVMaze по ключу imdb_id или name
    2. Константа `_TVMAZE_CACHE_MAX_SHOW_DATA = 20`
    3. В `lookup_show()`: после успешного HTTP-запроса сохранять полный response в `_show_data_cache[imdb_id]` (помимо show_id в `_show_cache`)
    4. В `search_show()`: аналогично сохранять response в `_show_data_cache[name]`
    5. Рефакторинг `get_show_status()`:
       - Сначала проверить `_show_data_cache` по ключу imdb_id/title
       - Если miss: вызвать `lookup_show()` (+ search_show() fallback) — это заполнит `_show_data_cache`
       - Достать status из `_show_data_cache`, не делая отдельный HTTP
       - Удалить прямые `self._http.get_json()` вызовы из этого метода
    6. Рефакторинг `get_tvdb_id()`:
       - Аналогично: проверить `_show_data_cache`, если miss — вызвать `lookup_show()` / `search_show()`
       - Достать externals.thetvdb из cached response
       - Удалить прямые `self._http.get_json()` вызовы
  Context: Сейчас `get_show_status()` и `get_tvdb_id()` делают независимые HTTP-вызовы в обход `lookup_show()`. Это не только дублирует запросы, но и обходит circuit breaker. После рефакторинга все HTTP-вызовы к TVMaze lookup пройдут через `lookup_show()` / `search_show()`, которые защищены circuit breaker'ом.
  Acceptance criteria: AC-02, AC-04
  Depends on: T-01 (circuit breaker должен быть на месте)
  Status: [✓] done

## T-03 [sonnet] — Тесты для circuit breaker и кэширования
  Traces to: AC-01, AC-02, AC-03, AC-04
  File: metadata.tvshows.ums/tests/test_tvmaze_client.py
  Task: Добавить тесты:
    1. `test_circuit_breaker_trips_after_threshold` — 2 провала → circuit open → последующие вызовы возвращают fallback без HTTP
    2. `test_circuit_breaker_resets_on_success` — успех после провала → circuit closed
    3. `test_circuit_breaker_does_not_trip_on_single_failure` — 1 провал → circuit still closed
    4. `test_get_show_status_uses_lookup_cache` — вызов get_show_status дважды для одного imdb_id → HTTP только 1 раз
    5. `test_get_tvdb_id_uses_lookup_cache` — аналогично для get_tvdb_id
    6. `test_get_show_status_after_lookup_show_no_extra_http` — сначала lookup_show, потом get_show_status → 0 доп. HTTP
    7. `test_circuit_breaker_all_methods_return_fallback` — при circuit open проверить fallback-значения всех методов
  Context: Мокать `HttpClient.get_json` через `unittest.mock.patch`. Не забывать сбрасывать модульные переменные (_circuit_failures, _circuit_open, _show_cache, _show_data_cache) в setUp/tearDown.
  Acceptance criteria: AC-01, AC-02, AC-03, AC-04
  Depends on: T-01, T-02
  Status: [✓] done

## T-04 [haiku] — Обновить BACKLOG.md и CHANGELOG.md
  File: BACKLOG.md, CHANGELOG.md
  Task: Добавить BL-73 в бэклог (секция 6 Performance, новый пункт), отметить как реализованный. Обновить CHANGELOG.
  Depends on: T-01, T-02, T-03
  Status: [✓] done
