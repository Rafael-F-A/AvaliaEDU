/**
 * landing-page.js — AvaliaEDU / SEED
 *
 * Responsável por:
 *   1. Redirecionar para o dashboard se o usuário já estiver logado
 *   2. Scroll suave para âncoras internas (nav + botão "Saiba Mais")
 *   3. Sombra no header ao rolar a página
 *   4. Animação de entrada nos cards ao entrarem na viewport
 */

/* ─────────────────────────────────────────
   1. REDIRECT SE JÁ LOGADO
   Se houver token + usuário válidos no localStorage,
   não há motivo para ficar na landing — manda direto
   para o dashboard correto (US02/US03).
   ─────────────────────────────────────── */

(function redirecionarSeJaLogado() {
  const TOKEN_KEY   = 'avaliaedu_token';
  const USUARIO_KEY = 'avaliaedu_usuario';

  const token = localStorage.getItem(TOKEN_KEY);
  const raw   = localStorage.getItem(USUARIO_KEY);

  if (!token || !raw) return;

  try {
    const usuario = JSON.parse(raw);
    if (usuario && usuario.perfil) {
      const destino = usuario.perfil === 'ADMIN'
        ? 'dashboard-admin.html'
        : 'dashboard-aluno.html';
      window.location.href = destino;
    }
  } catch {
    // JSON corrompido — limpa e permanece na landing
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USUARIO_KEY);
  }
})();

/* ─────────────────────────────────────────
   2. SCROLL SUAVE
   Intercepta cliques em âncoras internas (#inicio,
   #recursos) e no botão "Saiba Mais", executando
   um scroll animado em vez do salto nativo.
   ─────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {

  // Botão "Saiba Mais" → rola até a seção de recursos
  const btnSaibaMais = document.getElementById('btn-saiba-mais');
  if (btnSaibaMais) {
    btnSaibaMais.addEventListener('click', () => {
      const alvo = document.getElementById('recursos');
      if (alvo) alvo.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  // Links de nav com href="#..."  → scroll suave
  document.querySelectorAll('nav a[href^="#"]').forEach(link => {
    link.addEventListener('click', (e) => {
      const alvoId = link.getAttribute('href').slice(1);
      const alvo   = document.getElementById(alvoId);
      if (alvo) {
        e.preventDefault();
        alvo.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  /* ───────────────────────────────────────
     3. SOMBRA NO HEADER AO ROLAR
     Adiciona classe .scrolled ao <header>
     quando a página é rolada para baixo,
     aplicando box-shadow via CSS.
     ─────────────────────────────────────── */

  const header = document.getElementById('header');

  function atualizarHeader() {
    if (!header) return;
    if (window.scrollY > 10) {
      header.classList.add('scrolled');
    } else {
      header.classList.remove('scrolled');
    }
  }

  window.addEventListener('scroll', atualizarHeader, { passive: true });
  atualizarHeader(); // estado inicial

  /* ───────────────────────────────────────
     4. ANIMAÇÃO DE ENTRADA NOS CARDS
     Usa IntersectionObserver para adicionar
     a classe .visivel nos cards quando eles
     entram na viewport, disparando a transição
     CSS definida em landing-page.css.
     ─────────────────────────────────────── */

  const cards = document.querySelectorAll('.cards .card');

  if ('IntersectionObserver' in window && cards.length) {

    // Começa invisível + deslocado para baixo
    cards.forEach(card => {
      card.style.opacity   = '0';
      card.style.transform = 'translateY(30px)';
      card.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
    });

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const card = entry.target;
          // Delay escalonado: 1º card sem delay, 2º +120ms, 3º +240ms
          const indice = Array.from(cards).indexOf(card);
          setTimeout(() => {
            card.style.opacity   = '1';
            card.style.transform = 'translateY(0)';
          }, indice * 120);
          observer.unobserve(card);
        }
      });
    }, { threshold: 0.15 });

    cards.forEach(card => observer.observe(card));
  }

  /* ───────────────────────────────────────
     5. VALIDAR CERTIFICADO (US22)
     Consulta pública por código de validação.
     Endpoint: GET /certificacoes/validar/{codigo}
     Página pública — sem login, por isso usa fetch()
     direto em vez de apiFetch() (que pertence a
     global.js, carregado só nos dashboards).
     ─────────────────────────────────────── */

  const API_BASE_VALIDACAO = (['localhost', '127.0.0.1'].includes(location.hostname)) ? 'http://localhost:8000' : 'https://avaliaedu-api.onrender.com';

  function _escHtmlValidacao(str) {
    const div = document.createElement('div');
    div.textContent = str ?? '';
    return div.innerHTML;
  }

  function _formatarDataValidacao(isoString) {
    if (!isoString) return '—';
    const data = new Date(isoString);
    if (Number.isNaN(data.getTime())) return '—';
    return data.toLocaleDateString('pt-BR', {
      day: '2-digit', month: '2-digit', year: 'numeric',
    });
  }

  const formValidar = document.getElementById('form-validar-certificado');

  if (formValidar) {
    const inputCodigo  = document.getElementById('input-codigo-certificado');
    const btnValidar   = document.getElementById('btn-validar-certificado');
    const resultadoBox = document.getElementById('resultado-validacao');

    formValidar.addEventListener('submit', async (e) => {
      e.preventDefault();

      const codigo = inputCodigo.value.trim();
      if (!codigo) return;

      btnValidar.disabled = true;
      btnValidar.textContent = 'Validando...';
      resultadoBox.hidden = true;

      try {
        const resp = await fetch(
          `${API_BASE_VALIDACAO}/certificacoes/validar/${encodeURIComponent(codigo)}`
        );

        if (resp.status === 429) {
          throw new Error('Muitas tentativas. Aguarde um minuto e tente novamente.');
        }

        const data = await resp.json();

        if (!resp.ok) {
          throw new Error(data?.detail || 'Não foi possível validar o certificado agora.');
        }

        if (data.valido && data.certificado) {
          const c = data.certificado;
          resultadoBox.className = 'resultado-validacao valido';
          resultadoBox.innerHTML = `
            <div class="resultado-status">
              <span class="resultado-icone">✓</span>
              Certificado válido
            </div>
            <dl class="resultado-detalhes">
              <dt>Aluno</dt><dd>${_escHtmlValidacao(c.aluno_nome)}</dd>
              <dt>Prova</dt><dd>${_escHtmlValidacao(c.prova_titulo)}</dd>
              <dt>Emitido em</dt><dd>${_formatarDataValidacao(c.data_emissao)}</dd>
              <dt>Código</dt><dd>${_escHtmlValidacao(c.codigo)}</dd>
            </dl>`;
        } else {
          resultadoBox.className = 'resultado-validacao invalido';
          resultadoBox.innerHTML = `
            <div class="resultado-status">
              <span class="resultado-icone">✕</span>
              Certificado não encontrado
            </div>
            <p class="resultado-mensagem">${_escHtmlValidacao(data.detalhe) || 'Verifique o código informado e tente novamente.'}</p>`;
        }

      } catch (err) {
        resultadoBox.className = 'resultado-validacao erro';
        resultadoBox.innerHTML = `
          <div class="resultado-status">
            <span class="resultado-icone">!</span>
            Não foi possível validar agora
          </div>
          <p class="resultado-mensagem">${_escHtmlValidacao(err.message)}</p>`;
      } finally {
        resultadoBox.hidden = false;
        btnValidar.disabled = false;
        btnValidar.textContent = 'Validar';
      }
    });
  }

});