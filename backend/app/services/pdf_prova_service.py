import io
import json
import random
import os
import tempfile
from datetime import datetime, timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    HRFlowable, Table, TableStyle, PageBreak,
)
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app import models
from app.utils.storage import upload_certificado   # reusa o mesmo helper de upload

AZUL_SEED    = colors.HexColor("#0B57C5")
AMARELO_SEED = colors.HexColor("#F2C230")
CINZA_CLARO  = colors.HexColor("#F5F5F5")
CINZA_TEXTO  = colors.HexColor("#333333")
BORDA        = colors.HexColor("#CCCCCC")

PAGE_W, PAGE_H = A4
LETRAS = ["A", "B", "C", "D", "E", "F"]


# Estilos

def _estilos():
    return {
        "cabecalho": ParagraphStyle(
            "cabecalho",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=AZUL_SEED,
            alignment=TA_CENTER,
            spaceAfter=2,
        ),
        "subcabecalho": ParagraphStyle(
            "subcabecalho",
            fontName="Helvetica",
            fontSize=9,
            textColor=CINZA_TEXTO,
            alignment=TA_CENTER,
            spaceAfter=14,
        ),
        "titulo_prova": ParagraphStyle(
            "titulo_prova",
            fontName="Helvetica-Bold",
            fontSize=16,
            textColor=AZUL_SEED,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "meta_prova": ParagraphStyle(
            "meta_prova",
            fontName="Helvetica",
            fontSize=9,
            textColor=CINZA_TEXTO,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "aluno_label": ParagraphStyle(
            "aluno_label",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=CINZA_TEXTO,
            spaceAfter=2,
        ),
        "aluno_linha": ParagraphStyle(
            "aluno_linha",
            fontName="Helvetica",
            fontSize=10,
            textColor=CINZA_TEXTO,
            spaceAfter=10,
        ),
        "instrucoes": ParagraphStyle(
            "instrucoes",
            fontName="Helvetica",
            fontSize=8.5,
            textColor=CINZA_TEXTO,
            leading=13,
            spaceAfter=6,
        ),
        "numero_questao": ParagraphStyle(
            "numero_questao",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=AZUL_SEED,
            spaceAfter=4,
        ),
        "enunciado": ParagraphStyle(
            "enunciado",
            fontName="Helvetica",
            fontSize=10.5,
            textColor=CINZA_TEXTO,
            leading=15,
            alignment=TA_JUSTIFY,
            spaceAfter=8,
        ),
        "alternativa": ParagraphStyle(
            "alternativa",
            fontName="Helvetica",
            fontSize=10.5,
            textColor=CINZA_TEXTO,
            leading=14,
            leftIndent=16,
            spaceAfter=4,
        ),
        "rodape": ParagraphStyle(
            "rodape",
            fontName="Helvetica",
            fontSize=8,
            textColor=colors.HexColor("#888888"),
            alignment=TA_CENTER,
        ),
    }


def _borda_prova(canvas, doc):
    canvas.saveState()
    m = 18
    canvas.setStrokeColor(AZUL_SEED)
    canvas.setLineWidth(1)
    canvas.rect(m, m, PAGE_W - 2 * m, PAGE_H - 2 * m)
    # Rodapé com número de página
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#888888"))
    canvas.drawCentredString(
        PAGE_W / 2, 30,
        f"Página {doc.page} — SEED/SE — Uso exclusivo para aplicação presencial",
    )
    canvas.restoreState()


# Montagem do PDF de prova

def gerar_pdf_prova_aluno(
    prova: models.Prova,
    aluno: models.Usuario,
    questoes_ordenadas: list,        # list[models.Questao] na ordem do aluno
    alternativas_por_questao: dict,  # {questao_id: [models.Alternativa, ...]}
    numero_tentativa: int = 1,
) -> bytes:
    """Gera o PDF da prova personalizado para um aluno."""
    e = _estilos()
    buf = io.BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
        title=f"{prova.titulo} — {aluno.nome}",
        author="SEED/SE",
    )

    story = []

    # Cabeçalho
    story.append(Paragraph(
        "GOVERNO DO ESTADO DE SERGIPE — SECRETARIA DE ESTADO DA EDUCAÇÃO (SEED/SE)",
        e["cabecalho"],
    ))
    story.append(Paragraph(
        f"{prova.nivel.replace('_', ' ')} — {prova.serie} — {prova.tipo}",
        e["subcabecalho"],
    ))

    story.append(HRFlowable(width="100%", thickness=2, color=AZUL_SEED, spaceAfter=8))

    story.append(Paragraph(prova.titulo.upper(), e["titulo_prova"]))

    tempo_str = f"Tempo limite: {prova.tempo_limite} min" if prova.tempo_limite else "Sem tempo limite"
    story.append(Paragraph(
        f"{tempo_str}  |  {len(questoes_ordenadas)} questões",
        e["meta_prova"],
    ))

    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDA, spaceAfter=12))

    # Identificação do aluno
    id_table = Table(
        [
            [
                Paragraph("Nome:", e["aluno_label"]),
                Paragraph(aluno.nome, e["aluno_linha"]),
                Paragraph("Data:", e["aluno_label"]),
                Paragraph("___/___/______", e["aluno_linha"]),
            ],
            [
                Paragraph("Nível:", e["aluno_label"]),
                Paragraph(aluno.nivel or "—", e["aluno_linha"]),
                Paragraph("Turno:", e["aluno_label"]),
                Paragraph("________________", e["aluno_linha"]),
            ],
        ],
        colWidths=[2.2 * cm, 8.8 * cm, 1.8 * cm, 4.2 * cm],
        hAlign="LEFT",
    )
    id_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (1, 0), (1, 0), 0.5, BORDA),
        ("LINEBELOW", (3, 0), (3, 0), 0.5, BORDA),
        ("LINEBELOW", (1, 1), (1, 1), 0.5, BORDA),
        ("LINEBELOW", (3, 1), (3, 1), 0.5, BORDA),
    ]))
    story.append(id_table)
    story.append(Spacer(1, 8))

    # Instruções
    instrucoes_box = Table(
        [[Paragraph(
            "<b>INSTRUÇÕES:</b> Leia cada questão com atenção. "
            "Assinale apenas uma alternativa por questão. "
            "Não é permitido o uso de calculadora. "
            "Respostas a lápis não serão aceitas.",
            e["instrucoes"],
        )]],
        colWidths=[PAGE_W - 5 * cm],
        hAlign="LEFT",
    )
    instrucoes_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CINZA_CLARO),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDA),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("BORDERRADIUS", (0, 0), (-1, -1), 4),
    ]))
    story.append(instrucoes_box)
    story.append(Spacer(1, 16))

    # Questões
    for idx, questao in enumerate(questoes_ordenadas, start=1):
        story.append(Paragraph(f"Questão {idx}", e["numero_questao"]))
        story.append(Paragraph(questao.enunciado, e["enunciado"]))

        alts = alternativas_por_questao.get(questao.id, [])
        for i, alt in enumerate(alts):
            letra = LETRAS[i] if i < len(LETRAS) else str(i + 1)
            # Quadradinho de marcação + texto
            story.append(Paragraph(
                f"( {letra} )&nbsp;&nbsp;{alt.texto}",
                e["alternativa"],
            ))

        story.append(Spacer(1, 12))

        # Separador leve entre questões (exceto última)
        if idx < len(questoes_ordenadas):
            story.append(HRFlowable(
                width="100%", thickness=0.4,
                color=BORDA, spaceAfter=12,
            ))

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDA, spaceAfter=8))
    story.append(Paragraph(
        f"Código da prova: {prova.id} — Documento gerado em "
        f"{datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')} UTC",
        e["rodape"],
    ))

    doc.build(story, onFirstPage=_borda_prova, onLaterPages=_borda_prova)
    return buf.getvalue()


