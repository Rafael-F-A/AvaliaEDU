# AvaliaEDU — Auditoria Rigorosa (2026-06-21)

> Auditoria de front, back, banco, segurança e **conformidade com a documentação do
> Squad 32** (critérios de aceitação, histórias de usuário, edge cases, design de API).
> Metodologia: 96 agentes em paralelo + verificação adversarial (15 falso-positivos
> descartados) + **verificação ao vivo** (banco real Supabase, API de produção e backend
> rodando local). Escopo do código: `backend/`, `frontend/`, `database/` em
> `C:\Users\Public\avaliaedu` (a pasta `squad32-seed/` é cópia duplicada — ver C-02).

## Veredito

**MVP demonstrável, ainda NÃO deployável em produção.** A "trilha feliz" (criar prova,
cadastrar questão, iniciar/responder simulado, emitir/validar certificado) funciona quando
um único usuário segue o fluxo previsto. As falhas aparecem sob **concorrência**, **estados
de borda** (nota NULL, pausa expirada), **entradas fora de ordem** e **ataque** (XSS, CORS).
Há ainda um **bloqueador de dados**: o schema real do banco NÃO é reproduzível pelas
migrations versionadas.

| Severidade | Qtde |
|---|---|
| Alta (bloqueador) | 11 |
| Média | 22 |
| Baixa | 22 |
| Info | 2 |
| **Total confirmado** | **57** |
| Descartados na verificação adversarial | 15 |

Conformidade com a doc (itens checados):

| Grupo | Total | Atende | Parcial | Não atende | Não verificável |
|---|---|---|---|---|---|
| Critérios de aceitação | 15 | 11 | 4 | 0 | 0 |
| Histórias de usuário | 21 | 6 | 13 | 2 | 0 |
| Edge cases / tratamento de erro | 117 | 28 | 36 | 48 | 5 |
| Design de API (contrato) | 45 | 3 | 26 | 16 | 0 |

Leitura: os **critérios de aceitação funcionais** estão majoritariamente atendidos (MVP
entrega o que promete na superfície). O abismo está em **edge cases/resiliência** e no
**contrato de API documentado** (sem `/api/v1`, sem envelope padronizado, sem paginação
conforme spec) — aceitável para MVP acadêmico, **desde que declarado honestamente no pitch**.

---

## Provas ao vivo (o que foi testado em execução, não só lido)

1. **500 em `/simulados/{id}/resultado` — REPRODUZIDO.** Backend local, token do aluno dono
   da tentativa `id=14` (CONCLUIDA, `nota=NULL`). Resposta `HTTP 500`; traceback do servidor:
   ```
   File ".../app/services/simulado_service.py", line 379, in resultado_simulado
       "nota": float(tentativa.nota),
   TypeError: float() argument must be a string or a real number, not 'NoneType'
   ```
2. **CORS inseguro — CONFIRMADO na API de produção.** `GET https://avaliaedu-api.onrender.com/`
   com `Origin: https://evil.example` respondeu `access-control-allow-origin: *` **junto de**
   `access-control-allow-credentials: true` (combinação inválida/insegura).
3. **`nota NULL` em dado real.** `tentativas`: status `CONCLUIDA` total 12, com nota 11,
   `nota_null` = 1 (a tentativa 14). Há também 1 `PAUSADO` com nota NULL (id 23).
4. **Migrations não são fonte de verdade — CONFIRMADO.** `list_migrations` do Supabase = **vazio**;
   tabelas `reservas` (2 linhas) e `respostas` (43) existem no banco sem nenhum `.sql` que as crie;
   status `PAUSADO` existe em dado real mas falta no CHECK da migration `070_tentativas`.
5. **Telas do aluno quebradas — CONFIRMADO por código.** `_esc` e `confirmarExclusao` só
   existem em `admin.js` (linhas 2425 e 2355). `dashboard-aluno.html` carrega apenas
   `global.js`, `narrador.js`, `aluno.js` — logo as chamadas em `aluno.js` dão `ReferenceError`.
