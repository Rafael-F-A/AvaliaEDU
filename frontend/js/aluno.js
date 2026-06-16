/* ============================================================
   AvaliaEdu — aluno.js
   Lógica completa do Dashboard do Aluno.
   Depende de: global.js (apiFetch, showToast, openModal, etc.)
   ============================================================ */

/* ─────────────────────────────────────────
   1. ESTADO GLOBAL
   ─────────────────────────────────────── */

/** Usuário logado (preenchido no init) */
let usuario = null;

/** Cache de provas publicadas */
let provasDisponiveis = [];

/**
 * Estado completo do exame em andamento.
 * Zerado em cada nova prova iniciada.
 */
let exam = {
  tipo:                  null,   // 'SIMULADO' | 'CERTIFICACAO'
  provaId:               null,
  provaInfo:             null,   // objeto ProvaResponse
  tentativaId:           null,
  totalQuestoes:         0,
  indiceAtual:           0,      // posição atual no cache (0-based)
  questoesCache:         [],     // [{id, enunciado, alternativas, questao_numero}]
  respostasSalvas:       {},     // { questaoId: alternativaId }  (submetidas ao servidor)
  altSelecionadaAgora:   null,   // ID da alternativa selecionada na tela (não salva ainda)
  enviadas:              new Set(), // questaoIds já POSTadas em /responder
  timerInterval:         null,
  tempoRestante:         null,   // segundos
  certificadoId:         null,   // após gerar o cert de certificação
};

/* ─────────────────────────────────────────
   2. INICIALIZAÇÃO
   ─────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {
  usuario = requireAuth('ALUNO');
  if (!usuario) return;

  initUI(usuario);
  configurarNavegacao();
  configurarFiltros();
  carregarDashboard();
});

/* ─────────────────────────────────────────
   3. NAVEGAÇÃO ENTRE SEÇÕES
   ─────────────────────────────────────── */

/**
 * Navega para uma seção, carregando os dados necessários.
 * @param {'dashboard'|'provas'|'certificados'|'minha-area'|'realizar-prova'|'resultado'} secao
 */
function irPara(secao) {
  document.querySelectorAll('.dash-section').forEach(s => s.classList.add('hidden'));

  const el = document.getElementById(`section-${secao}`);
  if (el) el.classList.remove('hidden');

  // Sincroniza sidebar (apenas itens principais)
  document.querySelectorAll('.sidebar-nav .nav-link').forEach(a => {
    const target = a.dataset.section;
    a.classList.toggle('active', target === secao);
  });

  // Carrega dados da seção
  const loaders = {
    dashboard:      carregarDashboard,
    provas:         carregarProvasAluno,
    certificados:   carregarCertificados,
    'minha-area':   carregarMinhaArea,
  };
  if (loaders[secao]) loaders[secao]();

  window.scrollTo({ top: 0, behavior: 'smooth' });
}

/** Liga os cliques na sidebar aos trechos. */
function configurarNavegacao() {
  document.querySelectorAll('.sidebar-nav .nav-link').forEach(a => {
    a.addEventListener('click', (e) => {
      e.preventDefault();
      irPara(a.dataset.section);
    });
  });
}

/* ─────────────────────────────────────────
   4. DASHBOARD
   ─────────────────────────────────────── */

async function carregarDashboard() {
  try {
    const [historico, certs, provas] = await Promise.allSettled([
      apiFetch('/simulados/historico'),
      apiFetch('/certificacoes/historico'),
      apiFetch('/provas?status=PUBLICADA'),
    ]);

    const hist  = historico.status  === 'fulfilled' ? historico.value  : [];
    const certsV = certs.status     === 'fulfilled' ? certs.value      : [];
    const provasV = provas.status   === 'fulfilled' ? provas.value     : [];

    // Calcula média
    const finalizadas = hist.filter(t => t.nota !== null && t.nota !== undefined);
    const media = finalizadas.length
      ? (finalizadas.reduce((s, t) => s + t.nota, 0) / finalizadas.length).toFixed(1)
      : '—';

    // Próxima prova (primeira disponível por data_fim)
    const proxima = provasV
      .filter(p => p.data_fim && new Date(p.data_fim) > new Date())
      .sort((a, b) => new Date(a.data_fim) - new Date(b.data_fim))[0];

    // Preenche métricas
    document.getElementById('dash-proxima-data').textContent =
      proxima ? formatarData(proxima.data_fim) : '—';
    document.getElementById('dash-proxima-nome').textContent =
      proxima ? proxima.titulo : 'Nenhuma agendada';

    document.getElementById('dash-media').textContent = media;
    document.getElementById('dash-total-certs').textContent = certsV.length;
    document.getElementById('dash-provas-disponiveis').textContent = provasV.length;

    // Tabela desempenho recente (últimas 5)
    const tbody = document.getElementById('dash-desempenho');
    const recentes = hist.slice(0, 5);
    tbody.innerHTML = recentes.length
      ? recentes.map(t => `
          <tr>
            <td class="td-name">${t.prova_titulo || '—'}</td>
            <td class="td-muted">${formatarData(t.data_inicio || t.data_realizacao)}</td>
            <td>${formatarNota(t.nota)}</td>
            <td>${badgeResultado(t.resultado)}</td>
          </tr>`).join('')
      : `<tr><td colspan="4" class="table-empty">Nenhuma prova realizada ainda.</td></tr>`;

  } catch (err) {
    showToast('Erro ao carregar dashboard.', 'danger');
  }
}

/* ─────────────────────────────────────────
   5. SEÇÃO DE PROVAS
   ─────────────────────────────────────── */

