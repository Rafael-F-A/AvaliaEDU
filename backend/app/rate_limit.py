from slowapi import Limiter
from slowapi.util import get_remote_address

# Limiter ÚNICO compartilhado entre main.py (app.state.limiter) e os routers
# que aplicam limites específicos (ex.: /auth/login com @limiter.limit).
# Precisa ser a MESMA instância — duas instâncias diferentes fazem o slowapi
# não enforçar o limite por rota (a checagem usa app.state.limiter).
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