6. **Advisors de segurança do banco:** RLS **habilitado sem nenhuma policy** nas 14 tabelas do
   app (o backend usa service key e ignora RLS → sem defesa em profundidade); `spatial_ref_sys`
   sem RLS (ERROR, tabela de sistema PostGIS); `postgis` no schema `public` (WARN); funções
   `st_estimatedextent` (PostGIS) executáveis por `anon` (WARN, baixo risco).

---

## 🔴 Bloqueadores (severidade alta)

### A-01 · `resultado_simulado` quebra (500) com nota NULL — `bug`
`backend/app/services/simulado_service.py:379` · **reproduzido ao vivo**
Ao esgotar o tempo ou expirar a pausa, a tentativa vira `CONCLUIDA`/`REPROVADO` mas `nota`
nunca é setada (fica NULL). A validação da linha 351 passa e o código chega a `float(None)` → 500.
**Impacto:** aluno que estoura o tempo não consegue ver o resultado.
**Fix:** calcular e gravar `nota` ao encerrar por tempo/expiração; e/ou `float(tentativa.nota or 0)`.

### A-02 · Navegação do simulado assume resposta em ordem — `bug`
`simulado_service.py:204`
`responder_questao` valida só que a questão pertence à ordem, não que é a questão atual
(`ordem_ids[respondidas]`). A "próxima" é calculada por índice (`idx_atual+1`) enquanto
`questao_atual`/`retomar` usam contagem de respostas. Responder fora de ordem pula/repete
questões e pode dar `IndexError` (500). Compromete LOGICA-08.
**Fix:** validar `questao_id == ordem_ids[respondidas]` e derivar a próxima sempre por contagem.

### A-03 · Race condition em `criar_reserva` (oversell/duplicata) — `bug`
`reserva_service.py:73-114`
Padrão read-check-then-write sem `with_for_update`, sem constraint única, em READ COMMITTED.
Duas requisições concorrentes leem o mesmo estado → `vagas_restantes` negativo e/ou 2 reservas
ATIVAS. Casa com o bug histórico do "Aguarde infinito" (double-submit POST /reservas + iniciar).
*Latente:* os dados atuais (2 reservas) ainda não manifestaram, mas o código não tem proteção.
**Fix:** `SELECT ... FOR UPDATE` na linha do local + `UNIQUE` parcial `(aluno_id, prova_id) WHERE status='ATIVA'` + tratar `IntegrityError` com 409.

### A-04 · Vaga não devolvida quando reserva expira no `iniciar` — `dados`
`simulado_service.py:78-86`
No início presencial, reserva expirada vira `EXPIRADA` mas **não** incrementa
`vagas_restantes` (diferente do caminho lazy em `listar_minhas_reservas`). Vazamento de vagas:
local fica artificialmente lotado.
**Fix:** devolver a vaga também aqui; idealmente centralizar a lógica de expiração.

### A-05 · Resultado de certificação vaza o gabarito completo — `conformidade`/segurança
`routers/certificacoes.py:42` → reusa `resultado_simulado` (`simulado_service.py:367`)
A certificação reaproveita o resultado do simulado, que devolve `alternativa_correta` por
questão. LOGICA-12 manda mostrar **só aprovado/reprovado** na certificação. Qualquer aluno que
concluir vê o gabarito → compromete aplicações futuras.
**Fix:** caminho de resultado específico p/ certificação (sem `respostas`/`alternativa_correta`).

### A-06 · Tabelas `reservas` e `respostas` sem migration SQL — `conformidade`/dados
`database/migrations/` · **confirmado: `list_migrations` vazio**
Existem no banco e em `models.py`, mas nenhum `.sql` as cria. Recriar o banco só com as
migrations gera schema **incompleto** → quebra reserva presencial e gravação de respostas.
**Fix:** criar `050_reservas.sql`/`060_respostas.sql` (com FKs, defaults e índices UNIQUE) ou
adotar Alembic versionando a partir do estado atual.

