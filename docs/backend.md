# Backend и размещение

Backend принимает заявки на бета-тест и предоставляет закрытую Django Admin. Это список ожидания по email: аккаунты приложения, JWT, чаты, видеозвонки и расчёт совместимости здесь не реализованы. Используются Python 3.12, Django 5.2 LTS, Django REST Framework, PostgreSQL 18 и Gunicorn. Зависимости закреплены в `backend/uv.lock`.

## Быстрый запуск в Docker

Команды выполняются из каталога `astro-prototype`. Нужны Docker Engine и Docker Compose с поддержкой `service_completed_successfully`.

```bash
cp .env.example .env
python3 -c 'import secrets; print(secrets.token_urlsafe(64))'
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Первую сгенерированную строку запишите в `DJANGO_SECRET_KEY` файла `.env`, вторую — в `DB_PASSWORD`. Не публикуйте `.env`. Остальные значения подходят для локального HTTP. `DEBUG=False` сохранён даже локально; `DJANGO_COOKIE_SECURE=False` позволяет войти в админку по HTTP.

```bash
docker compose config --quiet
docker compose up --build -d
docker compose ps --all
docker compose logs --tail=100 init backend nginx
curl --fail http://localhost:8080/api/v1/health/
docker compose exec backend python manage.py createsuperuser
```

Сайт: `http://localhost:8080/`. Админка: `http://localhost:8080/admin/`. По умолчанию Nginx доступен только с этого компьютера: `HTTP_BIND=127.0.0.1`. Backend и PostgreSQL не публикуют порты на хост.

Compose сначала ждёт готовности PostgreSQL. Одноразовый сервис `init` выполняет миграции, включая создание общей таблицы кеша `astro_cache`, и `collectstatic`. Только после его успешного завершения запускаются Gunicorn и Nginx. Миграции не выполняются при старте каждого Gunicorn worker. Статика админки передаётся Nginx через отдельный том.