async function carregarProvasAluno() {
  try {
    setLoading(true);
    const [provas, historico, certHist] = await Promise.all([
      apiFetch('/provas?status=PUBLICADA'),
      apiFetch('/simulados/historico'),
      apiFetch('/certificacoes/historico'),
    ]);

    provasDisponiveis = provas;

    // Mapa de tentativas por prova_id para mostrar estado correto
    const tentativasMap = {};
    [...historico, ...certHist].forEach(t => {
      const pid = t.prova_id;
      if (!pid) return;
      if (!tentativasMap[pid] || t.status === 'PAUSADO') tentativasMap[pid] = t;
    });

    renderTabelaProvas(provas, tentativasMap);

    // Histórico combinado
    const todosHistorico = [
      ...historico.map(t => ({ ...t, tipo: 'SIMULADO' })),
      ...certHist.map(t => ({ ...t, tipo: 'CERTIFICACAO' })),
    ].sort((a, b) =>
      new Date(b.data_inicio || b.data_realizacao) - new Date(a.data_inicio || a.data_realizacao));

    renderTabelaHistorico(todosHistorico);

    // Liga os filtros
    aplicarFiltroProvas();

  } catch (err) {
    showToast('Erro ao carregar provas.', 'danger');
  } finally {
    setLoading(false);
  }
}

function renderTabelaProvas(provas, tentativasMap = {}) {
  const tbody = document.getElementById('provas-aluno-tbody');
  if (!provas.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="table-empty">Nenhuma prova disponível no momento.</td></tr>`;
    return;
  }

  tbody.innerHTML = provas.map(p => {
    const tent = tentativasMap[p.id];
    const finalizado = tent?.status === 'FINALIZADO';
    const pausado    = tent?.status === 'PAUSADO';

    let acaoBtns = '';
    if (finalizado) {
      acaoBtns = `<button class="btn btn-ghost btn-sm"
        onclick="verResultadoHistorico(${tent.id}, '${p.tipo}')">Ver resultado</button>`;
    } else if (pausado) {
      acaoBtns = `
        <button class="btn btn-secondary btn-sm"
          onclick="retomarProva(${tent.id})">Retomar</button>`;
    } else {
      acaoBtns = `<button class="btn btn-primary btn-sm"
        onclick="iniciarProva(${p.id}, '${p.tipo}')">Iniciar</button>`;
    }

    return `
      <tr data-titulo="${(p.titulo || '').toLowerCase()}" data-tipo="${p.tipo}">
        <td class="td-name">${p.titulo}</td>
        <td class="td-muted">${nivelLabel(p.nivel)} ${p.serie ? '— ' + p.serie : ''}</td>
        <td>${badgeTipoProva(p.tipo)}</td>
        <td class="td-muted">${p.tempo_limite ? p.tempo_limite + ' min' : '—'}</td>
        <td class="td-muted">${p.data_fim ? formatarData(p.data_fim) : '—'}</td>
        <td><div class="td-actions">${acaoBtns}</div></td>
      </tr>`;
  }).join('');
}

function renderTabelaHistorico(historico) {
  const tbody = document.getElementById('historico-tbody');
  if (!historico.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="table-empty">Nenhuma prova realizada ainda.</td></tr>`;
    return;
  }

  tbody.innerHTML = historico.map(t => `
    <tr>
      <td class="td-name">${t.prova_titulo || '—'}</td>
      <td>${badgeTipoProva(t.tipo)}</td>
      <td class="td-muted">${formatarData(t.data_inicio || t.data_realizacao)}</td>
      <td><strong>${formatarNota(t.nota)}</strong></td>
      <td>${badgeResultado(t.resultado)}</td>
      <td><div class="td-actions">
        ${t.status !== 'FINALIZADO' && t.status !== undefined ? '' :
          `<button class="btn btn-ghost btn-sm"
            onclick="verResultadoHistorico(${t.id}, '${t.tipo}')">Ver resultado</button>`}
        ${t.certificado_id
          ? `<button class="btn btn-secondary btn-sm"
              onclick="baixarCertPorId(${t.certificado_id})">Cert. PDF</button>`
          : ''}
      </div></td>
    </tr>`).join('');
}

function configurarFiltros() {
  const busca   = document.getElementById('provas-aluno-busca');
  const tipoSel = document.getElementById('provas-aluno-tipo');
  const abaSel  = document.getElementById('provas-aluno-aba');

  if (busca)   busca.addEventListener('input',   debounce(aplicarFiltroProvas, 250));
  if (tipoSel) tipoSel.addEventListener('change', aplicarFiltroProvas);
  if (abaSel)  abaSel.addEventListener('change',  () => {
    const isDisp = abaSel.value === 'disponiveis';
    document.getElementById('painel-disponiveis').style.display = isDisp ? '' : 'none';
    document.getElementById('painel-historico').style.display   = isDisp ? 'none' : '';
  });
}

function aplicarFiltroProvas() {
  const busca = (document.getElementById('provas-aluno-busca')?.value || '').toLowerCase();
  const tipo  = document.getElementById('provas-aluno-tipo')?.value || '';

  document.querySelectorAll('#provas-aluno-tbody tr[data-titulo]').forEach(tr => {
    const titulo = tr.dataset.titulo || '';
    const tTipo  = tr.dataset.tipo   || '';
    const ok = titulo.includes(busca) && (!tipo || tTipo === tipo);
    tr.style.display = ok ? '' : 'none';
  });
}

/* ─────────────────────────────────────────
   6. INICIAR / RETOMAR PROVA
   ─────────────────────────────────────── */

/**
 * Abre o modal de escolha de modalidade (US23).
 * Substitui o disparo direto de iniciarProva — agora o aluno
 * escolhe Online ou Presencial antes de a tentativa ser criada.
 * @param {number} provaId
 * @param {'SIMULADO'|'CERTIFICACAO'} tipo
 */
