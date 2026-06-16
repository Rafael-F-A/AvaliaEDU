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

});