# Разработка backend и размещение

Backend принимает заявки в список ожидания и предоставляет закрытую Django
Admin. Используются Python 3.12, Django 5.2 LTS, Django REST Framework,
PostgreSQL 18, psycopg и Gunicorn. Версии закреплены в `backend/uv.lock`.
Разработка и тесты также используют PostgreSQL; SQLite не предусмотрен.

## Границы frontend и API

`dist/` содержит самостоятельный статический сайт. Django не отдаёт его
в native-режиме. `dist/beta-signup.js` отправляет JSON в API только при
наличии адреса backend и ссылки на политику. Значения задаёт `config.js`:

- `apiBaseUrl: null` — отправка отключена;
- `apiBaseUrl: ""` — API на том же origin, как в Docker за Nginx;
- абсолютный `apiBaseUrl` — корневой адрес отдельного API без `/api/v1/`;
- `privacyPolicyUrl: null` — форма отключена до настройки документа.

Пример структуры конфигурации после подключения реальных адресов:

```javascript
window.ASTRO_CONFIG = {
  apiBaseUrl: "https://api.example.com",
  privacyPolicyUrl: "https://example.com/privacy/",
};
```

Это образец адресов, а не опубликованный API или готовая политика.
Секретов в frontend-конфигурации быть не должно. В исходном `dist/config.js`
оба значения равны `null`.

API реализует только список ожидания: сохраняет email, статус, время заявки,
время согласия и серверную редакцию политики. Аккаунтов приложения, JWT,
чата, видеосвязи и алгоритма совместимости здесь нет.

## Переменные окружения

Все команды ниже начинаются из корня проекта — `astro-prototype`,
если перед блоком не указан другой каталог. Подготовьте `.env`:

```bash
cp -n .env.example .env
python3 -c 'import secrets; print(secrets.token_urlsafe(64))'
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Первую строку внесите в `DJANGO_SECRET_KEY`, вторую — в `DB_PASSWORD`.
Не используйте пример или короткую постоянную строку вместо секрета.
`.env` исключён из репозитория. Django сам его не читает: Docker Compose
передаёт переменные автоматически, при native-запуске их нужно экспортировать.

Основные группы настроек:

- `DJANGO_SECRET_KEY` обязателен и не должен быть пустым. `DEBUG=False`
  подходит для Docker; локально с `runserver` удобно включить `DEBUG=True`.
- `DJANGO_ALLOWED_HOSTS` — имена хостов через запятую, без схемы и порта.
  Для локальных тестов: `localhost,127.0.0.1,testserver`. В Docker сохраните
  `localhost`, которым пользуется внутренний healthcheck.
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` задают подключение
  к PostgreSQL. В Compose адрес и порт переопределяются на `db:5432`.
  Для native-запуска обычно нужны `127.0.0.1:5432`.
- `CORS_ALLOWED_ORIGINS` содержит точные origins frontend через запятую,
  например `http://127.0.0.1:8081`. Для одного origin за Nginx оставьте пустым.
  `localhost` и `127.0.0.1` считаются разными origins.
- `CSRF_TRUSTED_ORIGINS` — доверенные origins для CSRF-проверок, прежде всего
  админки за внешним HTTPS proxy. Публичный POST не использует session cookies.
- `DJANGO_COOKIE_SECURE`, `DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_HSTS_SECONDS`
  управляют HTTPS. В шаблоне для локального HTTP: `False`, `False`, `0`.
- `PUBLIC_SIGNUPS_ENABLED=False` выключает приём. Для включения также нужна
  непустая `PRIVACY_POLICY_VERSION`. Версия задаётся только сервером.
- `PUBLIC_PRIVACY_POLICY_URL` использует startup-скрипт Nginx для генерации
  frontend-конфигурации. В native-режиме одна эта переменная не изменяет
  `dist/config.js`.
- `HTTP_BIND=127.0.0.1` и `HTTP_PORT=8080` задают внешний адрес Nginx в Docker.
  Backend и PostgreSQL не публикуют свои порты.