function iniciarProva(provaId, tipo) {
  // Guarda contexto para uso após a confirmação
  modalidade.provaId = provaId;
  modalidade.tipo    = tipo;
  modalidade.localSelecionado = null;
  modalidade.reservaId        = null;

  // Reseta visual do modal para o passo 1
  _modalidadeMostrarPasso('escolha');
  document.getElementById('modal-modalidade-titulo').textContent =
    `Como deseja realizar esta prova?`;
  document.getElementById('card-online').classList.remove('selected');
  document.getElementById('card-presencial').classList.remove('selected');
  document.getElementById('btn-confirmar-modalidade').style.display = 'none';

  openModal('modal-modalidade');
}

/* ─────────────────────────────────────────
   ESTADO DO FLUXO DE MODALIDADE (US23-25)
   ─────────────────────────────────────── */
const modalidade = {
  provaId:            null,
  tipo:               null,
  escolha:            null,   // 'ONLINE' | 'PRESENCIAL'
  localSelecionado:   null,   // objeto {id, nome, ...}
  reservaId:          null,   // id da reserva criada (US27)
  coordenadas:        null,   // {latitude, longitude}
};

/** Alterna entre os passos do modal */
function _modalidadeMostrarPasso(passo) {
  ['escolha', 'locais', 'confirmar'].forEach(p => {
    document.getElementById(`modal-step-${p}`).style.display =
      p === passo ? '' : 'none';
  });
}

/** Passo 1 → Passo 2 ou confirma online direto */
function selecionarModalidade(escolha) {
  modalidade.escolha = escolha;
  document.getElementById('card-online').classList.toggle('selected', escolha === 'ONLINE');
  document.getElementById('card-presencial').classList.toggle('selected', escolha === 'PRESENCIAL');

  if (escolha === 'ONLINE') {
    // Online: apenas habilita o botão de confirmação
    document.getElementById('btn-confirmar-modalidade').style.display = '';
  } else {
    // Presencial: avança para lista de locais (US24-25)
    document.getElementById('btn-confirmar-modalidade').style.display = 'none';
    _modalidadeMostrarPasso('locais');
    _obterLocalizacaoECarregar();
  }
}

/** Volta do passo de locais para a escolha de modalidade */
function voltarEscolhaModalidade() {
  modalidade.localSelecionado = null;
  _modalidadeMostrarPasso('escolha');
  document.getElementById('btn-confirmar-modalidade').style.display =
    modalidade.escolha === 'ONLINE' ? '' : 'none';
}

/** Volta do passo de confirmação para a lista de locais */
function voltarListaLocais() {
  modalidade.localSelecionado = null;
  _modalidadeMostrarPasso('locais');
  document.getElementById('btn-confirmar-modalidade').style.display = 'none';
  // Re-renderiza lista para desmarcar seleção anterior
  _renderLocais(modalidade._listaCache || []);
}

/* ─────────────────────────────────────────
   GEOLOCALIZAÇÃO E LISTA DE LOCAIS (US24-25)
   ─────────────────────────────────────── */

/** Tenta obter a posição do usuário e então carrega os locais */
function _obterLocalizacaoECarregar() {
  const msgEl = document.getElementById('locais-geo-msg');
  const btnEl = document.getElementById('btn-recarregar-locais');

  if (!navigator.geolocation) {
    msgEl.textContent = 'Geolocalização não suportada pelo seu navegador.';
    btnEl.style.display = '';
    _carregarLocaisFallback();
    return;
  }

  msgEl.textContent = 'Obtendo sua localização...';
  btnEl.style.display = 'none';
  _renderLocaisLoading();

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      modalidade.coordenadas = {
        latitude:  pos.coords.latitude,
        longitude: pos.coords.longitude,
      };
      msgEl.textContent = `Localização obtida — buscando locais próximos.`;
      btnEl.style.display = '';
      carregarLocaisProximos();
    },
    (err) => {
      const msgs = {
        1: 'Permissão de localização negada. Mostrando todos os locais.',
        2: 'Não foi possível determinar sua localização.',
        3: 'Tempo esgotado ao obter localização.',
      };
      msgEl.textContent = msgs[err.code] || 'Erro ao obter localização.';
      btnEl.style.display = '';
      _carregarLocaisFallback();
    },
    { timeout: 8000, maximumAge: 60000 }
  );
}

/** Carrega locais usando as coordenadas obtidas (US25) */
async function carregarLocaisProximos() {
  if (!modalidade.coordenadas) {
    _carregarLocaisFallback();
    return;
  }

  const raio  = document.getElementById('select-raio').value;
  const { latitude, longitude } = modalidade.coordenadas;

  _renderLocaisLoading();
  try {
    const lista = await apiFetch(
      `/locais/proximos?latitude=${latitude}&longitude=${longitude}&raio_km=${raio}&limite=20`
    );
    modalidade._listaCache = lista;
    _renderLocais(lista);
    document.getElementById('locais-geo-msg').textContent =
      `${lista.length} local(is) encontrado(s) em até ${raio} km.`;
  } catch (err) {
    document.getElementById('locais-geo-msg').textContent =
      'Erro ao buscar locais. Tente novamente.';
    document.getElementById('locais-lista').innerHTML =
      `<p style="text-align:center; padding:24px; color:var(--c-text-muted); font-size:14px;">
        Não foi possível carregar os locais.
       </p>`;
  }
}

/** Fallback: lista todos os locais sem filtro de proximidade */
async function _carregarLocaisFallback() {
  _renderLocaisLoading();
  try {
    const lista = await apiFetch('/locais/');
    // Adiciona distancia_km nula para manter compatibilidade com _renderLocais
    modalidade._listaCache = lista.map(l => ({ ...l, distancia_km: null }));
    _renderLocais(modalidade._listaCache);
  } catch {
    document.getElementById('locais-lista').innerHTML =
      `<p style="text-align:center; padding:24px; color:var(--c-text-muted); font-size:14px;">
        Não foi possível carregar os locais.
       </p>`;
  }
}

