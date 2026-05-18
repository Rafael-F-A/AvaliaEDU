# Squad 32 – Sistema de Gestão de Provas SEED

API para gerenciar provas, questões, simulados e certificações. Projeto desenvolvido durante a Residência em Software.

## Tecnologias

- **Back-end**: Python, FastAPI, SQLAlchemy, JWT
- **Banco de Dados**: PostgreSQL, PostGIS
- **Front-end**: HTML, CSS, JavaScript

## Banco de Dados

### Pré‑requisitos

- PostgreSQL 15+ com extensão PostGIS

### Criar o banco

psql -U postgres -c "CREATE DATABASE squad32_seed;"
**Executar migrações**
Os scripts estão em `database/migrations/` (executar em ordem numérica):bash

`psql -U postgres -d squad32_seed -f database/migrations/010_usuarios.sql
psql -U postgres -d squad32_seed -f database/migrations/020_provas.sql
psql -U postgres -d squad32_seed -f database/migrations/030_questoes.sql
psql -U postgres -d squad32_seed -f database/migrations/040_alternativas.sql`**
Execução
Back-end**bash

`cd backend
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate          # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload`**
Front-end**
Abra `frontend/index.html` no navegador.**
Configuração**
Crie um arquivo `.env` em `backend/`:env

`DATABASE_URL=postgresql://postgres:senha@localhost:5432/squad32_seed
SECRET_KEY=37592
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440`**
Problemas comunsProblemaSolução**`psql: command not found`Adicione o PostgreSQL ao PATH.`password authentication failed`Verifique a senha no `.env`.`ModuleNotFoundError`Ative o ambiente virtual.text