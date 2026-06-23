/* ============================================================
   orientacao.js — guia de uso (público)
   - Revela o "Guia do administrador" SOMENTE quando há sessão ADMIN.
   - Ajusta o link de acesso do topo conforme a sessão.
   - Self-contained: lê o localStorage direto (mesmas chaves do app),
     sem depender de global.js nem forçar autenticação.
   ============================================================ */

(function () {
  'use strict';

  var TOKEN_KEY = 'avaliaedu_token';
  var USUARIO_KEY = 'avaliaedu_usuario';

  function getUsuario() {
    try {
      return JSON.parse(localStorage.getItem(USUARIO_KEY) || 'null');
    } catch (e) {
      return null;
    }
  }

  function temSessao() {
    return !!localStorage.getItem(TOKEN_KEY);
  }

  function mostrar(el) { if (el) el.classList.remove('hidden'); }

  document.addEventListener('DOMContentLoaded', function () {
    var usuario = getUsuario();
    var logado = temSessao() && usuario;
    var isAdmin = logado && usuario.perfil === 'ADMIN';

    // 1) Revela o guia do administrador apenas para ADMIN logado.
    if (isAdmin) {
      mostrar(document.getElementById('admin'));
      mostrar(document.getElementById('nav-admin'));
      mostrar(document.getElementById('indice-admin'));
    }

    // 2) Ajusta o link de acesso do topo conforme a sessão.
    var navAcesso = document.getElementById('nav-acesso');
    if (navAcesso && logado) {
      if (isAdmin) {
        navAcesso.textContent = 'Painel';
        navAcesso.href = 'dashboard-admin.html';
      } else {
        navAcesso.textContent = 'Minha Área';
        navAcesso.href = 'dashboard-aluno.html';
      }
    }

    // 3) Sombra no header ao rolar (mesmo efeito da landing).
    var header = document.getElementById('header');
    if (header) {
      window.addEventListener('scroll', function () {
        header.classList.toggle('scrolled', window.scrollY > 10);
      }, { passive: true });
    }
  });
})();
