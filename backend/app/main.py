from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import os
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.database import get_db
from app import models
from app.routers import auth, provas, questoes, simulados, certificacoes, geracao, pdf
from app.dependencies import get_usuario_admin

load_dotenv()

# Configuração do rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
app = FastAPI(
    title="Sistema de Gestão de Provas - SEED",
    description="API para gerenciar provas, questões, simulados e certificações",
    version="1.0.0"
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusão dos routers
app.include_router(auth.router)
app.include_router(provas.router)
app.include_router(questoes.router)
app.include_router(simulados.router)
app.include_router(certificacoes.router)
app.include_router(geracao.router)
app.include_router(geracao.router)
app.include_router(pdf.router)

# Endpoints públicos
@app.get("/", tags=["Status"])
def root():
    return {"message": "API Squad 32 - Sistema de Gestão de Provas SEED"}

@app.get("/health", tags=["Status"])
def health_check():
    return {"status": "ok"}

@app.get("/admin/usuarios", tags=["Admin"], dependencies=[Depends(get_usuario_admin)])
def listar_usuarios(db: Session = Depends(get_db)):
    usuarios = db.query(models.Usuario).all()
    return {
        "total": len(usuarios),
        "usuarios": [
            {"id": u.id, "nome": u.nome, "email": u.email, "perfil": u.perfil, "status": u.status}
            for u in usuarios
        ],
    }