В PostgreSQL 18 том подключён к `/var/lib/postgresql`, как предусматривает [официальный образ](https://hub.docker.com/_/postgres). Не переносите в него каталог данных старой основной версии без процедуры обновления PostgreSQL. `docker compose down` сохраняет тома. Для резервного копирования используйте `pg_dump` и проверяйте восстановление; удаление томов уничтожает сохранённые заявки.

После изменения backend обновите образ и отдельно повторите подготовку перед запуском web:

```bash
docker compose build backend init
docker compose run --rm init
docker compose up -d backend nginx
```

## Включение приёма заявок

Пока реальная политика обработки данных и формулировка согласия не готовы, оставьте `PUBLIC_SIGNUPS_ENABLED=False`, `PRIVACY_POLICY_VERSION` и `PUBLIC_PRIVACY_POLICY_URL` пустыми. Юридический текст проект не генерирует.

Когда заказчик предоставит утверждённый документ, укажите его публичный абсолютный HTTP(S) URL в `PUBLIC_PRIVACY_POLICY_URL`, согласованный идентификатор редакции в `PRIVACY_POLICY_VERSION` и включите `PUBLIC_SIGNUPS_ENABLED=True`. В production документ должен открываться по HTTPS. Затем примените настройки:

```bash
docker compose up -d --force-recreate backend nginx
```

Nginx при запуске генерирует `/config.js` с `apiBaseUrl: ""` — API находится на том же origin — и ссылкой на документ. Пустая ссылка оставляет форму неактивной. При обычной раздаче `dist` исходный `dist/config.js` содержит `apiBaseUrl: null` и `privacyPolicyUrl: null`: это демонстрация без отправки контактов.

### Публичный POST

```bash
curl -i http://localhost:8080/api/v1/beta-signups/ \
  -H 'Content-Type: application/json' \
  --data '{"email":"user@example.com","consent":true,"website":""}'
```

`email` обязателен. `consent` должен быть именно JSON-значением `true`, не строкой. `website` — скрытая ловушка для простых ботов, обычный клиент оставляет её пустой. Редакция политики определяется сервером из `PRIVACY_POLICY_VERSION` и сохраняется вместе с согласием; клиент её не назначает.

Для новой, повторной заявки и заполненной ботом ловушки ответ одинаковый: `202 Accepted` с телом:

```json
{"detail":"Заявка принята. Если вы ещё не в списке, мы добавим ваш email."}
```

Ответ не раскрывает, есть ли адрес в списке. Ошибка валидации возвращает `400`, превышение лимита — `429`, выключенный приём — `503`. Публичного GET со списком email нет. Для просмотра заявок используйте `/admin/` с учётной записью сотрудника; вход работает через Django sessions и CSRF, не через публичный API.

Ограничения отправки — 5 запросов в минуту и 30 в сутки с одного IP. Состояние хранится в PostgreSQL `DatabaseCache` и общее для всех Gunicorn workers. Это прикладной throttle, не строгая квота при параллельных запросах и не защита от распределённых атак. Nginx перезаписывает `X-Forwarded-For` адресом соединения, Django доверяет одному proxy (`NUM_PROXIES=1`). Backend должен оставаться доступным только через этот Nginx. Если перед ним появится CDN или дополнительный proxy, настройте получение реального IP только от известных доверенных адресов, иначе лимит будет общим для посетителей за этим proxy.

## Тесты

Тестовый Docker target включает группу `dev`; production target её не устанавливает. Нужна отдельная тестовая БД, которую Pytest создаёт и удаляет сам. Роль PostgreSQL должна иметь право `CREATEDB`; в локальном официальном образе первоначальная роль уже имеет необходимые права.

```bash
docker compose --profile test build tests
docker compose --profile test run --rm tests
```

Для разработки вне контейнера установите Python 3.12 и uv, подготовьте отдельную PostgreSQL БД и экспортируйте переменные из своего `.env`. Команда `source` ниже предполагает созданный вами доверенный shell-совместимый файл: значения с пробелами должны быть в кавычках. Если СУБД работает на этом компьютере, замените `DB_HOST=db` на `127.0.0.1`.

```bash
set -a
source .env
set +a
export DB_HOST=127.0.0.1
cd backend
uv sync --frozen --group dev
uv run python manage.py migrate
uv run python manage.py collectstatic --noinput
uv run python manage.py createsuperuser
uv run python manage.py runserver 127.0.0.1:8000
```

В другом терминале с теми же переменными окружения:

```bash
cd backend
uv run --group dev pytest
```

`runserver` подходит только для разработки. Для просмотра CSS админки через него временно используйте `DEBUG=True`; Docker Nginx отдаёт `/static/` и при `DEBUG=False`.

## Production и Sites

Sites раздаёт статический frontend, Django и PostgreSQL требуют отдельного сервера или подходящего PaaS. Сейчас API не опубликован, доступы к такому хостингу не предоставлены. Для подключения опубликованного frontend необходимо задать реальный HTTPS `apiBaseUrl` и ссылку на утверждённую политику в его конфигурации. В backend `CORS_ALLOWED_ORIGINS` должен содержать точный origin frontend, например `https://your-site.example`, без пути и завершающего слеша. Для Docker с одним origin значение может оставаться пустым. Cookies публичному POST не нужны.

Перед внешней публикацией задайте домен в `DJANGO_ALLOWED_HOSTS`, сохранив `localhost` для внутреннего healthcheck. Используйте `DEBUG=False`, `DJANGO_COOKIE_SECURE=True`, случайный секрет и пароль БД. Для админки за HTTPS укажите её точный origin в `CSRF_TRUSTED_ORIGINS`. Храните секреты в окружении сервера, а не в публичной конфигурации frontend.

Поставляемый Nginx template обслуживает HTTP для локального запуска; HTTPS-сертификат и домен нужно настроить на реальном хостинге. При завершении TLS непосредственно в этом Nginx `$scheme` автоматически передаст Django значение `https`. После этого включите `DJANGO_SECURE_SSL_REDIRECT=True`. Если TLS завершается на ещё одном reverse proxy, настройте доверенную передачу HTTPS-схемы до Django: текущий template намеренно не доверяет произвольному клиентскому `X-Forwarded-Proto`. Простое включение redirect при таком внешнем proxy без этой настройки создаст цикл перенаправлений. `DJANGO_HSTS_SECONDS` увеличивайте только после проверки корректной работы HTTPS.

```bash
docker compose exec backend python manage.py check --deploy
```

Healthcheck `/api/v1/health/` выполняет `SELECT 1`; он не возвращает настройки, секреты или данные заявок. Gunicorn пишет access/error logs в stdout/stderr; email передаётся в JSON body, не в URL. Не включайте логирование тел заявок на proxy или в мониторинге.

Документация инструментов: [порядок запуска Compose](https://docs.docker.com/compose/how-tos/startup-order/), [uv в Docker](https://docs.astral.sh/uv/guides/integration/docker/).
