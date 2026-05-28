from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.database import get_db
from sqlalchemy.orm import Session
from app import models
from app.routers import auth, questoes, simulados, provas
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Sistema de Gestão de Provas - SEED",
    description="API para gerenciar provas, questões, simulados e certificações",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusão dos routers
app.include_router(auth.router)
app.include_router(questoes.router)
app.include_router(simulados.router)
app.include_router(provas.router)

# ENDPOINTS PÚBLICOS
@app.get("/")
def root():
    return {"message": "API Squad 32 - Sistema de Gestão de Provas SEED"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/usuarios")
def listar_usuarios(db: Session = Depends(get_db)):
    usuarios = db.query(models.Usuario).all()
    return {"usuarios": [{"id": u.id, "nome": u.nome, "email": u.email} for u in usuarios]}