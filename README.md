# AvaliaEDU — Squad 32 · Sistema de Gestão de Provas (SEED)

<p align="center">
  Plataforma web para criação, aplicação e correção de provas, simulados e
  certificações, com geolocalização de locais de prova e certificados digitais
  validáveis.<br>
  Projeto desenvolvido durante a <strong>Residência em Software</strong> —
  Secretaria de Estado da Educação de Sergipe (SEED).
</p>

---

## 🌐 Versão online (MVP publicado)

| Camada | URL |
|---|---|
| Aplicação (frontend) | https://frontend-ten-beryl-38.vercel.app |
| API (backend) | https://avaliaedu-api.onrender.com |
| Documentação da API (Swagger) | https://avaliaedu-api.onrender.com/docs |

> O backend roda no plano gratuito do Render; após ~15 min sem uso, a **primeira
> requisição pode levar ~50s** (cold start). Depois disso responde normalmente.

---

## 📚 Sobre o projeto

Sistema construído em arquitetura REST (FastAPI) com autenticação JWT e três
perfis de usuário (Aluno, Professor/Admin). Principais módulos:

- 📄 **Provas** — criação, edição, publicação, exportação em PDF
- ❓ **Questões** — manuais e **geração automática** a partir de modelos com
  variáveis (questões únicas por aluno — antifraude)
- 📝 **Simulados** e 🏆 **Certificações** (com regras distintas de tempo, nota e bloqueio)
- 🗺️ **Locais de prova** com recomendação por **geolocalização** (PostGIS)
- 🪪 **Certificados** em PDF (brasão + QR code) com **validação pública** por código
- 👥 **Usuários**, autenticação e relatórios

---

## 🚀 Tecnologias

**Back-end:** Python · FastAPI · SQLAlchemy · JWT (python-jose) · passlib/bcrypt ·
slowapi (rate limit) · ReportLab + qrcode (PDFs) · openpyxl (relatórios)
**Banco:** PostgreSQL + PostGIS (via SQLAlchemy + GeoAlchemy2)
**Storage:** Supabase Storage (certificados, provas e imagens de questões)
**Front-end:** HTML5 · CSS3 · JavaScript (vanilla, sem build)
**Deploy:** Render (backend) · Vercel (frontend) · Supabase (banco + storage)

---

## 🗂️ Estrutura do projeto

```
.
├── backend/
│   ├── app/
│   │   ├── main.py            # app FastAPI + middlewares (CORS, rate limit)
│   │   ├── database.py        # engine/sessão SQLAlchemy
│   │   ├── models.py          # modelos ORM
│   │   ├── schemas.py         # schemas Pydantic
│   │   ├── security.py        # hash de senha + criação de JWT
│   │   ├── dependencies.py    # auth (get_usuario_atual / admin / aluno)
│   │   ├── enums.py
│   │   ├── routers/           # auth, provas, questoes, geracao, simulados,
│   │   │                      # certificacoes, pdf, geolocalizacao, usuarios,
│   │   │                      # reservas, componentes, inscricoes, relatorios
│   │   ├── services/          # regras de negócio (1 por domínio)
│   │   └── utils/storage.py   # integração com Supabase Storage
│   ├── requirements.txt
│   ├── Procfile               # comando de start (deploy)
│   └── .python-version        # 3.12
├── frontend/
│   ├── index.html             # landing + validação pública de certificado
│   ├── auth.html              # login e cadastro
│   ├── dashboard-admin.html   # painel do professor/admin
│   ├── dashboard-aluno.html   # painel do aluno
│   ├── css/                   # global, admin, aluno, auth, landing-page
│   ├── js/                    # global, admin, aluno, auth, landing-page
│   └── favicon.svg · og-image.svg/png
├── database/
│   └── migrations/            # scripts SQL numerados (010 … 150)
├── render.yaml                # blueprint de deploy (Render)
└── README.md
```

---

## ⚙️ Pré-requisitos