/** Skeletons de carregamento */
function _renderLocaisLoading() {
  document.getElementById('locais-lista').innerHTML =
    [1, 2, 3].map(() => `<div class="local-skeleton"></div>`).join('');
}

/** Renderiza a lista de locais disponíveis */
function _renderLocais(lista) {
  const el = document.getElementById('locais-lista');
  if (!lista.length) {
    el.innerHTML = `
      <p style="text-align:center; padding:32px; color:var(--c-text-muted); font-size:14px;">
        Nenhum local com vagas disponíveis neste raio.<br>
        <small>Tente aumentar o raio de busca.</small>
      </p>`;
    return;
  }

  el.innerHTML = lista.map(local => {
    const semVagas  = local.vagas_restantes <= 0;
    const distTxt   = local.distancia_km != null
      ? `${local.distancia_km.toFixed(1)} km`
      : '—';
    const vagasCls  = semVagas ? ' sem-vagas' : '';
    const vagasTxt  = semVagas
      ? 'Sem vagas'
      : `${local.vagas_restantes} vaga(s)`;
    const disabled  = semVagas ? 'style="opacity:.5; pointer-events:none;"' : '';

    return `
      <div class="local-card" id="local-card-${local.id}"
           onclick="selecionarLocal(${local.id})" ${disabled}>
        <div class="local-card-icon">
          <svg viewBox="0 0 24 24" fill="currentColor" style="width:18px;height:18px;">
            <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/>
          </svg>
        </div>
        <div class="local-card-info">
          <p class="local-card-nome">${local.nome}</p>
          <p class="local-card-end">${local.endereco}${local.cidade ? ', ' + local.cidade : ''}</p>
        </div>
        <div class="local-card-meta">
          <span class="local-dist">${distTxt}</span>
          <span class="local-vagas${vagasCls}">${vagasTxt}</span>
        </div>
      </div>`;
  }).join('');
}

/** Passo 2 → Passo 3: seleciona local e exibe confirmação */
function selecionarLocal(localId) {
  const local = (modalidade._listaCache || []).find(l => l.id === localId);
  if (!local) return;

  modalidade.localSelecionado = local;

  // Destaca visualmente o card selecionado
  document.querySelectorAll('.local-card').forEach(c => c.classList.remove('selected'));
  const card = document.getElementById(`local-card-${localId}`);
  if (card) card.classList.add('selected');

  // Monta o painel de confirmação
  const distTxt = local.distancia_km != null
    ? `${local.distancia_km.toFixed(1)} km de distância`
    : '';
  document.getElementById('confirmar-local-info').innerHTML = `
    <p style="font-weight:600; font-size:15px; color:var(--c-primary); margin:0 0 6px;">${local.nome}</p>
    <p style="font-size:13px; color:var(--c-text-muted); margin:0 0 4px;">
      ${local.endereco}${local.cidade ? ' — ' + local.cidade : ''}
    </p>
    ${distTxt ? `<p style="font-size:12px; color:var(--c-text-muted); margin:0;">📍 ${distTxt}</p>` : ''}
    <p style="font-size:12px; color:var(--c-text-muted); margin:4px 0 0;">
      Vagas disponíveis: <strong>${local.vagas_restantes}</strong>
    </p>`;

  _modalidadeMostrarPasso('confirmar');
  document.getElementById('btn-confirmar-modalidade').style.display = '';
}

/* ─────────────────────────────────────────
   CONFIRMAÇÃO FINAL E INÍCIO DA PROVA
   ─────────────────────────────────────── */

/**
 * Executado ao clicar em "Confirmar e iniciar".
 * - Online  → chama API diretamente (US15/US19-20).
 * - Presencial → cria reserva (US27) e então inicia (US15).
 */
async function confirmarInicioProva() {
  closeModal('modal-modalidade');
  setLoading(true);

  const { provaId, tipo, escolha, localSelecionado } = modalidade;

  try {
    let dados;

    if (tipo === 'SIMULADO') {
      // Presencial: reservar vaga antes de iniciar (US27)
      if (escolha === 'PRESENCIAL') {
        const reserva = await apiFetch('/reservas/', {
          method: 'POST',
          body: JSON.stringify({
            prova_id: provaId,
            local_id: localSelecionado.id,
          }),
        });
        modalidade.reservaId = reserva.id;
      }

      dados = await apiFetch('/simulados/iniciar', {
        method: 'POST',
        body: JSON.stringify({
          prova_id:   provaId,
          modalidade: escolha,
          ...(escolha === 'PRESENCIAL' && { reserva_id: modalidade.reservaId }),
        }),
      });

    } else {
      // Certificação: solicitar → iniciar (sem pausa, US19-20)
      const sol = await apiFetch('/certificacoes/solicitar', {
        method: 'POST',
        body: JSON.stringify({ prova_id: provaId }),
      });
      dados = await apiFetch(`/certificacoes/iniciar/${sol.tentativa_id}`, { method: 'POST' });
    }

    // Monta estado global de exame
    const info = provasDisponiveis.find(p => p.id === provaId) || null;
    resetarExam();
    exam.tipo          = tipo;
    exam.provaId       = provaId;
    exam.provaInfo     = info;
    exam.tentativaId   = dados.tentativa_id;
    exam.totalQuestoes = dados.total_questoes;

    exam.questoesCache.push({
      id:             dados.questao_id,
      enunciado:      dados.enunciado,
      alternativas:   dados.alternativas || [],
      questao_numero: dados.questao_numero,
    });

    renderQuestaoExam();
    irPara('realizar-prova');

    const tempoSegundos = dados.tempo_restante_segundos
      ?? (info?.tempo_limite ? info.tempo_limite * 60 : null);
    if (tempoSegundos) iniciarTimer(tempoSegundos);

    if (escolha === 'PRESENCIAL' && modalidade.reservaId) {
      showToast(`Vaga reservada em ${localSelecionado.nome}. Boa prova!`, 'success', 4000);
    }

  } catch (err) {
    showToast(err.message || 'Não foi possível iniciar a prova.', 'danger');
  } finally {
    setLoading(false);
  }
}

