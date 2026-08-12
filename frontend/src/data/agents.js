/** Agent definitions for the SeedheOps DevOps Swarm orchestration flow */
export const SWARM_AGENTS = [
  {
    id: 'orchestrator',
    name: 'Triage Agent',
    workingStatus: 'Parsing telemetry & error logs...',
    doneStatus: 'Alert triaged. Root failure identified.',
    trace:
      'Telemetry ingested: Redis cluster memory ceiling reached (98.4%). Worker pod evictions detected in namespace prod-us-east-1. Routing to Hindsight Memory Agent for historical root-cause analysis.',
  },
  {
    id: 'personalization',
    name: 'Hindsight Memory Agent',
    workingStatus: 'Querying Hindsight for historical incidents...',
    doneStatus: 'Historical context retrieved. Previous fix identified.',
    trace:
      'Queried Hindsight Vector Database (endpoint: hindsight.vectorize.io). Vector search match: Incident #INC-8821 (Retrieved from 60 days ago) with Cosine Similarity score: 0.942. Recalled runbook payload feeds directly into Runbook Executor commands: kubectl drain, redis-cli volatile key eviction, and aws-cli ElastiCache cluster sync.',
  },
  {
    id: 'task-executor',
    name: 'Runbook Executor',
    workingStatus: 'Sequencing remediation steps...',
    doneStatus: 'Immediate hotfix runbook generated.',
    trace:
      'Executing runbook sequenced from #INC-8821: (1) kubectl drain failing pods, (2) redis-cli cache purge & maxmemory adjust, (3) aws-cli replica sync, (4) kubectl rollout restart deployment.',
  },
  {
    id: 'recommendation',
    name: 'Risk Mitigator',
    workingStatus: 'Analyzing post-mortem risk...',
    doneStatus: 'Long-term preventative measure logged.',
    trace:
      'Post-incident safeguard configured: adjust Redis maxmemory-policy to volatile-lru, increase memory request limits by 2Gi in Helm values, and configure PagerDuty threshold at 80% saturation.',
  },
  {
    id: 'voice-narrator',
    name: 'Audio Sitrep Agent',
    workingStatus: 'Generating audio briefing...',
    doneStatus: 'Sitrep ready for on-call engineer.',
    trace:
      'Synthesized audio sitrep for on-call SRE. Summary covers root cause, hotfix runbook execution, and long-term mitigation policies. Audio stream ready.',
  },
]

export const DEFAULT_SWARM_INPUT =
  'Production Alert: Payment-API Redis pod OOMKilled in cluster prod-us-east-1. Database connection pool exhaustion detected.'

export const DAY_PLAN_TASKS = [
  {
    time: '+00:00',
    title: 'Drain & isolate failing worker pod',
    description: 'kubectl drain pod-worker-3 --ignore-daemonsets --delete-emptydir-data -n prod',
    status: 'done',
  },
  {
    time: '+00:02',
    title: 'Evict expired volatile cache keys (#INC-8821 pattern)',
    description: 'redis-cli -h cache.internal --scan --pattern "session:temp:*" | xargs redis-cli -h cache.internal unlink',
    status: 'done',
  },
  {
    time: '+00:05',
    title: 'Scale Redis cluster statefulset replicas',
    description: 'kubectl scale statefulset/redis-cluster -n prod --replicas=4',
    status: 'done',
  },
  {
    time: '+00:08',
    title: 'Sync AWS ElastiCache replica configuration',
    description: 'aws elasticache modify-replication-group --replication-group-id prod-redis-cluster --apply-immediately',
    status: 'done',
  },
  {
    time: '+00:12',
    title: 'Verify cluster telemetry & pod health',
    description: 'kubectl get pods -n prod -l app=api-worker -w',
    status: 'done',
  },
]

export const VOICE_NARRATION =
  'On-call sitrep: Redis cluster memory exhaustion detected in production. Hindsight retrieved resolution pattern from Incident #INC-8821 (Cosine similarity 0.942). Hotfix runbook sequenced: draining failing pods, purging volatile cache keys, and scaling replicas to 4. Telemetry stabilization underway.'

