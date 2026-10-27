# AstroSynchro

Адаптивный прототип промосайта приложения знакомств и Django API для заявок
на бета-тест. Реализованы первый экран, переход к сцене приватности и форма
списка ожидания. Название, тексты и логотип временные; остальные разделы
полного ТЗ ещё предстоит подготовить.

Frontend и backend независимы: статическая версия работает без Django,
а отправка email включается только после настройки API и ссылки на реальную
политику обработки данных. Backend сохраняет email, дату согласия и редакцию
политики. Это список ожидания, а не аккаунт приложения: JWT, реальный чат,
видеозвонки и расчёт совместимости в этот этап не входят.

## Стек и структура

Frontend: HTML, CSS и JavaScript без сборщика. Backend: Python 3.12,
Django 5.2 LTS, Django REST Framework, PostgreSQL 18, psycopg и Gunicorn.
Зависимости закреплены в `backend/uv.lock`; для установки используется uv.
Проверки: Pytest, pytest-django и Ruff.

```text
dist/                  Статический сайт, форма, конфигурация и изображения
backend/config/        Настройки Django, маршруты и WSGI
backend/beta/          Модель заявки, API, сервис, ограничения и админка
backend/tests/         Тесты API, БД, согласия и доступа
backend/pyproject.toml Зависимости и настройки Pytest/Ruff
backend/uv.lock        Зафиксированные версии зависимостей
compose.yaml           PostgreSQL, подготовка Django, Gunicorn и Nginx
deploy/                Конфигурация Nginx и генерация frontend config.js
docs/                  Инструкция, контракт API, ревью и результаты проверок
```

## Только визуальный прототип

Из корня проекта, каталога `astro-prototype`:

```bash
python3 -m http.server 8081 --directory dist
```

Открыть `http://127.0.0.1:8081/`. В исходном `dist/config.js` оба значения
`apiBaseUrl` и `privacyPolicyUrl` равны `null`, поэтому форма не отправляет
контакты. Статический сервер не запускает API. Для просмотра сайта на Sites
Django также не требуется; для сбора заявок нужен отдельный хост backend.

## Настройка окружения

Создайте `.env` из шаблона, если файла ещё нет:

```bash
cp -n .env.example .env
python3 -c 'import secrets; print(secrets.token_urlsafe(64))'
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Первую строку запишите в `DJANGO_SECRET_KEY`, вторую — в `DB_PASSWORD`.
Файл `.env` содержит секреты и исключён из репозитория. Приём заявок оставьте
выключенным до согласования политики. Переменные, локальная PostgreSQL,
подключение формы и HTTPS описаны в [docs/backend.md](docs/backend.md).

## Backend локально: PostgreSQL и uv

Подготовьте PostgreSQL и роль с правом `CREATEDB` для тестов по
[инструкции](docs/backend.md#локальная-разработка-без-docker).
Следующие команды выполняются из корня проекта в Bash. Загружайте только
свой доверенный `.env`; значения со специальными символами заключайте
в кавычки.

```bash
set -a
source .env
set +a
export DB_HOST=127.0.0.1
export DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,testserver
export DEBUG=True
export DJANGO_COOKIE_SECURE=False
export DJANGO_SECURE_SSL_REDIRECT=False
cd backend
uv sync --python 3.12 --frozen --group dev
uv run python manage.py migrate
uv run python manage.py check
uv run python manage.py createsuperuser
uv run python manage.py runserver 127.0.0.1:8000
```

API: `http://127.0.0.1:8000/api/v1/`, админка:
`http://127.0.0.1:8000/admin/`. Если PostgreSQL использует другой порт,
измените `DB_PORT`. Команды `uv` выполняйте из `backend`, где лежат
`pyproject.toml` и `uv.lock`. `.env` сам по себе Django не загружает.

## Backend и frontend в Docker

Команды выполняются из корня проекта после подготовки `.env`:

```bash
docker compose config --quiet
docker compose up --build -d
docker compose ps --all
curl --fail http://localhost:8080/api/v1/health/
docker compose exec backend python manage.py createsuperuser
```

Сайт: `http://localhost:8080/`, админка: `http://localhost:8080/admin/`.
Сервис `init` выполняет миграции и `collectstatic` перед запуском Gunicorn.
Nginx отдаёт frontend и статику Django, проксирует `/api/` и `/admin/`.
Backend и БД доступны только внутри Docker-сети.

Конфигурация Docker подготовлена, но сборка и запуск Docker/Nginx в текущем
окружении не проверены: нет доступа к Docker socket. Backend ещё не развёрнут
на внешнем хостинге. Команды обновления и ограничения HTTPS —
в [docs/backend.md](docs/backend.md).

## Проверки и стиль кода

В терминале с теми же переменными окружения, из `backend`:

```bash
uv run --group dev pytest
uv run ruff check --config pyproject.toml . ../docs
uv run ruff format --check --config pyproject.toml . ../docs
uv run python manage.py makemigrations --check --dry-run
```

Из корня проекта:

```bash
node --check dist/app.js
node --check dist/config.js
node --check dist/beta-signup.js
backend/.venv/bin/ruff check --config backend/pyproject.toml backend docs
backend/.venv/bin/ruff format --check --config backend/pyproject.toml backend docs
```

Python оформляется по PEP 8: строки до 79 символов, текст комментариев
и докстрингов — до 72. Докстринги и поясняющие комментарии пишутся
по-русски. Общая конфигурация Ruff находится в `backend/pyproject.toml`
и применяется также к Python-скриптам из `docs/`. Для Docker-тестов:

```bash
docker compose --profile test build tests
docker compose --profile test run --rm tests
```

Ревью кода и актуальные проверки изменений:
[docs/code-review.md](docs/code-review.md). Исторический отчёт от
23 октября 2026 года с 56 тестами PostgreSQL и 10 сценариями формы:
[docs/backend-qa.md](docs/backend-qa.md). Эти результаты относятся к указанной
редакции проекта и не заменяют повторный запуск после изменений.
Контракт API: [docs/openapi.yaml](docs/openapi.yaml).

## Визуальное направление

При прокрутке композиция приближается, заголовок уходит, световой контур
раскрывается и появляется приватный чат. Переход работает в обе стороны.
Сигналы реагируют на наведение и нажатие; сообщение в демонстрационном чате
можно отпустить и вернуть. Проверьте также клавиатуру, мобильное меню
и системную настройку уменьшения движения.

Палитра взята из скриншотов ТЗ: `#0A051C`, `#EFEFF1`, `#6941B4`, `#B8B5FF`.
Логотип представлен временной текстовой надписью. Героиня создана image_gen.
Исходный файл: `dist/assets/hero-woman.png`, запрос:
[docs/hero-prompt.md](docs/hero-prompt.md). Отдельный прозрачный слой:
`dist/assets/hero-foreground-v2.png` (1203 × 1307), запрос:
[docs/hero-foreground-v2-prompt.md](docs/hero-foreground-v2-prompt.md).
Исходное изображение сохранено.

Раскадровка: [docs/storyboard.md](docs/storyboard.md). Браузерная проверка
визуальной версии: [docs/qa.md](docs/qa.md). Для окончательной приёмки нужны
реальные телефоны и согласование оформления. Прототип показывает движение
отдельных слоёв; изображение героини не является покадровой видеоанимацией.
