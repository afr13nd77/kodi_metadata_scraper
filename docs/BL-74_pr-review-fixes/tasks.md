# BL-74: Задачи

## T-01 [sonnet] — Подключить getartwork к диспатчеру movie scraper
  Traces to: BUG-01, AC-01
  File: metadata.ums/python/scraper.py
  Task: В функции `run()` (строка 219) добавить обработку action `"getartwork"`:
    ```python
    elif action == "getartwork":
        _handle_getartwork(params, handle, settings, logger)
        enddir = False
    ```
    Вставить между `elif action == "NfoUrl"` (строка 217) и `else:` (строка 219).
    `enddir = False` потому что `_handle_getartwork` сама вызывает `setResolvedUrl`.
  Context: `_handle_getartwork` (строка 901) уже реализована — получает постеры и фанарт через `kp_client.get_images()` и финализирует handle через `setResolvedUrl`. Нужно только подключить к диспатчеру.
  Acceptance criteria: AC-01
  Depends on: нет
  Verify: cd metadata.ums && python -m pytest tests/ -v -k "artwork or getartwork"
  Status: [✓] done

## T-02 [sonnet] — Убрать double-finalize в _handle_getdetails
  Traces to: BUG-02, AC-02
  File: metadata.ums/python/scraper.py
  Task: В `_handle_getdetails` убрать `setResolvedUrl` из ранних error-returns:
    1. Строки 381-382: убрать `xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem(offscreen=True))` перед `return False`
    2. Строки 386-387: аналогично убрать `setResolvedUrl`
    При `return False` → `enddir = True` → `endOfDirectory(handle)` вызовется автоматически — это единственный финализатор.
  Context: Текущий код вызывает и `setResolvedUrl` (внутри функции), и `endOfDirectory` (в `run()`) на один handle. Оставляем только `endOfDirectory` для error paths.
  Acceptance criteria: AC-02
  Depends on: нет
  Verify: cd metadata.ums && python -m pytest tests/ -v -k "getdetails"
  Status: [✓] done

## T-03 [sonnet] — Поменять порядок стратегий в _fallback_seasons_search
  Traces to: BUG-03, AC-03
  File: metadata.tvshows.ums/python/tv_scraper.py
  Task: В `_fallback_seasons_search` (строка 1096) поменять порядок стратегий:
    1. Сначала `imdb_id` lookup (текущие строки 1125-1140) — точный идентификатор
    2. Потом `title_original` search (текущие строки 1106-1123) — fuzzy, менее точный
    Просто вырезать блок imdb_id (строки 1125-1140) и вставить ПЕРЕД блоком title (строки 1106-1123).
  Context: Сейчас title search выполняется первой и может вернуть чужой сериал с таким же названием, игнорируя доступный IMDb ID. IMDb — уникальный идентификатор, должен быть приоритетнее.
  Acceptance criteria: AC-03
  Depends on: нет
  Verify: cd metadata.tvshows.ums && python -m pytest tests/ -v -k "fallback"
  Status: [✓] done

## T-04 [sonnet] — Тесты для всех трёх исправлений
  Traces to: AC-01, AC-02, AC-03
  Files:
    - metadata.ums/tests/test_scraper.py (или существующий файл тестов диспатчера)
    - metadata.tvshows.ums/tests/test_tv_scraper.py (или тесты fallback)
  Task:
    1. Тест: action="getartwork" → вызывается _handle_getartwork (mock, проверить вызов)
    2. Тест: _handle_getdetails с пустым kp_id → НЕ вызывает setResolvedUrl (mock, assert_not_called)
    3. Тест: _fallback_seasons_search с imdb_id и title → imdb стратегия используется первой
  Depends on: T-01, T-02, T-03
  Verify: python -m pytest metadata.ums/tests/ metadata.tvshows.ums/tests/ -v
  Status: [✓] done

## T-05 — Обновить PR в xbmc/repo-plugins
  Task: Пересобрать аддоны (shared → python/), обновить все 4 ветки в форке, force-push.
  Depends on: T-01, T-02, T-03, T-04
  Status: [✓] done

## T-06 — Обновить BACKLOG.md и CHANGELOG.md
  File: BACKLOG.md, CHANGELOG.md
  Depends on: T-01, T-02, T-03, T-04
  Status: [✓] done
