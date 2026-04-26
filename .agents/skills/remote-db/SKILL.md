---
name: remote-db-connect
description: Remote database connection via secure channel
---

# Remote DB Connection

1. Use environment variables: `DB_TYPE`, `DB_PATH`, `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_PORT`, `DB_NAME`
2. `DB_TYPE=sqlite` — local development, `DB_TYPE=postgresql` — production
3. PostgreSQL connection only via SSL (`sslmode=require`)
4. Connection pool: min=1, max=40
5. Timeout handling: 30 sec
