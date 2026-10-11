# FinMind AI — web (React + TypeScript + Tailwind + Framer Motion)

    cd web
    npm install
    npm run dev          # http://localhost:5173  (proxies /api -> http://127.0.0.1:8000)
    npm test             # 39 unit/component tests
    npm run build        # type-checks, then builds to dist/

The API must be running (`uvicorn backend.main:app --reload`) plus Postgres and Redis.
Shortcuts: `N` new transaction · `A` AI advisor.
