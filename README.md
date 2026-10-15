# Выручка водителей

Веб-приложение для учёта выручки водителей: ввод и фильтрация записей, аналитика, графики, импорт/экспорт Excel.

Сервер — Python + FastAPI + SQLite, клиент — браузер (SPA из одного `index.html`).

## Стек

- **Сервер:** Python, FastAPI, SQLite, uvicorn
- **Авторизация:** JWT в httpOnly-cookie, пароли bcrypt
- **Клиент:** SPA на одном `index.html`
- **Деплой:** Ubuntu, systemd + nginx + venv

## Роли

| Роль | Права |
|---|---|
| Администратор | Всё + раздел «Администрирование», импорт Excel, «Очистить всё», экспорт всех (CSV), журнал действий |
| Пользователь | Ввод/редактирование записей, сводные, экспорт текущего Excel, печать |
| Руководитель | Только «Аналитика» и «Графики» (запись и админ-разделы закрыты) |

## Функционал

- Таблица записей с периодом (месяц/год) и фильтрами по ФИО, дате и автору;
- «Аналитика»: сводные по водителям, датам и маршрутам;
- «Графики»: годовой, месячный и произвольный по дням;
- импорт из Excel (режимы «Дополнить» / «Заменить», только админ), предупреждение о дублях;
- экспорт: текущие записи в Excel, все записи в CSV (только админ);
- журнал действий администратора.

## Структура проекта

```
app/            серверный код FastAPI (main, db, schemas, auth, create_admin)
app/routers/    auth, users, rows, drivers, routes, audit
static/         index.html + xlsx.full.min.js (раздаёт сервер/nginx)
deploy/         systemd-юнит, nginx.conf, deploy.sh
test/           pytest: auth, роли, CRUD, дедупликация, экспорт, журнал
.env.example    шаблон конфигурации (секретов нет)
```

## Запуск (разработка)

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows
source .venv/bin/activate         # Linux/macOS
pip install -r requirements.txt

set DB_PATH=data/dev.db & set SECRET_KEY=dev   # Windows
python -m app.create_admin
uvicorn app.main:app --reload --port 8000
```

Открыть http://localhost:8000 (логин `admin`, пароль выводится при создании администратора).

## Деплой (Ubuntu)

```bash
sudo bash deploy/deploy.sh
```

Скрипт создаёт системного пользователя `vyruchka`, копирует код в `/opt/vyruchka`, ставит зависимости в venv, настраивает systemd и nginx. Подробности и настройка `.env` — в комментариях `deploy/deploy.sh`.

## Тесты

```bash
pytest -q
```