- **Python 3.12** (3.13/3.14 podem quebrar wheels de `psycopg2`/`pillow`)
- **PostgreSQL 15+ com PostGIS** — ou um projeto **Supabase** (que já traz PostGIS)
- Um projeto **Supabase** para o Storage (buckets `certificados`, `provas`, `questoes`)

---

## 🔑 Variáveis de ambiente

Crie um arquivo `backend/.env` (não versionado):

```env
# Banco PostgreSQL/PostGIS (ex.: connection string do Supabase — session pooler, porta 5432)
DATABASE_URL=postgresql://USUARIO:SENHA@HOST:5432/postgres

# Supabase Storage
SUPABASE_URL=https://<seu-projeto>.supabase.co
SUPABASE_SERVICE_KEY=<service_role key do painel Supabase>

# Autenticação
SECRET_KEY=<string aleatória forte>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
ADMIN_SECRET_KEY=<token exigido para registrar um ADMIN>

# Outros
BASE_URL=http://localhost:8000
ALLOWED_ORIGINS=*
```

---

## 🗄️ Banco de dados

Os scripts ficam em `database/migrations/` e devem ser executados **em ordem
numérica crescente** (`010_…` até `150_…`). Em um Postgres local:

```bash
psql -U postgres -c "CREATE DATABASE avaliaedu;"
psql -U postgres -d avaliaedu -c "CREATE EXTENSION IF NOT EXISTS postgis;"
# execute todos os arquivos de database/migrations/ em ordem:
for f in database/migrations/*.sql; do psql -U postgres -d avaliaedu -f "$f"; done
```

> Em um projeto Supabase, rode os mesmos scripts pelo SQL Editor (PostGIS já vem disponível).

---

## ▶️ Executando localmente

### Back-end

```bash
cd backend
python -m venv venv
# Windows:  venv\Scripts\activate
# Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API em `http://localhost:8000` · Swagger em `http://localhost:8000/docs` · ReDoc em `/redoc`.

### Front-end

É estático e **detecta o ambiente automaticamente** (`localhost` → API local;
caso contrário → API de produção). Sirva a pasta `frontend/` por HTTP:

```bash
cd frontend
python -m http.server 5500
# abra http://localhost:5500
```

---

## ☁️ Deploy

- **Backend (Render):** importe o repositório em *New → Blueprint*; o `render.yaml`
  configura o serviço. Preencha no painel os segredos (`DATABASE_URL`,
  `SUPABASE_SERVICE_KEY`, `SECRET_KEY`, `ADMIN_SECRET_KEY`, `BASE_URL`).
- **Frontend (Vercel):** publique a pasta `frontend/` (`vercel --prod`). O `API_BASE`
  já aponta para o backend de produção fora de `localhost`.
- **Banco/Storage:** Supabase (PostgreSQL + PostGIS + buckets de Storage).

---

## 🔐 Autenticação

JWT (Bearer). O cadastro de **ADMIN** exige o campo `admin_token` igual ao
`ADMIN_SECRET_KEY` do ambiente. Rotas privadas exigem o header
`Authorization: Bearer <token>`.

---

## ⚠️ Problemas comuns

| Problema | Solução |
|---|---|
| `ModuleNotFoundError` | Ative o venv e rode `pip install -r requirements.txt` |
| `password authentication failed` | Confira `DATABASE_URL` no `.env` |
| `connection refused` | Verifique se o PostgreSQL/Supabase está acessível |
| Front não fala com a API | Confira `ALLOWED_ORIGINS` no backend e a URL em `API_BASE` |
| 1ª requisição lenta em produção | Cold start do Render (plano free) — normal |

---

## 👨‍💻 Equipe — Squad 32

Arthur de Oliveira Brito · Damily dos Santos Lima · Fabio Campos Chagas ·
Henrique Peixoto Oliveira · João Pedro Alves Seixas · Juscelino Santos de Andrade ·
Marconi Vianna Silveira · Rafael Florencio de Azevedo

---

## 📄 Licença

Projeto desenvolvido para fins acadêmicos e educacionais.
