# Como dar Deploy no Railway (Monorepo)

O Railway não vai saber qual pasta compilar automaticamente se você não instruir ele (já que nosso repositório tem as pastas `/backend` e `/frontend`).

Para ter o Backend 100% no ar, você precisa rodar os dois motores: a Web API (FastAPI) e os Workers em Background (Celery).

## 1. Variáveis de Ambiente Necessárias
No painel do Railway, abra **Variables** no serviço da **API** e no **Worker** (mesmas variáveis nos dois).

Use o arquivo **`backend/railway.env.template`** como lista completa: copie, substitua os placeholders e cole no Raw Editor.

Resumo do que você precisa preencher ou referenciar:

| Variável | Origem |
|----------|--------|
| `DATABASE_URL` | Referência ao plugin **Postgres** do projeto (ou URL manual). |
| `REDIS_URL` | Referência ao plugin **Redis** (ou URL manual). |
| `CORS_ORIGINS` | URL pública do **frontend** no Railway (serviço Next.js), com `https://`, separada por vírgula se houver mais de uma. |
| `OPENROUTER_API_KEY` | Chave da OpenRouter (quando for usar correção por LLM). |
| `AZURE_DOCUMENT_INTELLIGENCE_*` | Opcional até ativar OCR na Azure. |
| `UPLOAD_DIR`, `MAX_*` | Já têm valores seguros no template; ajuste se quiser. |
| `JWT_SECRET_KEY` | **Obrigatório.** Segredo para assinar tokens (ex.: `python -c "import secrets; print(secrets.token_hex(32))"`). |
| `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` | Opcionais; o template já define HS256 e 7 dias. |

Chaves vazias (`OPENROUTER`, Azure) não quebram o deploy; só desativam essas integrações até você preencher.

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

Pronto! Com esses 2 serviços (mais os bancos de dados) a API e o pipeline ficam no ar.

## 4. Serviço do Frontend (Next.js) no Railway

- Novo serviço a partir do mesmo repositório.
- **Root Directory:** `/frontend`
- Defina **`NEXT_PUBLIC_API_URL`** com a URL da API (ex.: `https://medquest-proof-corrector-api.up.railway.app/api/v1`).
- No backend, **`CORS_ORIGINS`** deve ser exatamente a URL pública deste frontend (ex.: `https://seu-app-web.up.railway.app`).
- **Start Command** típico após build: `npm run start` (ou use o preset Node do Railway apontando para `frontend`).
