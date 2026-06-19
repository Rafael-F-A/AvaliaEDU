from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app import models, schemas
from app.dependencies import get_usuario_admin
from app.services import geolocalizacao_service as local_service
router = APIRouter(prefix="/locais", tags=["Locais"])


@router.post("/", response_model=schemas.LocalResponse, status_code=201)
def criar_local(
    dados: schemas.LocalCreate,
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_usuario_admin),
):
    return local_service.criar_local(dados, db)


@router.get("/", response_model=List[schemas.LocalResponse])
def listar_locais(
    cidade: str = None,
    db: Session = Depends(get_db),
):
    return local_service.listar_locais(db, cidade)


@router.get("/proximos", response_model=List[schemas.LocalProximoResponse])
def locais_proximos(
    latitude:  float = Query(..., ge=-90,  le=90),
    longitude: float = Query(..., ge=-180, le=180),
    raio_km:   float = Query(5.0, gt=0, le=100),
    limite:    int   = Query(20,  gt=0, le=100),
    db: Session = Depends(get_db),
):
    return local_service.locais_proximos(latitude, longitude, raio_km, limite, db)


@router.get("/{local_id}", response_model=schemas.LocalResponse)
def buscar_local(
    local_id: int,
    db: Session = Depends(get_db),
):
    return local_service.buscar_local(local_id, db)


@router.put("/{local_id}", response_model=schemas.LocalResponse)
def editar_local(
    local_id: int,
    dados: schemas.LocalCreate,
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_usuario_admin),
):
    return local_service.editar_local(local_id, dados, db)


@router.delete("/{local_id}", status_code=204)
def excluir_local(
    local_id: int,
    db: Session = Depends(get_db),
    admin: models.Usuario = Depends(get_usuario_admin),
):
    local_service.excluir_local(local_id, db)