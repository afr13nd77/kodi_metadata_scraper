# BL-72: Публикация в официальный репозиторий Kodi — Задачи

## Автоматизируемые задачи

T-01 [opus] — Иконки без прозрачности
  Traces to: R-01, AC-01
  Files: metadata.ums/icon.png, metadata.tvshows.ums/icon.png
  Task: Сохранить копии текущих иконок как icon_transparent.png. Добавить чёрный фон (#000000) под существующее изображение, сохранить как icon.png (512x512, PNG, без альфа-канала).
  Context: kodi-addon-checker выдаёт ERROR "icon should be solid. It has transparency". Пользователь выбрал чёрный фон.
  Depends on: нет
  Verify: kodi-addon-checker metadata.ums --branch nexus | grep -i "icon"
  Live test: визуальная проверка icon.png — фон чёрный, изображение сохранено
  Status: [✓] done

T-02 [opus] — Дополнить addon.xml обязательными полями
  Traces to: R-02, R-05, AC-02
  Files: metadata.ums/addon.xml, metadata.tvshows.ums/addon.xml
  Task: Внутри `<extension point="xbmc.addon.metadata">` добавить: `<license>MIT</license>`, `<platform>all</platform>`, `<source>https://github.com/afr13nd77/kodi_metadata_scraper</source>`, `<website>https://github.com/afr13nd77/kodi_metadata_scraper</website>`, `<news>` с кратким changelog v3.24.0. Поле `<forum>` оставить пустым (заполнится после создания темы). Также обновить xbmc.python 3.0.0 → 3.0.1.
  Context: kodi-addon-checker и эталон metadata.themoviedb.org.python требуют эти поля. forum пока пустой — пользователь создаст тему вручную.
  Depends on: нет
  Verify: kodi-addon-checker metadata.ums --branch nexus (0 errors)
  Live test: xmllint --noout addon.xml
  Status: [✓] done

T-03 [opus] — Создать changelog.txt
  Traces to: R-03, AC-02
  Files: metadata.ums/changelog.txt, metadata.tvshows.ums/changelog.txt
  Task: Создать changelog.txt в корне каждого аддона. Plain text, последние 5 версий. Для movie — из CHANGELOG.md (v3.24.0..v3.22.0). Для TV — те же версии, но с фокусом на TV-релевантные изменения.
  Context: Официальный репозиторий Kodi требует changelog.txt. CHANGELOG.md есть в корне проекта — использовать как источник.
  Depends on: нет
  Verify: файл существует, содержит версии
  Live test: cat metadata.ums/changelog.txt
  Status: [✓] done

T-04 [opus] — Исключить .gitkeep из сборки
  Traces to: R-06, AC-03
  File: build_zip.py
  Task: Добавить `.gitkeep` в EXCLUDE_EXTENSIONS или отдельный EXCLUDE_FILES set. Текущие исключения (tests, __pycache__, .pytest_cache, .claude, *.pyc) уже покрывают основное.
  Context: checker предупреждает о .gitkeep в tests/fixtures/. tests/ уже исключена из ZIP, но .gitkeep может попасть из других мест.
  Depends on: нет
  Verify: python build_zip.py && распаковать ZIP, проверить отсутствие .gitkeep
  Live test: zipinfo metadata.ums-3.24.0.zip | grep -i gitkeep
  Status: [✓] done

## Ручные задачи (пользователь)

T-05 [user] — Создать тему на Kodi Forum
  Traces to: R-04
  Task: Создать тему в Add-on Development → Add-on WIP. Описание, скриншоты, ссылка на GitHub.
  Status: [ ] pending

T-06 [user] — Заполнить <forum> URL в addon.xml
  Traces to: R-02
  Task: После T-05 вставить URL темы в оба addon.xml в поле <forum>.
  Depends on: T-05
  Status: [ ] pending

T-07 [user] — Fork xbmc/repo-plugins и создать PR
  Traces to: R-08, AC-04
  Task: Fork repo, ветка nexus, два PR (по одному на аддон).
  Depends on: T-01..T-04, T-06
  Status: [ ] pending
