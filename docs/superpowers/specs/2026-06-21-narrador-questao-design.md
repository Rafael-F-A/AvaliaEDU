# Narrador de Questão — Design

- **Data:** 2026-06-21
- **Status:** Design aprovado → próximo passo: plano de implementação
- **Tipo:** Feature de acessibilidade (frontend-only) no AvaliaEDU

## 1. Objetivo e contexto

Adicionar um **narrador de questão** (leitura em voz alta) na tela de prova do
aluno, para acessibilidade — especialmente para o público EJA (ex.: persona idosa
com baixa familiaridade digital). O projeto já tem um "Modo EJA" (fonte maior +
alto contraste). A tela de prova (`renderQuestaoExam` em `aluno.js`) já tem o
texto do enunciado e das alternativas disponível no cliente.

## 2. Requisitos (decididos no brainstorming)

- **Onde:** apenas na **prova do aluno** (simulado/certificação).
- **O que lê:** **enunciado + todas as alternativas**; e permitir **reler uma
  alternativa isolada**.
- **Acionamento:** botão **"Ouvir" sempre visível**, sob demanda, para qualquer
  aluno (não atrelado ao Modo EJA, mas convive bem com ele).
- **Controles:** Ouvir / **Pausar / Continuar** / Parar + **velocidade**
  (Devagar / Normal / Rápido).

## 3. Abordagem

**Web Speech API (`window.speechSynthesis`)** — 100% no cliente. Sem backend, sem
custo, sem latência, com suporte nativo a pausar/continuar/cancelar e a `rate`
(velocidade) e voz pt-BR na maioria dos dispositivos.

> Alternativa descartada: TTS no backend (Google/Azure/ElevenLabs/Piper) — voz
> melhor, porém com custo e/ou infra pesada (Render grátis não comporta bem),
> latência e storage. Pode ser uma evolução futura sem jogar fora a UI atual.

## 4. Arquitetura

### Módulo novo: `frontend/js/narrador.js`

Carregado em `dashboard-aluno.html` **antes** de `aluno.js`. Encapsula toda a
lógica de voz e expõe uma interface pequena (objeto global `Narrador`):

| Método | Função |
|---|---|
| `Narrador.suportado()` | retorna `true` se `speechSynthesis` existe |
| `Narrador.falar(textos)` | recebe um array de trechos e os enfileira para leitura |
| `Narrador.pausar()` / `continuar()` / `parar()` | controle de reprodução |
| `Narrador.setVelocidade(rate)` | define e **persiste** o rate (0.7 / 1.0 / 1.3) |
| `Narrador.onEstado(cb)` | registra callback chamado com `'parado' \| 'falando' \| 'pausado'` |

Responsabilidades internas (não vazam para o resto do app):
- **Seleção da voz pt-BR** — lida com o carregamento assíncrono de vozes
  (evento `voiceschanged`); fallback para a voz padrão se não houver pt-BR.
- **Fila de utterances** — quebra o conteúdo em trechos (ver §7).
- **Estado** — controla `falando/pausado/parado` e notifica via `onEstado`.

`aluno.js` apenas **usa** essa interface; não conhece os detalhes da Web Speech.

### Integração com o resto

- `dashboard-aluno.html`: adicionar a **barra de controles** na seção da prova
  (acima do enunciado) e `<script src="js/narrador.js">` antes de `aluno.js`.
- `aluno.js` / `renderQuestaoExam`:
  - compor os textos (enunciado + alternativas) e ligar o botão **Ouvir**;
  - inserir o **ícone 🔊 por alternativa** (com `stopPropagation`);
  - chamar `Narrador.parar()` ao renderizar nova questão e ao sair da prova.
- CSS (`aluno.css`): estilo da barra e dos ícones, herdando `eja-mode`.

## 5. UI na tela de prova

- **Barra do narrador** (acima do enunciado): `🔊 Ouvir` · `⏸ Pausar`/`▶ Continuar`
  (alterna conforme o estado) · `⏹ Parar` · velocidade **Devagar / Normal /
  Rápido** (3 botões; o ativo destacado, com `aria-pressed`).
- **Ícone 🔊 em cada `.alternativa-item`** — relê apenas aquela alternativa.
  Como clicar na alternativa **seleciona**, o ícone usa `event.stopPropagation()`
  (ouvir ≠ selecionar).
- Botões refletem o estado: **Pausar** só enquanto fala; **Continuar** só pausado.
- Acessibilidade: `aria-label` nos botões, foco visível, alvos grandes
  (compatíveis com os requisitos de toque do Modo EJA).

## 6. Comportamento / dados

- Texto da leitura completa: *"Questão {N}. {enunciado}. Opção A: {texto}. Opção
  B: {texto}. …"*. Alternativa só-imagem (sem texto) → *"Opção C: imagem."*.
- Leitura de uma alternativa: *"Opção A: {texto}."*.
- **Velocidade** é preferência do aluno → persistida em `localStorage`
  (`avaliaedu_narrador_rate`), como o Modo EJA.
- Um novo **Ouvir** cancela a fila anterior antes de começar (sem sobreposição).
- **Trocar de questão ou sair da prova → `Narrador.parar()`** (não vaza áudio).

## 7. Robustez e tratamento de erro

- **Bug do Chrome (corta falas longas ~15s):** em vez de um texto único e longo,
  **quebrar em trechos** (enunciado + cada alternativa = utterances separadas
  enfileiradas). Evita o corte e torna pausar/continuar mais suave.
- **Sem `speechSynthesis`** (raro): a barra aparece **desabilitada** com aviso
  "Seu navegador não suporta leitura em voz".
- **Sem voz pt-BR** no aparelho: usa a voz padrão (muda só o sotaque) — funciona.

## 8. Testes

- **No navegador (preview):** verificar `speechSynthesis.speaking`/`paused`, a
  troca dos botões por estado, a mudança de velocidade, o cancelamento ao navegar
  entre questões, e console sem erros.
- **Áudio real (checklist do usuário):** ouvir enunciado + alternativas;
  pausar/continuar; velocidade Devagar/Rápido; reler uma alternativa; confirmar
  que trocar de questão interrompe a fala. (Não é possível ouvir áudio no preview.)

## 9. Fora de escopo (YAGNI)

- TTS no backend / vozes premium.
- Narrador no admin, na revisão de resultados, ou auto-narração no Modo EJA.
- Descrição de imagens (apenas anuncia "imagem").

## 10. Arquivos afetados

- **Novo:** `frontend/js/narrador.js`
- **Editar:** `frontend/dashboard-aluno.html`, `frontend/js/aluno.js`,
  `frontend/css/aluno.css`
- **Backend:** nenhuma alteração.
