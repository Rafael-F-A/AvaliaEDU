from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from app.database import get_db
from app import models
from app.dependencies import get_usuario_atual
from app.services import relatorio_service

router = APIRouter(prefix="/relatorios", tags=["Relatórios"])


@router.get("/desempenho")
def obter_relatorio_desempenho(
    data_inicio: Optional[datetime] = Query(None),
    data_fim: Optional[datetime] = Query(None),
    prova_id: Optional[int] = Query(None),
    nivel: Optional[str] = Query(None),
    serie: Optional[str] = Query(None),
    componente_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(get_usuario_atual),
):
    """Retorna estatísticas de desempenho dos alunos. Requer perfil ADMIN."""
    if usuario_atual.perfil != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores podem acessar relatórios."
        )

    tentativas = relatorio_service.obter_tentativas_filtradas(
        db=db,
        data_inicio=data_inicio,
        data_fim=data_fim,
        prova_id=prova_id,
        nivel=nivel,
        serie=serie,
        componente_id=componente_id,
    )

    if not tentativas:
        return {
            "periodo": {"data_inicio": data_inicio, "data_fim": data_fim},
            "filtros_aplicados": {
                "prova_id": prova_id,
                "nivel": nivel,
                "serie": serie,
                "componente_id": componente_id,
            },
            "mensagem": "Nenhuma tentativa encontrada com os filtros aplicados.",
            "estatisticas_gerais": {},
            "distribuicao_por_nivel": [],
            "distribuicao_por_serie": [],
            "distribuicao_por_componente": [],
            "detalhes_por_prova": [],
        }

    return {
        "periodo": {"data_inicio": data_inicio, "data_fim": data_fim},
        "filtros_aplicados": {
            "prova_id": prova_id,
            "nivel": nivel,
            "serie": serie,
            "componente_id": componente_id,
        },
        "estatisticas_gerais": relatorio_service.calcular_estatisticas_gerais(tentativas),
        "distribuicao_por_nivel": relatorio_service.calcular_por_nivel(tentativas),
        "distribuicao_por_serie": relatorio_service.calcular_por_serie(tentativas),
        "distribuicao_por_componente": relatorio_service.calcular_por_componente(db, tentativas),
        "detalhes_por_prova": relatorio_service.calcular_detalhes_provas(db, tentativas),
    }


@router.get("/exportar")
def exportar_relatorio(
    data_inicio: Optional[datetime] = Query(None),
    data_fim: Optional[datetime] = Query(None),
    prova_id: Optional[int] = Query(None),
    nivel: Optional[str] = Query(None),
    serie: Optional[str] = Query(None),
    componente_id: Optional[int] = Query(None),
    formato: str = Query("excel", regex="^(excel|csv)$"),
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(get_usuario_atual),
):
    """Exporta relatório em Excel ou CSV. Requer perfil ADMIN."""
    if usuario_atual.perfil != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores podem exportar relatórios."
        )

    dados = relatorio_service.obter_dados_exportacao(
        db=db,
        data_inicio=data_inicio,
        data_fim=data_fim,
        prova_id=prova_id,
        nivel=nivel,
        serie=serie,
        componente_id=componente_id,
    )

    if not dados:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhum dado encontrado para exportar com os filtros aplicados."
        )

    if formato == "excel":
        arquivo = relatorio_service.exportar_excel(dados)
        return StreamingResponse(
            iter([arquivo]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=relatorio_desempenho.xlsx"}
        )

    arquivo = relatorio_service.exportar_csv(dados)
    return StreamingResponse(
        iter([arquivo]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=relatorio_desempenho.csv"}
    )