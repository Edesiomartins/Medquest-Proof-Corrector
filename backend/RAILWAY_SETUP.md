# Como dar Deploy no Railway (Monorepo)

O Railway não vai saber qual pasta compilar automaticamente se você não instruir ele (já que nosso repositório tem as pastas `/backend` e `/frontend`).

Para ter o Backend 100% no ar, você precisa rodar os dois motores: a Web API (FastAPI) e os Workers em Background (Celery).

## 1. Variáveis de Ambiente Necessárias
No painel do Railway, vá na aba **Variables** de cada serviço e cole tudo que está no arquivo `.env.example`:
- `DATABASE_URL` (O Railway te dá isso se você adicionar um Database de Postgres)
- `REDIS_URL` (O Railway te dá isso se você adicionar um serviço de Redis)
- Suas chaves de API (`OPENROUTER_API_KEY`, etc)

## 2. Serviço da Web API (FastAPI)
- Crie um novo serviço pelo GitHub.
- Em **Settings > Build > Root Directory**, digite: `/backend`
- O Railway vai identificar o `requirements.txt` e instalar tudo.
- Em **Settings > Deploy > Start Command**, cole isso:
  ```bash
  uvicorn main:app --host 0.0.0.0 --port $PORT
  ```

## 3. Serviço do Worker (Celery)
- Crie *outro* serviço puxando o mesmo repositório do GitHub.
- Em **Settings > Build > Root Directory**, digite: `/backend`
- Em **Settings > Deploy > Start Command**, cole isso:
  ```bash
  celery -A app.core.celery_app worker --loglevel=info
  ```

Pronto! Com esses 2 serviços (mais os bancos de dados) seu SaaS está em nuvem.
