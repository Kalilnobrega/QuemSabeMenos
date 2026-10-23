# Quem Sabe Menos?

Party game de quiz no navegador: alguém cria a sala, manda o código ou link e a galera descobre quem é o menos burro.

## Rodando localmente

**Backend** (Python 3.12, FastAPI + python-socketio), na porta 8001:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload --port 8001
.venv/bin/pytest            # testes
```

**Frontend** (React + Vite + TypeScript + Tailwind), na porta 5173:

```bash
cd frontend
npm install
npm run dev
```

## Tipos compartilhados

Os eventos do Socket.IO são definidos como modelos Pydantic em `backend/app/events.py`.
Depois de alterá-los, rode `npm run types` no frontend para gerar `src/types/events.ts`.

## Deploy

**Backend no Railway** (serviço apontando para este repositório):

- Root Directory: `/backend`
- Config file path: `/backend/railway.json` (o arquivo de config não segue o Root Directory)
- Variável `CORS_ORIGINS`: o domínio do front na Vercel, ex. `https://quem-sabe-menos.vercel.app`
  (vários domínios separados por vírgula)
- Mantenha **uma única réplica**: salas e partidas ficam na memória do processo.
  Cada deploy reinicia o servidor e encerra as partidas em andamento.

**Frontend na Vercel**:

- Root Directory: `frontend` (framework Vite detectado automaticamente)
- O endereço do backend fica em `frontend/.env.production` (`VITE_SERVER_URL`).
  Ele entra no build: ao trocar de servidor, edite o arquivo e faça push.
