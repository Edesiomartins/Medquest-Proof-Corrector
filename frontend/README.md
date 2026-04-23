This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to optimize font loading (por exemplo, Geist).

## Learn More

- [Next.js Documentation](https://nextjs.org/docs)
- [Learn Next.js](https://nextjs.org/learn)

## Deploy (Railway)

O frontend deste monorepo pode ser um serviço Railway com **Root Directory** `frontend` e comando de build/start conforme o `package.json`. Veja **`../backend/RAILWAY_SETUP.md`** (na raiz do monorepo: `backend/RAILWAY_SETUP.md`) para Postgres, Redis, API e worker.