### A-07 · Migration `070_tentativas` diverge do banco — `conformidade`/dados
`database/migrations/070_tentativas.sql`
Falta `PAUSADO` no CHECK de `status` e faltam colunas `ordem_alternativas` (JSON),
`modalidade`, `reserva_id`. (PAUSADO existe em dado real.) Recriar o banco quebraria
pausar/retomar e modalidade presencial.
**Fix:** alinhar a migration com `models.py` e o banco real.

### A-08 · XSS armazenado no painel admin — `segurança`
`frontend/js/admin.js` (166, 209, 587, 596, 1099, 1468-1469, 1951, 2257)
Campos do BD interpolados em `innerHTML` **sem** `_esc()` no texto visível (títulos de prova,
enunciados, nomes/e-mails de usuário, nomes de local, etc.). Um nome de aluno
`<img src=x onerror=...>` executa script **no navegador do admin autenticado**.
**Fix:** aplicar `_esc()` em todos os campos de dado interpolados (como já é feito nos `onclick`).

### A-09 · `confirmarExclusao()` indefinido quebra cancelamentos do aluno — `bug`
`frontend/js/aluno.js:438` (e 953-967) · **confirmado por código**
`confirmarExclusao` só existe em `admin.js`, não carregado pelo painel do aluno →
`ReferenceError`. Aluno não consegue cancelar inscrição nem reserva presencial; a vaga nunca
é liberada pela UI.
**Fix:** mover `confirmarExclusao` (e o modal) para `global.js`.

### A-10 · `_esc()` indefinido derruba a lista de provas do aluno — `bug`
`frontend/js/aluno.js:312` (e 322, 327) · **confirmado por código**
Provas com janela de inscrição caem num ramo que chama `_esc()` (inexistente no painel do
aluno) → `ReferenceError` dentro do `.map()` aborta a renderização inteira; a tela mostra
"Erro ao carregar provas." **Mesmo provas sem janela somem** (o map inteiro falha).
**Fix:** disponibilizar `_esc` em `global.js`; escapar também contexto de atributo (aspas simples em `onclick`).

### A-11 · XSS armazenado no painel do aluno — `segurança`
`frontend/js/aluno.js:342` (e 655-656, 893-918, 1034-1069, 1397)
Vários renderizadores injetam dados da API em `innerHTML` sem escape (título de prova,
`necessidades_especiais` digitado pelo próprio aluno, nome/endereço de local, etc.). Possível
roubo do token de sessão no cliente.
**Fix:** escapar toda interpolação (ou usar `textContent`/`createElement`).

---

## 🟠 Médias (22)