/** Retoma um simulado pausado. */
async function retomarProva(tentativaId) {
  setLoading(true);
  try {
    const dados = await apiFetch(`/simulados/${tentativaId}/retomar`, { method: 'PATCH' });

    resetarExam();
    exam.tipo         = 'SIMULADO';
    exam.tentativaId  = tentativaId;
    exam.totalQuestoes = dados.total_questoes;

    exam.questoesCache.push({
      id:            dados.questao_id,
      enunciado:     dados.enunciado,
      alternativas:  dados.alternativas || [],
      questao_numero: dados.questao_numero,
    });

    renderQuestaoExam();
    irPara('realizar-prova');

    if (dados.tempo_restante_segundos) iniciarTimer(dados.tempo_restante_segundos);

  } catch (err) {
    showToast(err.message || 'Não foi possível retomar a prova.', 'danger');
  } finally {
    setLoading(false);
  }
}

function resetarExam() {
  pararTimer();
  Object.assign(exam, {
    tipo: null, provaId: null, provaInfo: null, tentativaId: null,
    totalQuestoes: 0, indiceAtual: 0, questoesCache: [],
    respostasSalvas: {}, altSelecionadaAgora: null,
    enviadas: new Set(), timerInterval: null,
    tempoRestante: null, certificadoId: null,
  });
}

/* ─────────────────────────────────────────
   7. RENDERIZAÇÃO DO EXAME
   ─────────────────────────────────────── */

/** Renderiza a questão atual (baseado em exam.indiceAtual). */
function renderQuestaoExam() {
  const q = exam.questoesCache[exam.indiceAtual];
  if (!q) return;

  const num   = q.questao_numero || (exam.indiceAtual + 1);
  const total = exam.totalQuestoes;

  // Cabeçalho
  document.getElementById('exam-titulo').textContent =
    exam.provaInfo?.titulo || 'Realizando prova';
  document.getElementById('exam-progresso').textContent =
    `Questão ${num} de ${total}`;
  document.getElementById('exam-questao-numero').textContent =
    `Questão ${num}`;
  document.getElementById('exam-enunciado').textContent = q.enunciado;

  // Imagem
  const imgWrap = document.getElementById('exam-imagem-wrap');
  const imgEl   = document.getElementById('exam-imagem');
  if (q.imagem_url) {
    imgEl.src = q.imagem_url;
    imgWrap.style.display = '';
  } else {
    imgWrap.style.display = 'none';
  }

  // Alternativas
  const altDiv    = document.getElementById('exam-alternativas');
  const subWrap   = document.getElementById('exam-subjetiva-wrap');
  const altSalva  = exam.respostasSalvas[q.id] ?? null;
  exam.altSelecionadaAgora = altSalva;

  if (q.alternativas && q.alternativas.length > 0) {
    altDiv.style.display = 'flex';
    subWrap.style.display = 'none';

    const letras = ['A', 'B', 'C', 'D', 'E', 'F'];
    altDiv.innerHTML = q.alternativas
      .sort((a, b) => (a.ordem ?? 0) - (b.ordem ?? 0))
      .map((alt, i) => {
        const ativa = altSalva === alt.id ? 'alt-selecionada' : '';
        return `
          <div class="alternativa-item ${ativa}" id="alt-${alt.id}"
               onclick="selecionarAlternativa(${alt.id}, this)" role="radio"
               aria-checked="${altSalva === alt.id}" tabindex="0">
            <span class="alt-letra">${letras[i] || i + 1}</span>
            <span class="alt-texto">${alt.texto}</span>
            ${alt.imagem_url
              ? `<img src="${alt.imagem_url}" alt="Imagem da alternativa"
                  style="max-width:200px;margin-top:8px;border-radius:6px;">`
              : ''}
          </div>`;
      }).join('');
  } else {
    // Questão subjetiva (sem alternativas)
    altDiv.style.display = 'none';
    subWrap.style.display = '';
    document.getElementById('exam-resposta-texto').value = '';
  }

  // Botões de navegação
  document.getElementById('btn-anterior').disabled = exam.indiceAtual === 0;
  document.getElementById('btn-proxima').textContent =
    exam.indiceAtual === exam.totalQuestoes - 1 ? 'Finalizar ✓' : 'Próxima →';

  // Alerta inline
  const alerta = document.getElementById('exam-alert');
  alerta.className = 'alert-box';
  alerta.textContent = '';

  atualizarNavGrid();
}

/** Seleciona uma alternativa visualmente (sem salvar ainda). */
function selecionarAlternativa(altId, el) {
  document.querySelectorAll('.alternativa-item').forEach(d => {
    d.classList.remove('alt-selecionada');
    d.setAttribute('aria-checked', 'false');
  });
  el.classList.add('alt-selecionada');
  el.setAttribute('aria-checked', 'true');
  exam.altSelecionadaAgora = altId;
}

/** Atualiza o grid de navegação por número. */
function atualizarNavGrid() {
  const grid = document.getElementById('exam-nav-grid');
  if (!grid) return;

  const atual = exam.indiceAtual;
  const total = exam.totalQuestoes;

  let html = '';
  for (let i = 0; i < total; i++) {
    const q = exam.questoesCache[i];
    const qId      = q?.id;
    const respondida = qId && exam.respostasSalvas[qId] !== undefined;
    const isAtual  = i === atual;

    let cls = 'nav-q-btn';
    if (isAtual)    cls += ' nav-q-atual';
    else if (respondida) cls += ' nav-q-ok';
    else if (q)     cls += ' nav-q-vista';

    html += `<button class="${cls}" onclick="irParaQuestaoN(${i})"
      title="Questão ${i + 1}">${i + 1}</button>`;
  }
  grid.innerHTML = html;
}

