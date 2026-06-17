import { auth as apiAuth } from './api.js';

export const auth = {
  login: apiAuth.login,
  register: apiAuth.register,
};