| ID | Cat | Achado | Local |
|---|---|---|---|
| backend-auth-seg-1 / config-3 | seg/config | **CORS `*` + credentials** (código e fixado no `render.yaml` de prod) | `main.py:27-35`, `render.yaml:20` |
| backend-auth-seg-5 | seg | Sem rate limit específico no login nem bloqueio por tentativas (EDGE-06) | `routers/auth.py:17` |
| backend-provas-4 | dados | `ordem_alternativas` lida no PDF mas **nunca persistida** no iniciar → ordem inconsistente PDF×tela | `simulado_service.py:150` |
| backend-provas-5 | conf | Edição/exclusão de questão de prova publicada não bloqueada | `questao_service.py:84` |
| backend-inscr-reserva-3 | bug | Validação presencial usa reserva ATIVA de **qualquer** aluno; quebra após 1ª reserva usada | `simulado_service.py:42-55` |
| backend-inscr-reserva-4 | bug | Iniciar simulado sem lock → tentativas EM_ANDAMENTO concorrentes duplicadas | `simulado_service.py:124-167` |
| backend-inscr-reserva-6 | perf | Relatório `/desempenho` carrega tudo em memória + N+1, sem paginação | `relatorio_service.py:46-160` |
| backend-cert-geo-pdf-5 | conf | `POST /certificacoes/{id}/certificado` grava `url_pdf` placeholder que não aponta p/ PDF | `certificacao_service.py:132` |
| backend-data-layer-3 | conf | Migration `120_modelos_questao` sem gabarito/distratores/variaveis/imagem_url + conflito NOT NULL | `database/migrations/120` |
| backend-data-layer-4 | conf | Migration `090_componentes` sem colunas `nivel`/`serie` | `database/migrations/090` |
| backend-data-layer-5 | conf | Migration `110_certificados` sem coluna `ativo` | `database/migrations/110` |
| backend-data-layer-6 | dados | `auditoria.usuario_id`: FK na migration mas ausente no banco/ORM (3-vias divergente) | `database/migrations/140` |
| frontend-aluno-3 | bug | Botão do modal trava em "Aguarde..." após iniciar prova **online** | `aluno.js:710` |
| frontend-aluno-5 | ux | Highlight da alternativa não aparece no Modo EJA (classe CSS divergente `alt-selecionada`) | `aluno.css:372` |
| frontend-aluno-6 | conf | Revisão de simulado não mostra escolhida×correta (LOGICA-11/HISTORIAS-12) | `aluno.js:1390` |
| frontend-aluno-7 | bug | Finalização manual não chama endpoint de finalizar — só `GET /resultado` | `aluno.js:1330` |
| frontend-core-1 | seg | `showToast` injeta mensagem via `innerHTML` (XSS refletido) | `global.js:250-253` |
| frontend-core-2 | conf | Senha aceita sem exigir números/letras (EDGE-03) | `auth.js:189-191` |
| frontend-landing-3 | ux | Único `<h1>` é a sigla "S-E-E-D", sem texto acessível | `index.html:21` |
| config-deploy-secrets-2 | qualidade | **Pasta `squad32-seed/` é cópia duplicada e obsoleta**, versionada | `squad32-seed/` |

(IDs completos preservados; CORS aparece como achado duplo auth-seg-1/config-3 por afetar código e deploy.)

## 🟡 Baixas e ℹ️ Info (24)

- **auth/segurança:** `SECRET_KEY` sem fallback (quebra se faltar a env); JWT não carrega `perfil`
  (diverge de API-01); `/admin/usuarios` duplica `/usuarios/` e expõe e-mails sem paginação;
  `POST /reservas` usa `get_usuario_atual` (qualquer perfil reserva); `gen_session.py` imprime
  JWT válido em stdout.
- **provas/dados:** `criar_questao` vincula questão a prova já PUBLICADA; cancelamento/expiração
  de reserva pode passar `vagas_restantes` da capacidade; `calcular_detalhes_provas` faz
  `float(nota_minima)` sem proteger None; ordem de alternativas reembaralhada ao avançar na
  certificação; `print()` de debug do logo no import (`pdf_certificado_service.py`).
- **data-layer (migrations × banco × ORM):** divergências em `locais` (CHECK capacidade, NOT NULL
  de `cep`, UNIQUE), `030_questoes` sem `imagem_url`, `provas.nivel` sem CHECK e `ProvaBase` não
  aceita `FUNDAMENTAL`.
- **frontend:** paginação do servidor não implementada (containers ficam vazios); métrica de
  Tentativas fixa em "—"; `res.json()` sem proteção a resposta não-JSON; logout inconsistente
  entre `global.js` e `auth.js`; sem detecção proativa de expiração de sessão; landing sem
  hambúrguer real; hero sem `<h2>`; nav "Provas" e "Resultados" apontam ambos p/ `#recursos`;
  input de validação de certificado sem `<label>`.
- **integração:** front envia `status=PUBLICADA` que `/provas` **não aceita** (filtro ignorado);
  registro central de endpoints em `global.js` tem caminhos errados/inexistentes.

---

## ✅ O que funciona bem (pontos fortes confirmados)