/** Vai para uma questão específica pelo índice (se já estiver no cache). */
async function irParaQuestaoN(indice) {
  if (indice === exam.indiceAtual) return;

  // Salva a resposta atual antes de pular
  if (exam.altSelecionadaAgora !== null
      && !exam.enviadas.has(exam.questoesCache[exam.indiceAtual]?.id)) {
    await salvarResposta(true); // silencioso
  }

  if (indice < exam.questoesCache.length) {
    exam.indiceAtual = indice;
    renderQuestaoExam();
  } else {
    showToast('Responda as questões anteriores para chegar aqui.', 'warning');
  }
}

/* ─────────────────────────────────────────
   8. SALVAR RESPOSTA E NAVEGAR
   ─────────────────────────────────────── */

/**
 * Salva a resposta da questão atual via API e avança para a próxima.
 * @param {boolean} silencioso – não exibe toast de confirmação
 * @returns {Promise<boolean>} true se foi possível avançar
 */
async function salvarResposta(silencioso = false) {
  const q   = exam.questoesCache[exam.indiceAtual];
  const alt = exam.altSelecionadaAgora;

  if (!alt) {
    if (!silencioso) {
      const alerta = document.getElementById('exam-alert');
      alerta.textContent = 'Selecione uma alternativa antes de salvar.';
      alerta.className = 'alert-box error show';
    }
    return false;
  }

  // Se já enviada, só atualiza localmente
  if (exam.enviadas.has(q.id)) {
    exam.respostasSalvas[q.id] = alt;
    return true;
  }

  try {
    const endpoint = exam.tipo === 'SIMULADO' ? '/simulados/responder' : '/certificacoes/responder';
    const resp = await apiFetch(endpoint, {
      method: 'POST',
      body: JSON.stringify({
        tentativa_id: exam.tentativaId,
        questao_id:   q.id,
        alternativa_id: alt,
      }),
    });

    exam.respostasSalvas[q.id] = alt;
    exam.enviadas.add(q.id);

    // Se o servidor retornou a próxima questão, adiciona ao cache
    if (!resp.finalizado && resp.proxima_questao_id) {
      const jaTemProxima = exam.questoesCache.length > exam.indiceAtual + 1;
      if (!jaTemProxima) {
        exam.questoesCache.push({
          id:            resp.proxima_questao_id,
          enunciado:     resp.proxima_questao_enunciado,
          alternativas:  resp.proximas_alternativas || [],
          questao_numero: resp.questao_numero,
        });
        exam.totalQuestoes = resp.total_questoes || exam.totalQuestoes;
      }
    }

    if (!silencioso) showToast('Resposta salva!', 'success', 1800);

    // Prova finalizada automaticamente pelo servidor
    if (resp.finalizado) {
      pararTimer();
      await carregarResultado();
      return true;
    }

    return true;

  } catch (err) {
    if (!silencioso) showToast(err.message || 'Erro ao salvar resposta.', 'danger');
    return false;
  }
}

/** Botão Anterior / Próxima */
async function navegarQuestao(direcao) {
  if (direcao === 1) {
    // Avançar: salva primeiro
    const q = exam.questoesCache[exam.indiceAtual];
    const temAlt = exam.questoesCache[exam.indiceAtual]?.alternativas?.length > 0;

    if (temAlt && exam.altSelecionadaAgora === null && !exam.enviadas.has(q?.id)) {
      document.getElementById('exam-alert').textContent = 'Selecione uma alternativa.';
      document.getElementById('exam-alert').className   = 'alert-box error show';
      return;
    }

    const isUltima = exam.indiceAtual === exam.totalQuestoes - 1;

    if (exam.altSelecionadaAgora !== null && !exam.enviadas.has(q?.id)) {
      const ok = await salvarResposta(true);
      if (!ok) return;
    }

    if (isUltima) {
      confirmarFinalizarProva();
      return;
    }

    if (exam.indiceAtual < exam.questoesCache.length - 1) {
      exam.indiceAtual++;
      exam.altSelecionadaAgora = exam.respostasSalvas[exam.questoesCache[exam.indiceAtual]?.id] ?? null;
      renderQuestaoExam();
    } else {
      showToast('Sem próxima questão disponível ainda.', 'warning');
    }

  } else {
    // Voltar
    if (exam.indiceAtual > 0) {
      exam.indiceAtual--;
      exam.altSelecionadaAgora = exam.respostasSalvas[exam.questoesCache[exam.indiceAtual]?.id] ?? null;
      renderQuestaoExam();
    }
  }
}

/* ─────────────────────────────────────────
   9. TIMER
   ─────────────────────────────────────── */

function iniciarTimer(totalSegundos) {
  pararTimer();
  exam.tempoRestante = Math.floor(totalSegundos);

  atualizarDisplayTimer();

  exam.timerInterval = setInterval(() => {
    exam.tempoRestante--;
    atualizarDisplayTimer();

    if (exam.tempoRestante <= 0) {
      pararTimer();
      showToast('Tempo esgotado! Enviando prova automaticamente.', 'warning', 4000);
      finalizarProva();
    }

    // Alerta vermelho nos últimos 5 minutos
    const timerEl = document.getElementById('exam-timer');
    if (timerEl && exam.tempoRestante <= 300) {
      timerEl.style.color = 'var(--c-danger)';
      timerEl.style.fontWeight = '700';
    }
  }, 1000);
}

function pararTimer() {
  if (exam.timerInterval) {
    clearInterval(exam.timerInterval);
    exam.timerInterval = null;
  }
}

