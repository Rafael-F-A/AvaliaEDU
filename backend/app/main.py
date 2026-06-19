from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import os
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

 
from app.database import get_db
from app import models
from app.routers import auth, provas, questoes, simulados, certificacoes, geracao, pdf, geolocalizacao, usuarios, reservas
from app.dependencies import get_usuario_admin
from app.routers.relatorios import router as relatorios_router
 
load_dotenv()
 
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
app = FastAPI(
    title="Sistema de Gestão de Provas - SEED",
    description="API para gerenciar provas, questões, simulados e certificações",
    version="1.0.0"
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
 
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(provas.router)
app.include_router(questoes.router)
app.include_router(simulados.router)
app.include_router(certificacoes.router)
app.include_router(geracao.router)
app.include_router(pdf.router)
app.include_router(geolocalizacao.router)
app.include_router(relatorios_router)
app.include_router(usuarios.router)
app.include_router(reservas.router)

@app.get("/", tags=["Status"])
def root():
    return {"message": "API Squad 32 - Sistema de Gestão de Provas SEED"}
 
 
@app.get("/health", tags=["Status"])
def health_check():
    return {"status": "ok"}

