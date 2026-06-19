from fastapi import APIRouter, HTTPException

router = APIRouter(
    prefix="/provas",
    tags=["Provas"]
)

provas = []


@router.post("/")
def criar_prova(dados: dict):

    prova = {
        "id": len(provas) + 1,
        "titulo": dados["titulo"],
        "materia": dados["materia"],
        "data": dados["data"],
        "publicada": False
    }

    provas.append(prova)

    return {
        "mensagem": "Prova criada com sucesso",
        "dados": prova
    }


@router.get("/")
def listar_provas():

    return provas


@router.put("/{id}")
def editar_prova(id: int, dados: dict):

    for prova in provas:

        if prova["id"] == id:

            prova["titulo"] = dados["titulo"]
            prova["materia"] = dados["materia"]

            return {
                "mensagem": "Prova atualizada"
            }

    raise HTTPException(
        status_code=404,
        detail="Prova não encontrada"
    )


@router.delete("/{id}")
def excluir_prova(id: int):

    for prova in provas:

        if prova["id"] == id:

            provas.remove(prova)

            return {
                "mensagem": "Prova removida"
            }

    raise HTTPException(
        status_code=404,
        detail="Prova não encontrada"
    )


@router.post("/{id}/publicar")
def publicar_prova(id: int):

    for prova in provas:

        if prova["id"] == id:

            prova["publicada"] = True

            return {
                "mensagem": "Prova publicada com sucesso"
            }

    raise HTTPException(
        status_code=404,
        detail="Prova não encontrada"
    )