- **Autenticação/segurança server-side sólida:** bcrypt para senha; RBAC revalidado no banco a
  cada request (403); ADMIN exige `ADMIN_SECRET_KEY`; e-mail duplicado → 409; JWT HS256 com
  exp → 401; usuário BLOQUEADO barrado no login e em toda request; `senha_hash` nunca exposto.
- **Regras de prova:** gabarito **não** exposto durante a prova (schema `AlternativaPublica` sem
  `is_correta`) — CRITERIOS-10 ok; embaralhamento de questões e alternativas; bloqueio de
  tentativa duplicada (409); validação de questão (≥2 alternativas, exatamente 1 correta);
  publicação bloqueada sem questões; soft delete com proteção de integridade; `_safe_eval` do
  gerador rejeita import/dunder/os/exec.
- **Inscrição/reserva (caminho single-user):** valida prova publicada, janela de inscrição com
  timezone, compatibilidade de nível, duplicata/já-iniciado (409); `joinedload` evitando N+1.
- **Certificado:** PDF formal com brasão + QR p/ validação pública; código único via
  `secrets.token_hex` com unicidade no banco; validação pública anonimiza o nome; **geo PostGIS
  correto** (`ST_DWithin`/`ST_DistanceSphere`, ordenação por distância).
- **Frontend núcleo:** `apiFetch` com `AbortController`/timeout 60s, trata 401/204/não-JSON,
  injeta Bearer, remove Content-Type p/ FormData; `apiFetchAll` faz paginação real com trava
  anti-loop; narrador trata o gotcha `var`/`onclick` e os bugs do Chrome (cancel+speak).
- **Config/segredos:** `.env` **não** versionado (confirmado via `git check-ignore`); `.gitignore`
  cobre `.env`/venv; segredos como `sync:false` no `render.yaml`; `requirements.txt` 100% pinado.

---

## 🗄️ Banco de dados (ground truth + advisors)

- Schema real tem 14 tabelas de negócio + PostGIS; `models.py` reflete bem a estrutura geral.
- **Migrations versionadas ≠ banco real** (ver A-06/A-07 e médias de data-layer). O schema foi
  aplicado fora do mecanismo de migrations (`list_migrations` vazio).
- **Advisors de segurança:** RLS ON sem policy nas 14 tabelas (deny-all p/ anon via PostgREST,
  mas zero defesa em profundidade — o app depende 100% do backend com service key);
  `spatial_ref_sys` sem RLS (ERROR — tabela de sistema PostGIS, aceitável); `postgis` no schema
  `public` (WARN). Sem advisor de performance relevante além do esperado.

---

## 🛠️ Ordem de remediação sugerida

1. **Bloqueadores de dados (A-06, A-07 + data-layer médias):** alinhar migrations ao banco
   (criar `reservas`/`respostas`, corrigir `070`, etc.) — fundação para tudo.
2. **Telas quebradas do aluno (A-09, A-10):** mover `_esc` e `confirmarExclusao` p/ `global.js`.
   Correção pequena, impacto alto.
3. **500 em fluxos centrais (A-01, A-02 + `float(None)` no relatório):** tratar `nota` NULL;
   navegação por ordem persistida.
4. **Concorrência (A-03, A-04, inscr-reserva-4):** `with_for_update` + constraints UNIQUE
   parciais + CHECK `vagas_restantes >= 0`.
5. **Segurança (CORS, A-05, A-08, A-11, core-1):** lista explícita de origens (código +
   `render.yaml`); resultado de certificação sem gabarito; escapar todo `innerHTML`.
6. **Regras de negócio/conformidade:** persistir `ordem_alternativas`; bloquear edição de prova
   publicada; rate limit + bloqueio no login; complexidade de senha.
7. **Resiliência/arquitetura (pós-MVP — declarar no pitch):** paginação real, envelope
   padronizado, `/api/v1`, jobs/filas p/ geração e PDF, expiração proativa de sessão, job de
   liberação de reservas expiradas.
8. **Limpeza:** remover `squad32-seed/`, `print()` de debug, `/admin/usuarios` redundante,
   registro de endpoints morto em `global.js`.
