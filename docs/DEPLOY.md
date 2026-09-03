# Деплой

Бот живёт в FreeBSD-jail `bots` на домашнем сервере, как и соседние боты. В этом
репозитории **нет** ничего деплойного (ARCHITECTURE A12): rc.d-скрипт, запись в реестре
и роли Ansible — в `~/Projects/Automation/freebsd-server`, env-файл — на сервере.

## Как выкатывается релиз

1. Push в `main` → CI (job с именем ровно `ci`).
2. Тег `vX.Y.Z` (строго три числа) на коммит с зелёным `ci`.
3. `ansible-pull` на сервере раз в 2 минуты видит новый тег, проверяет статус `ci`
   **анонимным** вызовом GitHub API (поэтому репозиторий публичный), клонирует в
   `~/releases/<tag>`, ставит `pip install -r requirements.txt` в `~/venv`
   (`--system-site-packages`: компилируемые пакеты — из портов), гонит
   `alembic upgrade head`, переключает симлинк `~/app`, перезапускает службу,
   проверяет `service … status`; при неудаче откатывает симлинк.

Имена по конвенции парка:

| Что | Значение |
|---|---|
| репозиторий | `dabajabaza/anki-deck-gen-tgbot` |
| `deploy_bots.name`, Kuma, env, pid, lock | `anki-deck-gen` |
| служба / rc.d / `sysrc` | `anki_deck_gen` |
| пользователь и home | `ankideckgen`, `/home/ankideckgen` |
| пакет Python | `anki_deck_gen` (`python -m anki_deck_gen`) |
| env-файл | `/usr/local/etc/anki-deck-gen.env` |
| scratch и кэш озвучки | `/var/tmp/anki-deck-gen` |
| база | `/var/db/ankideckgen/access.sqlite` |
| editable `.pth` | `_editable_impl_anki_deck_gen.pth` (из `name = "anki-deck-gen"` в pyproject) |

## Разовый бутстрап jail — ДО записи в реестр

Иначе `ansible-pull` каждые 2 минуты падает в `rescue` на несуществующем пользователе.
И второе, проверено на первой выкатке: роль после перезапуска службы делает
`service anki_deck_gen status`, а у **невключённой** службы `status` возвращает ошибку —
выкатка признаётся провальной и откатывается на пустой `pre-deploy`. Значит, к моменту
первой выкатки служба должна быть включена, а env-файл — заполнен целиком, включая токен.
Внутри `jexec bots sh`:

```sh
pw useradd ankideckgen -m -d /home/ankideckgen -s /bin/sh
mkdir -p /home/ankideckgen/releases/pre-deploy
chown -R ankideckgen:ankideckgen /home/ankideckgen
install -d -o ankideckgen -g ankideckgen -m 700 /var/tmp/anki-deck-gen /var/db/ankideckgen
install -m 600 -o ankideckgen /dev/null /usr/local/etc/anki-deck-gen.env
```

Заполнить `/usr/local/etc/anki-deck-gen.env` (см. `.env.example`):

```sh
TELEGRAM_BOT_TOKEN=…          # от @BotFather
ADMIN_IDS=…,…                 # оба админа
TELEGRAM_PROXY=http://127.0.0.1:1080
WORK_DIR=/var/tmp/anki-deck-gen
DATABASE_URL=sqlite+aiosqlite:////var/db/ankideckgen/access.sqlite
```

Заполнив токен — сразу `sysrc anki_deck_gen_enable=YES`. Служба не стартует до появления
релиза (`~/app` ещё пуст), но `status` у включённой службы роль трактует правильно после
своего же `restart`. Порядок: пользователь и каталоги → env с токеном → `sysrc` → push реестра.

## Регистрация в Automation

В `freebsd-server/site.yml`, список `deploy_bots`:

```yaml
- name: anki-deck-gen
  service: anki_deck_gen
  home: /home/ankideckgen
  owner: ankideckgen
  repo_owner: dabajabaza
  repo_name: anki-deck-gen-tgbot
  editable_pth: _editable_impl_anki_deck_gen.pth
  editable_target: /home/ankideckgen/app/src
  alembic: true
  env_file: /usr/local/etc/anki-deck-gen.env
```

Плюс rc.d `roles/bot_rc/files/anki_deck_gen` по образцу `twitter_dl` (`-m anki_deck_gen`,
`--name anki-deck-gen`, `--watchdog-sec 90`, экспорт `LOCK_FILE`) и запись в
`backup_dumps` для `/jails/bots/var/db/ankideckgen/access.sqlite`.

## После первой выкатки

```sh
service anki_deck_gen status
tail -f /var/log/messages     # ждём READY=1 от sdnotify-supervise
```

Если реестр запушили раньше, чем включили службу: каждые 2 минуты роль будет
выкатывать и откатывать релиз. Это самолечится — как только служба включена и env
заполнен, следующий тик проходит health check. Не ждать можно так: на хосте
`/usr/local/sbin/ansible-pull-bots`.

Kuma-хартбит — строка `KUMA_PUSH_ANKI_DECK_GEN=…` в `/usr/local/etc/kuma-push.conf`,
по желанию.

## Что помнить

- Каталог релиза принадлежит root: бот пишет только в `/var/tmp/anki-deck-gen` и в базу.
- Кэш озвучки переживает релизы — чистится только `releases/`.
- Супервизор убивает процесс без `WATCHDOG=1` дольше 90 с; бот шлёт его каждые 30 с,
  пока Telegram отвечает.
- Удалить каталог `~/releases/pre-deploy` нельзя: первый прогон роли делает
  `mv ~/app ~/releases/pre-deploy`.
