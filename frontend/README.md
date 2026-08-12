# SeedheOps

**Autonomous 5-Agent DevOps Incident Response Swarm** — a production-ready React + Vite dashboard replicating an autonomous SRE incident response center.

## Swarm Agent Identities

1. **Triage Agent** (`orchestrator`): Ingests infrastructure telemetry, crash logs, and error codes; identifies root failure domain and blast radius.
2. **Hindsight Memory Agent** (`personalization`): Queries Hindsight vector memory store for past incident post-mortems (e.g. #INC-8821) and retrieves historical fix patterns.
3. **Runbook Executor** (`task-executor`): Sequences executable terminal commands (`kubectl`, `redis-cli`, `psql`, `aws`) with relative execution offsets.
4. **Risk Mitigator** (`recommendation`): Formulates long-term post-mortem safeguards and preventative architectural policies.
5. **Audio Sitrep Agent** (`voice-narrator`): Synthesizes an authoritative, concise situation report for the on-call engineer.

## Stack

- React 19 + Vite 8
- Framer Motion
- Recharts
- Lucide React
- Tailwind CSS 4

## Getting Started

```bash
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

## License

SeedheOps © 2026
