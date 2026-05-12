import { Brain, FileText, PenTool, Eye, Scale, Download, Settings, ChevronRight } from 'lucide-react';
import { useAgentStore } from '@/stores/agentStore';

const agentConfig = {
  knowledge: { icon: Brain, name: 'Knowledge', description: '知识检索' },
  summary: { icon: FileText, name: 'Summary', description: '需求摘要' },
  writer: { icon: PenTool, name: 'Writer', description: '内容生成' },
  review: { icon: Eye, name: 'Review', description: '质量评审' },
  judge: { icon: Scale, name: 'Judge', description: '复杂度判断' },
  result: { icon: Download, name: 'Result', description: '成果导出' },
};

export default function SidePanel() {
  const { agents, selectedAgent, setSelectedAgent } = useAgentStore();

  return (
    <aside className="w-72 bg-dark-800 border-r border-dark-700 flex flex-col">
      <div className="p-4 border-b border-dark-700">
        <h2 className="text-sm font-semibold text-dark-300 uppercase tracking-wider">Agent 舰队</h2>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {Object.entries(agents).map(([agentId, agent]) => {
          const config = agentConfig[agentId as keyof typeof agentConfig];
          const Icon = config?.icon || Brain;
          const isSelected = selectedAgent === agentId;
          const isActive = agent.status === 'processing';

          return (
            <button
              key={agentId}
              onClick={() => setSelectedAgent(agentId)}
              className={`w-full p-3 rounded-lg text-left transition-all duration-200 ${
                isSelected
                  ? 'bg-blue-500/20 border border-blue-500/30'
                  : 'bg-dark-700/50 border border-transparent hover:bg-dark-700 hover:border-dark-600'
              }`}
            >
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                  isActive ? 'bg-blue-500 animate-pulse' : 'bg-dark-600'
                }`}>
                  <Icon className="w-5 h-5 text-white" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-white text-sm truncate">{config?.name}</span>
                    {isActive && (
                      <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                    )}
                  </div>
                  <span className="text-xs text-dark-400 truncate">{config?.description}</span>
                </div>
                <ChevronRight className={`w-4 h-4 transition-transform ${
                  isSelected ? 'text-blue-400 translate-x-1' : 'text-dark-500'
                }`} />
              </div>

              {agent.current_task && (
                <div className="mt-2 pt-2 border-t border-dark-600">
                  <p className="text-xs text-dark-400 truncate">
                    当前任务: {agent.current_task}
                  </p>
                </div>
              )}
            </button>
          );
        })}
      </div>

      <div className="p-3 border-t border-dark-700">
        <button className="w-full p-3 rounded-lg bg-dark-700/50 hover:bg-dark-700 border border-transparent hover:border-dark-600 transition-all flex items-center gap-3">
          <Settings className="w-5 h-5 text-dark-400" />
          <span className="text-sm text-dark-300">系统设置</span>
        </button>
      </div>
    </aside>
  );
}