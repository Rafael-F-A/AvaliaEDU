import { certificacoes as apiCert } from './api.js';

export const certificacoes = {
  solicitar: apiCert.solicitar,
  iniciar: apiCert.iniciar,
  responder: apiCert.responder,
  gerarCertificado: apiCert.gerarCertificado,
};

