import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="squad32_seed",
    user="postgres",
    password="0522"
)

cur = conn.cursor()

# Tabela usuarios
cur.execute("""
CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    senha_hash VARCHAR(255) NOT NULL,
    perfil VARCHAR(50) NOT NULL,
    nivel VARCHAR(50),
    serie VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

print("✅ Tabela 'usuarios' criada/verificada")

# Tabela provas
cur.execute("""
CREATE TABLE IF NOT EXISTS provas (
    id SERIAL PRIMARY KEY,
    titulo VARCHAR(255) NOT NULL,
    descricao TEXT,
    nivel VARCHAR(50) NOT NULL,
    serie VARCHAR(50) NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'RASCUNHO',
    nota_minima FLOAT DEFAULT 6.0,
    tempo_limite INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

print("✅ Tabela 'provas' criada/verificada")

# Tabela questoes
cur.execute("""
CREATE TABLE IF NOT EXISTS questoes (
    id SERIAL PRIMARY KEY,
    enunciado TEXT NOT NULL,
    prova_id INTEGER REFERENCES provas(id),
    nivel_dificuldade VARCHAR(50) DEFAULT 'MEDIO'
);
""")

print("✅ Tabela 'questoes' criada/verificada")

### Tabela alternativas ###
cur.execute("""
CREATE TABLE IF NOT EXISTS alternativas (
    id SERIAL PRIMARY KEY,
    texto TEXT NOT NULL,
    questao_id INTEGER REFERENCES questoes(id),
    alternativa_correta BOOLEAN DEFAULT FALSE
);
""")

print("✅ Tabela 'alternativas' criada/verificada")

cur.execute("""
CREATE TABLE IF NOT EXISTS inscricao (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER REFERENCES usuarios(id),
    prova_id INTEGER REFERENCES provas(id),
    data_inscricao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'INSCRITO',
    presencial BOOLEAN DEFAULT FALSE,
    pessoaDeficiente BOOLEAN DEFAULT FALSE        
);
""") 

print("✅ Tabela 'inscricao' criada/verificada")

cur.execute("""
CREATE TABLE IF NOT EXISTS localidade (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    estado VARCHAR(255) NOT NULL,
    cidade VARCHAR(255) NOT NULL,
    cep VARCHAR(20) NOT NULL,
    contato VARCHAR(255) NOT NULL,
    capacidade INTEGER NOT NULL 

);
""")

print("✅ Tabela 'localidade' criada/verificada")

cur.execute("""
CREATE TABLE IF NOT EXISTS respostas (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER REFERENCES inscricao(id),
    questao_id INTEGER REFERENCES questoes(id),
    alternativa INTEGER REFERENCES alternativas(id)
    
);
""")

print("✅ Tabela 'respostas' criada/verificada")

conn.commit()
cur.close()
conn.close()

print("🎉 Todas as tabelas foram criadas com sucesso!")