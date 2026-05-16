Squad 32 - Sistema de Gestão de Provas SEED
📌 Sobre o Projeto
API para gerenciar provas, questões, simulados e certificações. Desenvolvido pelo Squad 32 como projeto da Residência em Software.

🛠️ Tecnologias
Back-end: Python + FastAPI

Banco de Dados: PostgreSQL + PostGIS (geolocalização)

Front-end: HTML, CSS, JavaScript puro

ORM: SQLAlchemy

Autenticação: JWT

🗄️ Banco de Dados – Estrutura e Migrações
Pré‑requisitos
PostgreSQL 15+ instalado

Extensão PostGIS (para geolocalização)

1. Criar o banco de dados
psql -U postgres -c "CREATE DATABASE squad32_seed;"

2. Executar as migrações (criar tabelas)
Os scripts estão em database/migrations/. Execute em ordem numérica:

Opção A: Manual (Bash)

psql -U postgres -d squad32_seed -f database/migrations/010_usuarios.sql

psql -U postgres -d squad32_seed -f database/migrations/020_provas.sql

psql -U postgres -d squad32_seed -f database/migrations/030_questoes.sql

psql -U postgres -d squad32_seed -f database/migrations/040_alternativas.sql

Opção B: Automática (PowerShell - Windows)
Get-ChildItem database/migrations/*.sql | Sort-Object Name | ForEach-Object { psql -U postgres -d squad32_seed -f $_.FullName }

🚀 Como executar o projeto
Back-end (API)
Acesse a pasta backend: cd backend

Crie e ative o ambiente virtual:

Windows: python -m venv venv e venv\Scripts\activate

Linux/Mac: python -m venv venv e source venv/bin/activate

Instale as dependências: python -m pip install -r requirements.txt

Configure o .env e execute: uvicorn app.main:app --reload

Front-end
Abra o arquivo frontend/index.html no navegador.

📦 Variáveis de Ambiente (.env)
Crie o arquivo na pasta /backend:

DATABASE_URL=postgresql://postgres:sua_senha@localhost:5432/squad32_seed

SECRET_KEY=37592

ALGORITHM=HS256

ACCESS_TOKEN_EXPIRE_MINUTES=1440

🐛 Solução de Problemas
psql: command not found: Adicione o PostgreSQL ao PATH do sistema.

FATAL: auth failed: Verifique a senha no arquivo .env.

ModuleNotFoundError: Ative a venv antes de rodar o projeto.