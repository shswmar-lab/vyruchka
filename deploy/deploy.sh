#!/usr/bin/env bash
#
# Установка «Выручка водителей» на Ubuntu (systemd + nginx + venv).
#
# Запуск от имени root:
#   sudo bash deploy.sh
#
# Скрипт идемпотентен (безопасно перезапускать).
#
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/vyruchka}"
APP_DIR="${APP_DIR%/}"
SERVICE_USER="${SERVICE_USER:-vyruchka}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Каталог приложения: $APP_DIR"

# ── 1. Системный пользователь ──────────────────────────────
if ! id "$SERVICE_USER" &>/dev/null; then
    echo "==> Создаю системного пользователя $SERVICE_USER"
    useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

install -d -o "$SERVICE_USER" -g "$SERVICE_USER" \
    "$APP_DIR" "$APP_DIR/static" "$APP_DIR/data" "$APP_DIR/log"

# ── 2. Копирование кода ────────────────────────────────────
echo "==> Копирую код из $SRC_DIR"
if [ "$SRC_DIR" = "$APP_DIR" ]; then
    echo "    SRC_DIR совпадает с APP_DIR ($APP_DIR) — копирование в себя пропущено"
else
    cp -r "$SRC_DIR/app" "$APP_DIR/"
    cp -r "$SRC_DIR/static/." "$APP_DIR/static/"
    cp "$SRC_DIR/requirements.txt" "$APP_DIR/"
    cp "$SRC_DIR/.env.example" "$APP_DIR/.env.example"
fi

# ── 3. Виртуальное окружение ───────────────────────────────
if [ ! -x "$APP_DIR/venv/bin/python" ]; then
    echo "==> Создаю venv"
    python3 -m venv "$APP_DIR/venv"
fi
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

# ── 4. .env ────────────────────────────────────────────────
if [ ! -f "$APP_DIR/.env" ]; then
    echo "==> Генерирую .env"
    SECRET="$(openssl rand -hex 32)"
    sed "s/^SECRET_KEY=.*/SECRET_KEY=$SECRET/" "$APP_DIR/.env.example" > "$APP_DIR/.env"
    chown "$SERVICE_USER:$SERVICE_USER" "$APP_DIR/.env"
    echo
    echo "!!! Отредактируйте $APP_DIR/.env:"
    echo "    - ADMIN_USERNAME (по умолчанию admin)"
    echo "    - ADMIN_PASSWORD (если пусто — будет сгенерирован при создании админа)"
    echo "    - COOKIE_SECURE=true, если будете использовать HTTPS"
    echo "    Затем повторно запустите: sudo bash $SRC_DIR/deploy/deploy.sh"
    echo "    Либо создайте админа сейчас: sudo -u vyruchka bash -c 'cd $APP_DIR && exec ./venv/bin/python -m app.create_admin'"
    exit 1
else
    echo "==> .env уже существует, пропускаю"
fi

# ── 5. Инициализация БД и первичный администратор ──────────
echo "==> Инициализация БД и администратора"
# create_admin требует, чтобы python -m app.* стартовал из $APP_DIR
# (пакет app ищется в текущем каталоге), и должен видеть ADMIN_* из .env.
# Запуск через sudo -u из чужого каталога (напр. /root) невозможен для vyruchka,
# поэтому делаем cd внутрь и подгружаем .env в отдельной оболочке.
if [ -d "$APP_DIR/app" ]; then
    sudo -u "$SERVICE_USER" bash -c 'cd "$1" && set -a && . ./.env && set +a && exec ./venv/bin/python -m app.create_admin' _ "$APP_DIR"
else
    echo "ОШИБКА: $APP_DIR/app не найден — код приложения не скопирован." >&2
    exit 1
fi

# ── 6. systemd ─────────────────────────────────────────────
echo "==> Устанавливаю systemd-сервис"
install -m 644 "$SRC_DIR/deploy/vyruchka.service" /etc/systemd/system/vyruchka.service
systemctl daemon-reload
systemctl enable --now vyruchka
systemctl status vyruchka --no-pager || true

# ── 7. nginx ───────────────────────────────────────────────
if command -v nginx >/dev/null 2>&1; then
    echo "==> Настраиваю nginx"
    # Дефолтный сайт nginx перехватывает :80 -> удаляем его, иначе vyruchka
    # будет недоступно по http://localhost/ (покажет приветствие nginx)
    rm -f /etc/nginx/sites-enabled/default
    cp "$SRC_DIR/deploy/nginx.conf" /etc/nginx/sites-available/vyruchka
    ln -sfn /etc/nginx/sites-available/vyruchka /etc/nginx/sites-enabled/vyruchka
    nginx -t
    systemctl reload nginx || systemctl restart nginx
else
    echo "==> nginx не найден. Установите: apt install nginx"
fi

echo
echo "Готово. Проверка:"
echo "  systemctl status vyruchka"
echo "  curl -I http://localhost/"
echo "  journalctl -u vyruchka -f"
echo
echo "Учётка администратора задаётся в $APP_DIR/.env (ADMIN_USERNAME / ADMIN_PASSWORD)."