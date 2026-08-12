import { motion } from 'framer-motion'
import { Bot, ChevronRight, Activity } from 'lucide-react'

const activityList = [
  { name: 'Triage Agent', task: 'Parsing telemetry & error logs...', color: '#0EA5E9' },
  { name: 'Hindsight Memory Agent', task: 'Querying historical incidents...', color: '#0EA5E9' },
  { name: 'Runbook Executor', task: 'Sequencing remediation steps...', color: '#0EA5E9' },
  { name: 'Risk Mitigator', task: 'Analyzing post-mortem risk...', color: '#0EA5E9' },
  { name: 'Audio Sitrep Agent', task: 'Generating audio briefing...', color: '#0EA5E9' },
]

export default function LiveAgentWidget({ onOpenSwarm }) {
  return (
    <div className="glass-panel p-5 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bot size={18} className="text-[#0EA5E9]" />
          <h3 className="font-display font-semibold text-sm text-[#F1F5F9]">DevOps Swarm</h3>
        </div>
        {onOpenSwarm && (
          <button
            type="button"
            onClick={onOpenSwarm}
            className="text-xs font-semibold text-[#0EA5E9] hover:text-[#38BDF8] flex items-center gap-1 cursor-pointer"
          >
            <span>View All</span>
            <ChevronRight size={14} />
          </button>
        )}
      </div>

      <div className="flex flex-col gap-2">
        {activityList.map((item, index) => (
          <motion.div
            key={item.name}
            className="flex items-center gap-3 py-2 border-t border-[var(--line)] first:border-t-0"
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.05 }}
          >
            <div className="relative flex items-center justify-center flex-shrink-0">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: item.color }} />
              <span
                className="absolute w-4 h-4 rounded-full border opacity-30 animate-ping"
                style={{ borderColor: item.color }}
              />
            </div>
            
            <div className="flex flex-col">
              <strong className="text-xs font-semibold text-[#F1F5F9]">{item.name}</strong>
              <span className="text-[10px] text-[#64748B] mt-0.5">{item.task}</span>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}
