---
name: remote-db-connect
description: Подключение к удаленной БД через защищенный канал
---
# Инструкция
1. Используй переменные окружения: DB_TYPE, DB_PATH, DB_HOST, DB_USER, DB_PASSWORD, DB_PORT, DB_NAME
2. DB_TYPE=sqlite — локальная разработка, DB_TYPE=postgresql — продакшн
3. Подключение к PostgreSQL только через SSL (sslmode=require)
4. Пул соединений: min=1, max=40
5. Обработка таймаутов: 30 сек
