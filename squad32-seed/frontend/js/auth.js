/**
 * auth.js — AvaliaEDU / SEED
 * Responsável por: login, criação de conta, sessão JWT e logout.
 *
 * Campos que o backend espera:
 *   POST /auth/login    → { email, senha }
 *   POST /auth/register → { nome, email, senha, confirmar_senha, perfil,
 *                           nivel?, serie?, admin_token? }
 */

const API_BASE  = 'http://localhost:8000';
const TOKEN_KEY = 'avaliaedu_token';
const USR_KEY   = 'avaliaedu_usuario';

/* ──────────────────────────────────────────
   Sessão
────────────────────────────────────────── */

/** Retorna o token salvo ou null. */
function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

/** Retorna o objeto do usuário salvo ou null. */
function getUsuario() {
  try {
    return JSON.parse(localStorage.getItem(USR_KEY));
  } catch {
    return null;
  }
}

/** Remove sessão e volta para login. */
function logout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USR_KEY);
  window.location.href = 'auth.html';
}

/**
 * Redireciona para o dashboard correto se já houver sessão ativa.
 * Chame essa função no topo de cada página protegida.
 */
function redirecionarSeLogado() {
  const token   = getToken();
  const usuario = getUsuario();
  if (token && usuario) {
    const destino = usuario.perfil === 'ADMIN'
      ? 'dashboard-admin.html'
      : 'dashboard-aluno.html';
    window.location.href = destino;
  }
}

/**
 * Redireciona para login se NÃO houver sessão ativa.
 * Chame nas páginas que exigem autenticação.
 */
function exigirLogin() {
  const token   = getToken();
  const usuario = getUsuario();
  if (!token || !usuario) {
    window.location.href = 'auth.html';
  }
}

/* ──────────────────────────────────────────
   UI helpers
────────────────────────────────────────── */

function mostrarAlerta(msg, tipo = 'error') {
  const el = document.getElementById('alert-box');
  if (!el) return;
  el.textContent = msg;
  el.className   = `alert-box ${tipo} show`;
}

function esconderAlerta() {
  const el = document.getElementById('alert-box');
  if (el) el.className = 'alert-box';
}

function setBtnLoading(btnId, loading, textoOriginal) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  if (loading) {
    btn.disabled     = true;
    btn.innerHTML    = '<span class="btn-spinner"></span>Aguarde...';
  } else {
    btn.disabled     = false;
    btn.textContent  = textoOriginal;
  }
}

/* ──────────────────────────────────────────
   Abas (Entrar / Criar conta)
────────────────────────────────────────── */

function trocarAba(aba) {
  const abas = ['entrar', 'criar'];
  abas.forEach((a, i) => {
    const btn    = document.querySelectorAll('.tab-btn')[i];
    const painel = document.getElementById(`panel-${a}`);
    const ativo  = a === aba;
    if (btn)    btn.classList.toggle('active', ativo);
    if (painel) painel.classList.toggle('active', ativo);
  });
  esconderAlerta();
}

function toggleCamposAluno() {
  const perfil = document.getElementById('reg-perfil')?.value;
  if (!perfil) return;
  const camposAluno = document.getElementById('campos-aluno');
  const campoAdmin  = document.getElementById('campo-admin-token');
  if (camposAluno) camposAluno.style.display = perfil === 'ALUNO' ? '' : 'none';
  if (campoAdmin)  campoAdmin.style.display  = perfil === 'ADMIN' ? '' : 'none';
}

/* ──────────────────────────────────────────
   LOGIN  (US02 — POST /auth/login)
   Body: { email, senha }
────────────────────────────────────────── */

async function fazerLogin() {
  const email = document.getElementById('login-email')?.value.trim();
  const senha = document.getElementById('login-senha')?.value;

  if (!email || !senha) {
    mostrarAlerta('Preencha e-mail e senha.');
    return;
  }

  setBtnLoading('btn-entrar', true, 'Entrar');
  esconderAlerta();

  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ email, senha }),
    });

    const data = await res.json();

    if (!res.ok) {
      // O backend retorna 401 para credenciais erradas, 403 para bloqueado
      throw new Error(data?.detail || 'E-mail ou senha incorretos.');
    }

    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(USR_KEY, JSON.stringify(data.usuario));

    window.location.href = data.usuario.perfil === 'ADMIN'
      ? 'dashboard-admin.html'
      : 'dashboard-aluno.html';

  } catch (err) {
    mostrarAlerta(err.message);
  } finally {
    setBtnLoading('btn-entrar', false, 'Entrar');
  }
}

/* ──────────────────────────────────────────
   REGISTRO  (US01 — POST /auth/register)
   Body: { nome, email, senha, confirmar_senha, perfil, nivel?, serie?, admin_token? }
────────────────────────────────────────── */

async function criarConta() {
  const nome          = document.getElementById('reg-nome')?.value.trim();
  const email         = document.getElementById('reg-email')?.value.trim();
  const senha         = document.getElementById('reg-senha')?.value;
  const confirmarSenha= document.getElementById('reg-confirmar-senha')?.value;
  const perfil        = document.getElementById('reg-perfil')?.value;
  const nivel         = document.getElementById('reg-nivel')?.value;
  const serie         = document.getElementById('reg-serie')?.value.trim();
  const adminToken    = document.getElementById('reg-admin-token')?.value;

  // Validações locais
  if (!nome || !email || !senha || !confirmarSenha) {
    mostrarAlerta('Preencha todos os campos obrigatórios.');
    return;
  }
  if (nome.length < 2) {
    mostrarAlerta('O nome deve ter pelo menos 2 caracteres.');
    return;
  }
  if (senha.length < 8) {
    mostrarAlerta('A senha deve ter pelo menos 8 caracteres.');
    return;
  }
  if (senha !== confirmarSenha) {
    mostrarAlerta('As senhas não coincidem.');
    return;
  }
  if (perfil === 'ADMIN' && !adminToken) {
    mostrarAlerta('Informe a chave de administrador.');
    return;
  }
  if (perfil === 'ALUNO' && !nivel) {
    mostrarAlerta('Selecione o nível de ensino.');
    return;
  }

  setBtnLoading('btn-criar', true, 'Criar conta');
  esconderAlerta();

  // Monta o corpo exatamente como o backend espera
  const corpo = {
    nome,
    email,
    senha,
    confirmar_senha: confirmarSenha,  // campo obrigatório pelo Pydantic
    perfil,
  };

  if (perfil === 'ALUNO') {
    corpo.nivel = nivel;
    if (serie) corpo.serie = serie;
  }

  if (perfil === 'ADMIN') {
    corpo.admin_token = adminToken;  // campo correto no schema
  }

  try {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(corpo),
    });

    const data = await res.json();

    if (!res.ok) {
      // 409 = e-mail já existe, 400 = dados inválidos, 403 = token admin errado
      throw new Error(data?.detail || 'Erro ao criar conta. Verifique os dados.');
    }

    mostrarAlerta('Conta criada com sucesso! Faça login para entrar.', 'success');
    setTimeout(() => trocarAba('entrar'), 2000);

  } catch (err) {
    mostrarAlerta(err.message);
  } finally {
    setBtnLoading('btn-criar', false, 'Criar conta');
  }
}

/* ──────────────────────────────────────────
   Atalho de teclado — Enter envia o form
────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {
  // Redireciona se já estiver logado
  redirecionarSeLogado();

  // Enter no painel de login
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter') return;
    const painelEntrar = document.getElementById('panel-entrar');
    if (painelEntrar?.classList.contains('active')) fazerLogin();
  });
});