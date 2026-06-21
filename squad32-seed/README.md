# Squad 32 – Sistema de Gestão de Provas SEED

<p align="center">
  API para gerenciamento de provas, questões, simulados e certificações.<br>
  Projeto desenvolvido durante a <strong>Residência em Software</strong>.
</p>

---

## 📚 Sobre o Projeto

O **Squad 32 – Sistema de Gestão de Provas SEED** é uma API desenvolvida com foco na administração de avaliações educacionais, permitindo o gerenciamento de:

- 📄 Provas
- ❓ Questões
- 📝 Simulados
- 🏆 Certificações
- 👥 Usuários e autenticação

A aplicação foi construída seguindo uma arquitetura moderna baseada em APIs REST, utilizando autenticação JWT e integração com PostgreSQL/PostGIS.

---

## 🚀 Tecnologias Utilizadas

### 🔧 Back-end
- Python
- FastAPI
- SQLAlchemy
- JWT Authentication

### 🗄️ Banco de Dados
- PostgreSQL
- PostGIS

### 🎨 Front-end
- HTML
- CSS
- JavaScript

---

#️⃣ Estrutura do Projeto

```bash
squad32-seed/
│
├── backend/
│   ├── app/
│   ├── requirements.txt
│   └── .env
│
├── frontend/
│   └── index.html
│
├── database/
│   └── migrations/
│       ├── 010_usuarios.sql
│       ├── 020_provas.sql
│       ├── 030_questoes.sql
│       └── 040_alternativas.sql
│
└── README.md
```

---

## 🛢️ Banco de Dados

### ✅ Pré-requisitos

Antes de iniciar, certifique-se de possuir:

- PostgreSQL 15+
- Extensão PostGIS instalada

---

## 🏗️ Criando o Banco

```bash
psql -U postgres -c "CREATE DATABASE squad32_seed;"
```

---

## 📂 Executando as Migrações

Os scripts SQL estão localizados em:

```bash
database/migrations/
```

Execute os arquivos na ordem numérica:

```bash
psql -U postgres -d squad32_seed -f database/migrations/010_usuarios.sql

psql -U postgres -d squad32_seed -f database/migrations/020_provas.sql

psql -U postgres -d squad32_seed -f database/migrations/030_questoes.sql

psql -U postgres -d squad32_seed -f database/migrations/040_alternativas.sql
```

---

## ⚙️ Configuração do Ambiente

Crie um arquivo `.env` dentro da pasta `backend/`:

```env
DATABASE_URL=postgresql://postgres:senha@localhost:5432/squad32_seed
SECRET_KEY=37592
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

---

## ▶️ Execução do Projeto

### 🔹 Back-end

```bash
cd backend

python -m venv venv
```

#### Ativando ambiente virtual

##### Linux / MacOS

```bash
source venv/bin/activate
```

##### Windows

```bash
venv\Scripts\activate
```

#### Instalando dependências

```bash
pip install -r requirements.txt
```

#### Executando servidor

```bash
uvicorn app.main:app --reload
```

A API estará disponível em:

```bash
http://localhost:8000
```

---

### 🔹 Front-end

Abra o arquivo abaixo diretamente no navegador:

```bash
frontend/index.html
```

---

## 🔐 Autenticação

O sistema utiliza autenticação baseada em **JWT (JSON Web Token)** para proteção das rotas privadas.

---

## 🧪 Documentação da API

Após iniciar o servidor, a documentação automática estará disponível em:

### Swagger UI

```bash
http://localhost:8000/docs
```

### ReDoc

```bash
http://localhost:8000/redoc
```

---

## ⚠️ Problemas Comuns

| Problema | Solução |
|---|---|
| `psql: command not found` | Adicione o PostgreSQL ao PATH do sistema |
| `password authentication failed` | Verifique usuário e senha no `.env` |
| `ModuleNotFoundError` | Ative o ambiente virtual antes de executar |
| `connection refused` | Verifique se o PostgreSQL está em execução |

---

## 👨‍💻 Equipe

Projeto desenvolvido pela equipe **Squad 32** durante a Residência em Software.

---

## 📄 Licença

Este projeto foi desenvolvido para fins acadêmicos e educacionais.