# Orquestrador: gera PDF para uma lista de alunos
def exportar_prova_para_alunos(
    prova_id: int,
    aluno_ids: list[int],
    db: Session,
) -> list[dict]:
    """
    Para cada aluno_id:
      1. Busca tentativa existente (usa a ordem já persistida).
      2. Se não existe tentativa, cria uma nova com ordem aleatória.
      3. Gera o PDF e faz upload para o Supabase Storage.
      4. Retorna lista com {aluno_id, aluno_nome, url_pdf, erro}.

    Chamado apenas por admin (verificado no router).
    """
    prova = db.query(models.Prova).filter(
        models.Prova.id == prova_id,
        models.Prova.deleted == False,
        models.Prova.status == "PUBLICADA",
    ).first()
    if not prova:
        raise HTTPException(404, "Prova não encontrada ou não publicada.")

    questoes_db = db.query(models.Questao).filter(
        models.Questao.prova_id == prova_id
    ).all()
    if not questoes_db:
        raise HTTPException(422, "A prova não possui questões.")

    questoes_map = {q.id: q for q in questoes_db}
    resultados = []

    for aluno_id in aluno_ids:
        aluno = db.query(models.Usuario).filter(
            models.Usuario.id == aluno_id,
            models.Usuario.perfil == "ALUNO",
        ).first()
        if not aluno:
            resultados.append({
                "aluno_id": aluno_id,
                "aluno_nome": None,
                "url_pdf": None,
                "erro": "Aluno não encontrado.",
            })
            continue

        try:
            # Busca tentativa EM_ANDAMENTO ou INSCRITO para esta prova
            tentativa = db.query(models.Tentativa).filter(
                models.Tentativa.aluno_id == aluno_id,
                models.Tentativa.prova_id == prova_id,
                models.Tentativa.status.in_(["INSCRITO", "EM_ANDAMENTO"]),
            ).first()

            if tentativa and tentativa.ordem_questoes:
                ordem_q = json.loads(tentativa.ordem_questoes) if isinstance(tentativa.ordem_questoes, str) else tentativa.ordem_questoes
                ordem_alt = json.loads(tentativa.ordem_alternativas) if isinstance(tentativa.ordem_alternativas, str) else (tentativa.ordem_alternativas or {})
            else:
                # Cria tentativa nova com ordem aleatória
                ordem_q = [q.id for q in questoes_db]
                random.shuffle(ordem_q)

                ordem_alt = {}
                for q in questoes_db:
                    alts = [a.id for a in q.alternativas]
                    random.shuffle(alts)
                    ordem_alt[str(q.id)] = alts

                tentativa = models.Tentativa(
                    aluno_id=aluno_id,
                    prova_id=prova_id,
                    tipo=prova.tipo,
                    status="INSCRITO",
                    data_inicio=datetime.now(timezone.utc),
                    ordem_questoes=json.dumps(ordem_q),
                    ordem_alternativas=json.dumps(ordem_alt),
                )
                db.add(tentativa)
                db.commit()
                db.refresh(tentativa)

            # Monta estruturas ordenadas
            questoes_ordenadas = [questoes_map[qid] for qid in ordem_q if qid in questoes_map]

            alts_map: dict[int, list] = {}
            for q in questoes_ordenadas:
                alts_db = {a.id: a for a in q.alternativas}
                ids_ordenados = ordem_alt.get(str(q.id), list(alts_db.keys()))
                alts_map[q.id] = [alts_db[aid] for aid in ids_ordenados if aid in alts_db]

            pdf_bytes = gerar_pdf_prova_aluno(
                prova=prova,
                aluno=aluno,
                questoes_ordenadas=questoes_ordenadas,
                alternativas_por_questao=alts_map,
            )

            # Upload para Supabase Storage
            nome_arquivo = f"provas/{prova_id}/aluno_{aluno_id}.pdf"
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_bytes)
                tmp_path = tmp.name

            try:
                url = upload_certificado(tmp_path, nome_arquivo)
            finally:
                os.unlink(tmp_path)

            resultados.append({
                "aluno_id": aluno_id,
                "aluno_nome": aluno.nome,
                "url_pdf": url,
                "erro": None,
            })

        except Exception as exc:
            db.rollback()
            resultados.append({
                "aluno_id": aluno_id,
                "aluno_nome": getattr(aluno, "nome", None),
                "url_pdf": None,
                "erro": str(exc),
            })

    return resultados