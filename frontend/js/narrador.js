/* ============================================================
   AvaliaEdu — narrador.js
   Leitura em voz alta (Web Speech API) para a tela de prova.
   Acessibilidade — ler enunciado e alternativas em pt-BR.
   Usado por: dashboard-aluno.html (chamado pelo aluno.js).

   Interface pública (objeto global `Narrador`):
     Narrador.suportado()            -> bool
     Narrador.falar(textos)          -> enfileira e lê (string ou array de strings)
     Narrador.pausar() / continuar() / parar()
     Narrador.setVelocidade(rate)    -> 0.7 | 1.0 | 1.3 (persistido)
     Narrador.getVelocidade()        -> rate atual
     Narrador.onEstado(cb)           -> cb('parado' | 'falando' | 'pausado')
   ============================================================ */

// `var` (não `const`) para virar propriedade de window — necessário p/ onclick inline.
var Narrador = (function () {
  const RATE_KEY = 'avaliaedu_narrador_rate';
  const synth = (typeof window !== 'undefined') ? window.speechSynthesis : null;

  let vozPt      = null;
  let estado     = 'parado';   // 'parado' | 'falando' | 'pausado'
  let onEstadoCb = null;
  let restantes  = 0;          // utterances ainda na fila
  let rate       = parseFloat(localStorage.getItem(RATE_KEY)) || 1.0;

  function suportado() {
    return !!synth && typeof window.SpeechSynthesisUtterance === 'function';
  }

  function _carregarVoz() {
    if (!suportado()) return;
    const vozes = synth.getVoices() || [];
    vozPt = vozes.find(v => /pt[-_]BR/i.test(v.lang))
         || vozes.find(v => /^pt/i.test(v.lang))
         || null;
  }

  function _setEstado(novo) {
    if (estado === novo) return;
    estado = novo;
    if (typeof onEstadoCb === 'function') onEstadoCb(novo);
  }

  /** Quebra um texto em trechos curtos (evita o corte ~15s do Chrome). */
  function _dividir(texto) {
    const limpo = String(texto || '').replace(/\s+/g, ' ').trim();
    if (!limpo) return [];
    if (limpo.length <= 200) return [limpo];
    const frases = limpo.match(/[^.!?;]+[.!?;]*/g) || [limpo];
    const out = [];
    let buf = '';
    for (const f of frases) {
      if (buf && (buf + ' ' + f).trim().length > 200) { out.push(buf.trim()); buf = f; }
      else { buf = (buf + ' ' + f).trim(); }
    }
    if (buf) out.push(buf.trim());
    return out;
  }

  function onEstado(cb) { onEstadoCb = cb; }

  function getVelocidade() { return rate; }

  function setVelocidade(r) {
    rate = Number(r) || 1.0;
    try { localStorage.setItem(RATE_KEY, String(rate)); } catch (e) { /* ignora */ }
  }

  function parar() {
    if (!suportado()) return;
    restantes = 0;
    synth.cancel();
    _setEstado('parado');
  }

  function pausar() {
    if (!suportado()) return;
    if (estado === 'falando') { synth.pause(); _setEstado('pausado'); }
  }

  function continuar() {
    if (!suportado()) return;
    if (estado === 'pausado') { synth.resume(); _setEstado('falando'); }
  }

  function falar(textos) {
    if (!suportado()) return;
    parar();                       // cancela qualquer leitura anterior
    if (!vozPt) _carregarVoz();

    let chunks = [];
    (Array.isArray(textos) ? textos : [textos]).forEach(t => {
      chunks = chunks.concat(_dividir(t));
    });
    chunks = chunks.filter(c => c && c.trim());
    if (!chunks.length) return;

    restantes = chunks.length;
    _setEstado('falando');

    const _fim = () => {
      restantes--;
      if (restantes <= 0 && estado !== 'pausado') _setEstado('parado');
    };

    // pequeno atraso: no Chrome, speak() logo após cancel() às vezes não dispara
    setTimeout(() => {
      chunks.forEach(texto => {
        const u = new SpeechSynthesisUtterance(texto);
        u.lang = 'pt-BR';
        if (vozPt) u.voice = vozPt;
        u.rate = rate;
        u.onend = _fim;
        u.onerror = _fim;
        synth.speak(u);
      });
    }, 60);
  }

  // Vozes podem carregar de forma assíncrona.
  if (suportado()) {
    _carregarVoz();
    if (typeof synth.onvoiceschanged !== 'undefined') {
      synth.onvoiceschanged = _carregarVoz;
    }
  }

  return { suportado, falar, pausar, continuar, parar, setVelocidade, getVelocidade, onEstado };
})();