function atualizarDisplayTimer() {
  const el = document.getElementById('exam-timer');
  if (!el) return;
  const s = exam.tempoRestante ?? 0;
  const mm = String(Math.floor(s / 60)).padStart(2, '0');
  const ss = String(s % 60).padStart(2, '0');
  el.textContent = `⏱ ${mm}:${ss}`;
}

/* ─────────────────────────────────────────
   10. FINALIZAR / SAIR DA PROVA
   ─────────────────────────────────────── */

function confirmarFinalizarProva() {
  const pendentes = exam.totalQuestoes - Object.keys(exam.respostasSalvas).length;

  const msg = document.getElementById('modal-finalizar-msg');
  if (msg) {
    msg.textContent = pendentes > 0
      ? `Você ainda tem ${pendentes} questão(ões) sem resposta. Ao finalizar, a nota será calculada com base nas respondidas. Deseja continuar?`
      : 'Ao finalizar, sua nota será calculada e não será possível alterar as respostas.';
  }
  openModal('modal-finalizar');
}

async function finalizarProva() {
  closeModal('modal-finalizar');
  pararTimer();
  await carregarResultado();
}

function confirmarSairProva() {
  openModal('modal-sair-prova');
}

async function pausarESair() {
  closeModal('modal-sair-prova');
  if (exam.tipo === 'SIMULADO' && exam.tentativaId) {
    try {
      await apiFetch(`/simulados/${exam.tentativaId}/pausar`, { method: 'PATCH' });
      showToast('Prova pausada. Você pode retomá-la depois.', 'info');
    } catch {
      // Ignora erro de pausa — vai sair mesmo assim
    }
  }
  resetarExam();
  irPara('provas');
}

/* ─────────────────────────────────────────
   11. RESULTADO
   ─────────────────────────────────────── */

async function carregarResultado() {
  setLoading(true);
  try {
    const endpoint = exam.tipo === 'SIMULADO'
      ? `/simulados/${exam.tentativaId}/resultado`
      : `/certificacoes/${exam.tentativaId}/resultado`;

    const res = await apiFetch(endpoint);

    irPara('resultado');

    // Métricas
    const nota = res.nota ?? 0;
    const acertos = res.total_acertos ?? 0;
    const total   = res.total_questoes ?? 1;
    const pct     = Math.round((acertos / total) * 100);
    const aprovado = res.status === 'APROVADO';

    document.getElementById('res-nota').textContent       = formatarNota(nota);
    document.getElementById('res-prova-nome').textContent = res.prova_titulo || 'Prova';
    document.getElementById('res-percentual').textContent = `${pct}%`;
    document.getElementById('res-acertos-label').textContent = `${acertos} de ${total} acertos`;
    document.getElementById('res-resultado').textContent  = aprovado ? 'Aprovado' : 'Reprovado';
    document.getElementById('res-resultado').style.color  = aprovado ? 'var(--c-success)' : 'var(--c-danger)';
    document.getElementById('res-nota-minima').textContent =
      exam.provaInfo?.nota_minima ? `Nota mínima: ${exam.provaInfo.nota_minima}` : '';

    const badge = document.getElementById('res-badge-resultado');
    badge.textContent  = aprovado ? 'Aprovado' : 'Reprovado';
    badge.className    = `badge ${aprovado ? 'badge-aprovado' : 'badge-reprovado'}`;

    // Gabarito
    const tbody = document.getElementById('res-gabarito-tbody');
    if (res.respostas && res.respostas.length) {
      tbody.innerHTML = res.respostas.map((r, i) => {
        const ok = r.correta;
        return `<tr>
          <td>${i + 1}</td>
          <td class="td-muted" style="max-width:300px; white-space:normal;">
            ${r.enunciado || r.questao_id || '—'}
          </td>
          <td>
            <span class="badge ${ok ? 'badge-aprovado' : 'badge-reprovado'}">
              ${ok ? 'Correto' : 'Errado'}
            </span>
          </td>
        </tr>`;
      }).join('');
    } else {
      tbody.innerHTML = `<tr><td colspan="3" class="table-empty">Gabarito não disponível.</td></tr>`;
    }

    // Certificado (só para CERTIFICACAO aprovada)
    if (exam.tipo === 'CERTIFICACAO' && aprovado) {
      await gerarCertificado();
    } else {
      document.getElementById('res-cert-status').textContent = 'Não disponível';
      document.getElementById('res-cert-codigo').textContent  = exam.tipo !== 'CERTIFICACAO'
        ? 'Apenas em certificações' : 'Nota insuficiente';
      document.getElementById('res-cert-card').style.display = 'none';
      document.getElementById('btn-baixar-cert').style.display = 'none';
    }

  } catch (err) {
    showToast(err.message || 'Erro ao carregar resultado.', 'danger');
  } finally {
    setLoading(false);
  }
}

async function gerarCertificado() {
  try {
    const cert = await apiFetch(`/certificacoes/${exam.tentativaId}/certificado`, {
      method: 'POST',
    });

    exam.certificadoId = cert.id;

    document.getElementById('res-cert-status').textContent = 'Disponível';
    document.getElementById('res-cert-codigo').textContent  = cert.codigo;
    document.getElementById('res-cert-codigo-display').textContent = cert.codigo;
    document.getElementById('res-cert-card').style.display = '';

    if (cert.url_pdf) {
      document.getElementById('btn-baixar-cert').style.display = '';
    }

  } catch (err) {
    document.getElementById('res-cert-status').textContent = 'Erro ao gerar';
    document.getElementById('res-cert-codigo').textContent  = err.message || 'Tente novamente.';
  }
}

