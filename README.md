\# Squad 32 - Sistema de Gestão de Provas SEED



API para gerenciar provas, questões, simulados e certificações.



\## Tecnologias

\- FastAPI (Python)

\- PostgreSQL + PostGIS

\- SQLAlchemy



\## Como executar



1\. Clone o repositório

2\. Crie ambiente virtual: `python -m venv venv`

3\. Ative: `venv\\Scripts\\activate`

4\. Instale dependências: `python -m pip install -r requirements.txt`

5\. Configure `.env` com sua senha do PostgreSQL

6\. Execute: `uvicorn app.main:app --reload`



\## Endpoints principais

\- `GET /` - Mensagem de boas-vindas

\- `GET /health` - Health check

\- `GET /usuarios` - Listar usuários

