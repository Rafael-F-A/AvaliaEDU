from fastapi import APIRouter, HTTPException

router = APIRouter(
    prefix="/questoes",
    tags=["Questões"]
)

''' banco temporário'''
questoes = []


''' POST para criar questão'''
@router.post("/")
def criar_questao(dados: dict):

    alternativas = dados.get("alternativas", [])
    if len(alternativas) < 2:
        raise HTTPException(
            status_code=400,
            detail="A questão precisa ter no mínimo 2 alternativas"
        )

    '''validar só uma alternativa correta'''
    corretas = [a for a in alternativas if a.get("correta")]
    if len(corretas) != 1:
        raise HTTPException(
            status_code=400,
            detail="A questão precisa ter exatamente 1 alternativa correta"
        )

    questao = {
        "id": len(questoes) + 1,
        "enunciado": dados["enunciado"],
        "prova_id": dados["prova_id"],
        "alternativas": alternativas
    }

    questoes.append(questao)

    return {
        "mensagem": "Questão criada com sucesso",
        "dados": questao
    }

'''GET para listar questões'''

@router.get("/")
def listar_questoes(prova_id: int = None):

    if prova_id:
        return [
            q for q in questoes
            if q["prova_id"] == prova_id
        ]

    return questoes


'''PUT - Editar questão'''
@router.put("/{id}")
def editar_questao(id: int, dados: dict):

    for questao in questoes:

        if questao["id"] == id:

            questao["enunciado"] = dados["enunciado"]

            return {
                "mensagem": "Questão atualizada"
            }

    raise HTTPException(
        status_code=404,
        detail="Questão não encontrada"
    )


'''DELETE - Excluir questão'''
@router.delete("/{id}")
def excluir_questao(id: int):

    for questao in questoes:

        if questao["id"] == id:

            questoes.remove(questao)

            return {
                "mensagem": "Questão removida"
            }

    raise HTTPException(
        status_code=404,
        detail="Questão não encontrada"
    )


''' GET para listar alternativas'''
@router.get("/{id}/alternativas")
def listar_alternativas(id: int):

    for questao in questoes:

        if questao["id"] == id:

            return questao["alternativas"]

    raise HTTPException(
        status_code=404,
        detail="Questão não encontrada"
    )