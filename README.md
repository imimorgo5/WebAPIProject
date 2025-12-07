# Итоговое задание — Асинхронный Backend: REST API + WebSocket + Фоновые задачи + NATS

### Выполнил: Муравьев Илья Германович РИ-330910

## Реализовано
- REST API для CRUD-операций над парфюмами (`/perfumes`).
- WebSocket `/ws/perfumes` для уведомлений в реальном времени.
- Фоновая задача, которая запускается по интервалу, парсит сайт `letu.ru` и добавляет новые парфюмы в БД.
- Ручной старт фоновой задачи: `POST /tasks/run`.
- Интеграция с NATS: публикация изменений и подписка на внешний канал `perfumes.updates`.
- Асинхронная работа с SQLite через SQLModel/SQLAlchemy.

## Инструкция по запуску

1. Клонировать проект
```bash
git clone https://github.com/imimorgo5/WebAPIProject.git
cd WebAPIProject
```

2. Создать виртуальное окружение и установить зависимости
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Установить браузеры для playwright
```bash
playwright install
```

4. Запустить nats-server (используйте поставляемый двоичный файл в проекте (версия v2.12.2-darwin-arm64) или скачайте под свою систему (https://github.com/nats-io/nats-server/releases), после установки добавьте в главную директорию проекта)
```bash
 ./nats-server
```

5. Запустить приложение
```bash
uvicorn app.main:app --reload
```

6. API docs: http://127.0.0.1:8000/docs
   WebSocket: ws://0.0.0.0:8000/ws/perfumes

## Эндпойнты
- `GET /perfumes` — список всех парфюмов 
  - `?only_discounted=` `true` — вернуть только парфюмы со скидкой, `false` — все.
  - `?brand={Название_бренда}` — вернуть только парфюмы указанного бренда
- `GET /perfumes/{id}` — получить парфюм
- `POST /perfumes` — создать парфюм
- `PATCH /perfumes/{id}` — обновить парфюм
- `DELETE /perfumes/{id}` — удалить парфюм
- `POST /tasks/run` — запуск фоновой задачи вручную
- `GET /brands` — список брендов
- WebSocket: `/ws/perfumes`