async function baixarCertificado() {
  const id = exam.certificadoId;
  if (!id) { showToast('Certificado não disponível.', 'warning'); return; }

  try {
    // Abre a URL do PDF diretamente, passando o token no header não é possível via <a href>.
    // Solicitamos via fetch e abrimos como blob.
    const token = getToken();
    const resp = await fetch(`${API_BASE}/certificacoes/${id}/download`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    if (!resp.ok) throw new Error('Erro ao baixar PDF.');
    const blob = await resp.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `certificado-${id}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

/** Baixa cert de um certificado já emitido (por ID do certificado). */
async function baixarCertPorId(certId) {
  try {
    const token = getToken();
    const resp = await fetch(`${API_BASE}/certificacoes/${certId}/download`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    if (!resp.ok) throw new Error('Erro ao baixar PDF.');
    const blob = await resp.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `certificado-${certId}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

/** Ver resultado de uma tentativa histórica. */
async function verResultadoHistorico(tentativaId, tipo) {
  exam.tentativaId  = tentativaId;
  exam.tipo         = tipo;
  exam.provaInfo    = null;
  exam.certificadoId = null;
  await carregarResultado();
}

/* ─────────────────────────────────────────
   12. CERTIFICADOS
   ─────────────────────────────────────── */

async function carregarCertificados() {
  const tbody = document.getElementById('certs-tbody');
  tbody.innerHTML = `<tr><td colspan="5" class="table-empty">Carregando...</td></tr>`;

  try {
    const lista = await apiFetch('/certificacoes/historico');
    const comCert = lista.filter(t => t.certificado_id);

    if (!comCert.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="table-empty">Nenhum certificado emitido ainda.</td></tr>`;
      return;
    }

    tbody.innerHTML = comCert.map(t => `
      <tr>
        <td class="td-name">${t.prova_titulo || '—'}</td>
        <td><strong>${formatarNota(t.nota)}</strong></td>
        <td class="td-muted">${formatarData(t.data_realizacao)}</td>
        <td>
          <code style="font-size:12px; background:var(--c-bg); padding:3px 8px;
            border-radius:4px; border:1px solid var(--c-border);">
            —
          </code>
        </td>
        <td><div class="td-actions">
          <button class="btn btn-primary btn-sm"
            onclick="baixarCertPorId(${t.certificado_id})">Baixar PDF</button>
        </div></td>
      </tr>`).join('');

  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" class="table-empty">Erro: ${err.message}</td></tr>`;
  }
}

/* ─────────────────────────────────────────
   13. MINHA ÁREA
   ─────────────────────────────────────── */

async function carregarMinhaArea() {
  try {
    const [me, hist, certs] = await Promise.all([
      apiFetch('/auth/me'),
      apiFetch('/simulados/historico'),
      apiFetch('/certificacoes/historico'),
    ]);

    // Perfil
    document.getElementById('area-nome').textContent      = me.nome || '—';
    document.getElementById('area-email').value           = me.email || '';
    document.getElementById('area-nivel').value           = nivelLabel(me.nivel) || '—';
    document.getElementById('area-serie').value           = me.serie || '—';
    document.getElementById('area-nivel-serie').textContent =
      [nivelLabel(me.nivel), me.serie].filter(Boolean).join(' — ') || '—';

    const ini = iniciais(me.nome);
    const bigAvatar = document.getElementById('area-avatar-big');
    if (bigAvatar) bigAvatar.textContent = ini;

    // Totais
    document.getElementById('area-total-provas').textContent = hist.length;
    document.getElementById('area-total-certs').textContent  =
      certs.filter(t => t.certificado_id).length;

    // Histórico combinado
    const todosCombinados = [
      ...hist.map(t => ({ ...t, tipoLabel: 'Simulado' })),
      ...certs.map(t => ({ ...t, tipoLabel: 'Certificação' })),
    ].sort((a, b) =>
      new Date(b.data_inicio || b.data_realizacao || 0)
      - new Date(a.data_inicio || a.data_realizacao || 0));

    const tbody = document.getElementById('area-historico-tbody');
    tbody.innerHTML = todosCombinados.length
      ? todosCombinados.map(t => `
          <tr>
            <td class="td-name">${t.prova_titulo || '—'}</td>
            <td class="td-muted">${formatarData(t.data_inicio || t.data_realizacao)}</td>
            <td><strong>${formatarNota(t.nota)}</strong></td>
            <td>${badgeResultado(t.resultado)}</td>
          </tr>`).join('')
      : `<tr><td colspan="4" class="table-empty">Nenhuma tentativa registrada.</td></tr>`;

  } catch (err) {
    showToast('Erro ao carregar perfil.', 'danger');
  }
}

/** Abre um prompt simples para atualizar o nome. */
function editarPerfil() {
  const novoNome = prompt('Novo nome:', document.getElementById('area-nome').textContent.trim());
  if (!novoNome || !novoNome.trim()) return;

  apiFetch('/usuarios/me/perfil', {
    method: 'PATCH',
    body: JSON.stringify({ nome: novoNome.trim() }),
  }).then(() => {
    showToast('Perfil atualizado!', 'success');
    document.getElementById('area-nome').textContent = novoNome.trim();
    const ini = iniciais(novoNome.trim());
    document.getElementById('user-avatar').textContent   = ini;
    document.getElementById('area-avatar').textContent   = ini;
    document.getElementById('area-avatar-big').textContent = ini;
  }).catch(err => showToast(err.message, 'danger'));
}

/* ─────────────────────────────────────────
   14. UTILITÁRIOS LOCAIS
   ─────────────────────────────────────── */

/** Converte enum de nível para label legível. */
function nivelLabel(nivel) {
  const map = {
    FUNDAMENTAL_I:  'Fundamental I',
    FUNDAMENTAL_II: 'Fundamental II',
    MEDIO:          'Médio',
    ENEM:           'ENEM',
    EJA:            'EJA',
  };
  return map[nivel] || nivel || '—';
}