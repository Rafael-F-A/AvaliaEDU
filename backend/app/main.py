from fastapi import FastAPI, Depends  # <-- adicione ", Depends" aqui
from fastapi.middleware.cors import CORSMiddleware
from app.database import get_db, engine
from sqlalchemy.orm import Session
from app import models
models.Base.metadata.create_all(bind=engine)
from app.routers.auth import router as auth_router
from app.routers.provas import router as provas_router

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

@app.get("/")
def root():
    return {"message": "API Squad 32 - Sistema de Gestão de Provas SEED"}

@app.get("/usuarios")
def listar_usuarios(db: Session = Depends(get_db)):
    usuarios = db.query(models.Usuario).all()
    return {"usuarios": [{"id": u.id, "nome": u.nome, "email": u.email} for u in usuarios]}

@app.get("/health")
def health_check():
    return {"status": "ok"}

app.include_router(auth_router)

app.include_router(provas_router)