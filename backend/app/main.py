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
from app.routers import auth, provas, questoes, simulados, certificacoes, geracao, pdf, geolocalizacao, usuarios, reservas, componentes, inscricoes
from app.dependencies import get_usuario_admin
from app.routers.relatorios import router as relatorios_router
 
load_dotenv()
 
from app.rate_limit import limiter  # limiter compartilhado (mesma instância usada nos routers)
app = FastAPI(
    title="Sistema de Gestão de Provas - SEED",
    description="API para gerenciar provas, questões, simulados e certificações",
    version="1.0.0"
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
 
# CORS: origens explícitas. "*" + credentials é inválido/inseguro (rejeitado
# pelos navegadores) — se "*" estiver na lista, desligamos as credenciais.
# Em produção, ALLOWED_ORIGINS é definido no Render (ver render.yaml).
_origens_default = "https://frontend-ten-beryl-38.vercel.app,http://localhost:5500,http://127.0.0.1:5500"
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", _origens_default).split(",") if o.strip()]
_permite_credenciais = "*" not in ALLOWED_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=_permite_credenciais,
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
app.include_router(componentes.router)
app.include_router(inscricoes.router)

@app.get("/", tags=["Status"])
def root():
    return {"message": "API Squad 32 - Sistema de Gestão de Provas SEED"}
 
 
@app.get("/health", tags=["Status"])
def health_check():
    return {"status": "ok"}
 
 
# Endpoint /admin/usuarios removido (backend-auth-seg-7): duplicava GET /usuarios/
# e expunha e-mails sem paginação. Use GET /usuarios/ (já protegido por admin).