Не меняйте пароль уже созданной Docker-БД только редактированием `.env`:
`POSTGRES_PASSWORD` применяется при первоначальной инициализации тома.
Существующую роль изменяют средствами PostgreSQL, затем обновляют настройки
приложения.

## Локальная разработка без Docker

Нужны Python 3.12, uv и работающий PostgreSQL 18. База и роль должны
существовать до запуска Django. Для новой локальной БД на Linux администратор
PostgreSQL может выполнить:

```bash
sudo -u postgres psql
```

В открывшейся SQL-консоли:

```sql
CREATE ROLE astro WITH LOGIN CREATEDB;
\password astro
CREATE DATABASE astro OWNER astro;
\quit
```

Введите тот же пароль, что записан в `.env`. Имена соответствуют значениям
шаблона. Для уже существующих роли и базы повторно выполнять эти SQL-команды
не нужно. `CREATEDB` требуется только тестовой/локальной роли: Pytest создаёт
отдельную `test_astro`, а не очищает рабочую `astro`. Не запускайте тесты
с реквизитами production.

Загрузите свой доверенный `.env` из корня проекта. Команды предназначены
для Bash; значения со специальными символами в `.env` заключайте в кавычки:

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

Если сервер БД использует другой порт, после загрузки `.env` задайте
соответствующий `DB_PORT`. API доступен на `http://127.0.0.1:8000/api/v1/`,
админка — на `http://127.0.0.1:8000/admin/`. `DEBUG=True` позволяет
`runserver` отдать CSS админки. `runserver` используется только для разработки.

Команды `uv` выполняйте из `backend`: конфигурация и lock-файл находятся
в этом каталоге. Для сборки статики перед размещением команда также
выполняется оттуда:

```bash
uv run python manage.py collectstatic --noinput
```

При `DEBUG=False` обычный `runserver` не отдаёт собранную статику.
В Docker этим занимается Nginx через общий том.

Для отдельного просмотра frontend во втором терминале, из корня проекта:

```bash
python3 -m http.server 8081 --directory dist
```

Откройте `http://127.0.0.1:8081/`. Для проверки настоящей формы нужно отдельно
задать в `dist/config.js` адрес `http://127.0.0.1:8000`, ссылку на утверждённую
политику и разрешить CORS origin `http://127.0.0.1:8081` в backend. После
локальной проверки верните публичную конфигурацию в отключённое состояние,
если реальный API ещё не подключён.

## Запуск в Docker

Конфигурация подготовлена, но сборка и запуск Docker/Nginx в текущем окружении
не подтверждены: нет доступа к Docker socket. Следующие команды — инструкция
для окружения с рабочим Docker Engine и Docker Compose.

Из корня проекта после подготовки `.env`:

```bash
docker compose config --quiet
docker compose up --build -d
docker compose ps --all
docker compose logs --tail=100 init backend nginx
curl --fail http://localhost:8080/api/v1/health/
docker compose exec backend python manage.py createsuperuser
```

Сайт: `http://localhost:8080/`, админка: `http://localhost:8080/admin/`.
По умолчанию HTTP-порт доступен только с этого компьютера.

Порядок запуска уже задан в `compose.yaml`: PostgreSQL проходит healthcheck,
сервис `init` выполняет `migrate` и `collectstatic`, затем запускаются Gunicorn
и Nginx. Миграция `0002_throttle_cache` создаёт таблицу общего кеша
`astro_cache`; отдельная ручная команда `createcachetable` не нужна.
Gunicorn работает непривилегированным пользователем с двумя workers.
Nginx отдаёт `/static/` из отдельного тома, frontend — из `dist/`.

