DATABASE_URL = "sqlite+aiosqlite:///./perfumes.db"
BASE_URL = "https://www.letu.ru/browse/muzhchinam/muzhskaya-parfyumeriya"
PARSE_LIMIT = 10
MAX_PAGES = 100
BACKGROUND_INTERVAL_SECONDS = 600
NATS_SERVERS = ["nats://127.0.0.1:4222"]
NATS_SUBJECT = "perfumes.updates"