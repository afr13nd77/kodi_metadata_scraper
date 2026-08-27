# BL-72: Публикация в официальный репозиторий Kodi

## 1.1 Обзор

Подготовка обоих аддонов (metadata.ums и metadata.tvshows.ums) к публикации в официальный репозиторий Kodi ([xbmc/repo-plugins](https://github.com/xbmc/repo-plugins)). Цель — сделать аддоны доступными для установки из стандартного менеджера аддонов Kodi без ручной загрузки ZIP.

**Целевой репозиторий:** `xbmc/repo-plugins`, ветки `nexus` (Kodi v20) и `omega` (Kodi v21).

## 1.2 User Stories

```
US-01: Как пользователь Kodi, я хочу установить UMS scraper из официального репозитория,
       чтобы не скачивать ZIP вручную и получать автоматические обновления.

US-02: Как разработчик, я хочу пройти ревью Team Kodi,
       чтобы аддоны были доступны максимальной аудитории.
```

## 1.3 Требования

### R-01: Иконки без прозрачности (BLOCKER)

Kodi addon checker требует solid background на icon.png. Текущие иконки обоих аддонов содержат прозрачные пиксели.

- Заменить icon.png (512x512) в `metadata.ums/` и `metadata.tvshows.ums/`
- Фон должен быть непрозрачным (solid color)
- Сохранить узнаваемость текущего дизайна

### R-02: Дополнить addon.xml обязательными полями (BLOCKER)

В оба addon.xml добавить внутри `<extension point="xbmc.addon.metadata">`:

| Поле | Значение |
|---|---|
| `<license>` | `MIT` |
| `<platform>` | `all` |
| `<source>` | `https://github.com/afr13nd77/kodi_metadata_scraper` |
| `<forum>` | URL темы на Kodi Forum (создаётся вручную, см. R-04) |
| `<website>` | `https://github.com/afr13nd77/kodi_metadata_scraper` |
| `<news>` | Краткий changelog текущей версии (текст) |

### R-03: Создать changelog.txt (BLOCKER)

Файл `changelog.txt` в корне каждого аддона (`metadata.ums/changelog.txt`, `metadata.tvshows.ums/changelog.txt`). Формат — plain text, краткий список изменений по версиям (последние 3-5 версий).

### R-04: Создать тему на Kodi Forum (BLOCKER, ручное действие)

Создать тему в разделе [Add-on Development -> Add-on WIP](https://forum.kodi.tv/forumdisplay.php?fid=26) с:
- Описание аддона
- Скриншоты из Kodi
- Ссылка на GitHub
- Инструкции по установке

URL темы вставляется в `<forum>` addon.xml.

### R-05: Обновить версию xbmc.python (HIGH)

В обоих addon.xml: `<import addon="xbmc.python" version="3.0.0"/>` -> `version="3.0.1"` (рекомендация checker-а для ветки nexus).

### R-06: Очистка мусорных файлов (HIGH)

Убедиться, что `build_zip.py` исключает:
- `__pycache__/`
- `.pytest_cache/`
- `.claude/`
- `.gitkeep`
- `*.pyc`
- `tests/` (тесты не должны попадать в дистрибутив для repo-plugins)

Также добавить `.gitignore` внутрь каждого аддона.

### R-07: Рефакторинг entry point (MEDIUM)

kodi-addon-checker предупреждает о сложности entry point (643 / 1113 строк vs лимит 15). Официальные аддоны используют тонкий entry point, который импортирует модули. Это warning, не error — может не блокировать PR, но улучшит шансы прохождения ревью.

### R-08: Подготовка PR (FINAL)

1. Fork `xbmc/repo-plugins`
2. Ветка `nexus` — создать папки `metadata.ums/` и `metadata.tvshows.ums/`
3. Один коммит на аддон: `[metadata.ums] 3.24.0`, `[metadata.tvshows.ums] 3.24.0`
4. Два отдельных PR — по одному на аддон
5. В описании PR: ссылка на тему форума, краткое описание, ссылка на GitHub

## 1.4 Acceptance Criteria

```
AC-01 (R-01):
  GIVEN: icon.png обоих аддонов
  WHEN: запускаем kodi-addon-checker
  THEN: нет ERROR про transparency

AC-02 (R-02, R-03, R-05):
  GIVEN: addon.xml и changelog.txt обоих аддонов
  WHEN: запускаем kodi-addon-checker --branch nexus
  THEN: 0 errors, минимум warnings

AC-03 (R-06):
  GIVEN: собранные ZIP-архивы
  WHEN: распаковываем и проверяем содержимое
  THEN: нет __pycache__, .pytest_cache, .claude, *.pyc, tests/

AC-04 (R-08):
  GIVEN: форк xbmc/repo-plugins
  WHEN: создаём PR с аддоном
  THEN: CI repo-plugins проходит без ошибок
```

## 1.5 Вне скоупа

- Поддержка ветки `matrix` (Kodi v19) — наш код требует Python 3.8+, matrix = Python 3
- Рефакторинг entry point на данном этапе — если ревьюеры потребуют, сделаем отдельной задачей
- Перевод addon.xml на 60+ языков — начинаем с en + ru, расширим по запросу

## 1.6 Зависимости

- Аккаунт на [forum.kodi.tv](https://forum.kodi.tv) (для создания темы)
- Аккаунт на GitHub с правами fork (есть: afr13nd77)
- Текущая стабильная версия аддонов без known bugs