Том PostgreSQL 18 подключён к `/var/lib/postgresql`, как предусматривает
[официальный образ](https://hub.docker.com/_/postgres). `docker compose down`
сохраняет тома. Обновление основной версии PostgreSQL требует отдельной
процедуры, а не замены версии образа поверх существующих данных.

После изменения backend, из корня проекта:

```bash
docker compose build backend init
docker compose run --rm init
docker compose up -d backend nginx
docker compose restart nginx
```

Последний шаг нужен потому, что текущая конфигурация Nginx разрешает адрес
`backend` при запуске. После пересоздания backend его IP может измениться;
перезапуск Nginx обновляет адрес upstream.

## Включение приёма заявок

До готовности реальной политики оставьте `PUBLIC_SIGNUPS_ENABLED=False`,
`PRIVACY_POLICY_VERSION` и `PUBLIC_PRIVACY_POLICY_URL` пустыми. Юридический
текст проект не генерирует.

После согласования документа укажите его публичный абсолютный HTTP(S) URL
в `PUBLIC_PRIVACY_POLICY_URL`, идентификатор редакции в
`PRIVACY_POLICY_VERSION` и включите `PUBLIC_SIGNUPS_ENABLED=True`.
Для production документ должен открываться по HTTPS. Примените изменения
из корня проекта:

```bash
docker compose up -d --force-recreate backend nginx
docker compose restart nginx
```

При запуске Nginx генерирует `/config.js` с `apiBaseUrl: ""` и ссылкой
на политику. При пустой ссылке frontend оставляет поля отключёнными.
В native-режиме перезапустите Django с новыми переменными и настройте
`dist/config.js` отдельно. Не включайте сбор настоящих контактов
с временным или выдуманным документом.

## Контракт API

Проверка доступности выполняет `SELECT 1` и возвращает только состояние,
без настроек и содержимого БД:

```bash
curl --fail http://127.0.0.1:8000/api/v1/health/
```

Ответ работающего API — `{"status":"ok"}`. При недоступной БД — `503`.

Для заявки используйте JSON POST. Приём должен быть включён предыдущим
шагом; по умолчанию этот запрос вернёт `503`:

```bash
curl -i http://127.0.0.1:8000/api/v1/beta-signups/ \
  -H 'Content-Type: application/json' \
  --data '{"email":"user@example.com","consent":true,"website":""}'
```

Для Docker замените origin на `http://localhost:8080`. Поля:

- `email` обязателен, проверяется сериализатором и приводится к нижнему
  регистру. Уникальность без учёта регистра дополнительно защищена БД.
- `consent` должен быть именно JSON-значением `true`, не строкой.
- `website` — необязательная ловушка для простых ботов. Обычный клиент
  оставляет её пустой.

Дату согласия и редакцию политики назначает сервер. Повторная заявка
не перезаписывает исходное согласие и статус. Для новой, повторной заявки
и заполненной ловушки ответ одинаковый: `202 Accepted`:

```json
{"detail":"Заявка принята. Если вы ещё не в списке, мы добавим ваш email."}
```

Другие ответы: `400` — ошибка валидации, `429` — превышен лимит,
`503` — приём выключен или версия политики не задана. При `429` frontend
читает `Retry-After`; заголовок доступен также при разрешённом CORS.
Публичного GET со списком email нет. Полный контракт:
[openapi.yaml](openapi.yaml).

Лимиты — 5 запросов в минуту и 30 в сутки с одного IP. PostgreSQL
`DatabaseCache` общий для всех workers. Это прикладной throttle,
а не строгая атомарная квота при параллельных запросах. Nginx перезаписывает
`X-Forwarded-For` адресом соединения, Django доверяет одному proxy
(`NUM_PROXIES=1`). Backend должен оставаться доступным только через Nginx.
Если перед ним появится CDN или дополнительный proxy, получение реального
IP нужно настроить только для доверенных адресов.

## Админка

Создайте администратора командой `createsuperuser` из выбранного сценария
запуска. Вход в `/admin/` использует Django sessions и CSRF. Для сотрудников
нужен `is_staff` и права на просмотр/изменение заявок. Через админку можно
просматривать заявки и менять статус; исходные сведения о согласии доступны
только для чтения. Публичный API административных операций не предоставляет.

## Pytest и стиль Python

В новом терминале сначала загрузите окружение из корня проекта:

```bash
set -a
source .env
set +a
export DB_HOST=127.0.0.1
export DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,testserver
cd backend
uv run --group dev pytest
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run ruff check --config pyproject.toml . ../docs
uv run ruff format --check --config pyproject.toml . ../docs
```

Если тестовая БД находится на другом порту, задайте `DB_PORT` перед Pytest.
Общий autouse fixture включает сбор заявок и тестовую редакцию политики
только внутри тестов. Обычные тесты изолируют кеш; отдельные тесты проверяют
настоящий `DatabaseCache` PostgreSQL. Используется отдельная тестовая БД.

Настройки Ruff едины для backend и Python-скриптов QA из `docs/`:
`backend/pyproject.toml`. Лимит строки Python — 79 символов, текста
комментариев и докстрингов — 72. Докстринги модулей, классов и функций,
а также поясняющие комментарии пишутся по-русски. Ruff проверяет наличие
и оформление докстрингов; русский язык проверяется при ревью.
Не переводите имена библиотек, API-поля и общепринятые технические термины
ради формального соблюдения языка.

Те же проверки Ruff из корня проекта:

```bash
backend/.venv/bin/ruff check --config backend/pyproject.toml backend docs
backend/.venv/bin/ruff format --check --config backend/pyproject.toml backend docs
```

Чтобы применить форматирование, из `backend`:

```bash
uv run ruff format --config pyproject.toml . ../docs
```

Тестовый Docker target устанавливает группу `dev`, production target — нет.
Из корня проекта:

```bash
docker compose --profile test build tests
docker compose --profile test run --rm tests
```

Актуальное ревью и результаты текущих проверок:
[code-review.md](code-review.md). Исторический отчёт от 23 октября 2026 года:
[backend-qa.md](backend-qa.md), 56 тестов на PostgreSQL и 10 сценариев формы.
Он фиксирует состояние той редакции и не подтверждает проверки новых
изменений.

## Production и Sites

Sites исполняет статический frontend. Django и PostgreSQL требуют отдельного
сервера или подходящего PaaS; backend пока не развёрнут на внешнем хостинге.
Для подключения нужны реальный HTTPS `apiBaseUrl`, утверждённая политика
и точный origin frontend в `CORS_ALLOWED_ORIGINS`, без пути и завершающего
слеша. Для Docker с одним origin CORS можно оставить пустым.

Перед публикацией настройте домен в `DJANGO_ALLOWED_HOSTS`, сохранив
`localhost` для healthcheck. Используйте `DEBUG=False`,
`DJANGO_COOKIE_SECURE=True`, случайные секрет и пароль БД. Для админки
за HTTPS задайте доверенный origin в `CSRF_TRUSTED_ORIGINS`. Секреты храните
на сервере; не помещайте их в frontend.

Поставляемый Nginx template обслуживает локальный HTTP. HTTPS-сертификат
и домен нужно настроить на хостинге. Если TLS завершается в этом Nginx,
`$scheme` передаст Django значение `https`. После настройки включите
`DJANGO_SECURE_SSL_REDIRECT=True`. При TLS на внешнем reverse proxy
настройте доверенную передачу HTTPS-схемы: текущий template не доверяет
произвольному клиентскому `X-Forwarded-Proto`. Включение redirect без этого
создаст цикл перенаправлений. HSTS включайте после проверки HTTPS.

Из корня проекта с рабочим Docker:

```bash
docker compose exec backend python manage.py check --deploy
```

В локальном окружении предупреждения о выключенных HTTPS redirect/HSTS
ожидаемы. На сервере отдельно настройте резервное копирование PostgreSQL
и проверьте восстановление. Gunicorn пишет access/error logs в stdout/stderr;
не добавляйте логирование тел заявок с email.

Документация инструментов:
[порядок запуска Compose](https://docs.docker.com/compose/how-tos/startup-order/),
[uv в Docker](https://docs.astral.sh/uv/guides/integration/docker/).
