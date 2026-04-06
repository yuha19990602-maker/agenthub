/** Resource sidebar component with collapsible groups */

import { useState } from 'react';
import {
  MessageSquare,
  Bot,
  BookOpen,
  Zap,
  Code,
  PenTool,
  BarChart3,
  FileText,
  Database,
  Layers,
  Cpu,
  Globe,
  ChevronDown,
  ChevronRight,
  Sparkles,
} from 'lucide-react';
import type { Resource } from '../types';

interface ResourceSidebarProps {
  resourcesGrouped: Record<string, Resource[]>;
  currentResourceId?: string;
  onSelectResource: (resource: Resource) => void;
}

// Group configuration with icons and colors
const groupConfig: Record<string, { icon: React.ReactNode; color: string; bgColor: string }> = {
  '基础对话': {
    icon: <MessageSquare className="w-5 h-5" />,
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
  },
  '技能助手': {
    icon: <Bot className="w-5 h-5" />,
    color: 'text-purple-600',
    bgColor: 'bg-purple-50',
  },
  '知识库': {
    icon: <BookOpen className="w-5 h-5" />,
    color: 'text-green-600',
    bgColor: 'bg-green-50',
  },
  '智能应用': {
    icon: <Zap className="w-5 h-5" />,
    color: 'text-orange-600',
    bgColor: 'bg-orange-50',
  },
  '集成应用': {
    icon: <Globe className="w-5 h-5" />,
    color: 'text-indigo-600',
    bgColor: 'bg-indigo-50',
  },
};

// Resource icon mapping based on resource id or type
const getResourceIcon = (resource: Resource): React.ReactNode => {
  const iconClass = "w-5 h-5";
  
  // Map specific resources to unique icons
  switch (resource.id) {
    case 'general-chat':
      return <Sparkles className={iconClass} />;
    case 'skill-coding':
      return <Code className={iconClass} />;
    case 'skill-writing':
      return <PenTool className={iconClass} />;
    case 'skill-data-analysis':
      return <BarChart3 className={iconClass} />;
    case 'kb-policy':
      return <FileText className={iconClass} />;
    case 'kb-tech':
      return <Database className={iconClass} />;
    case 'agent-report':
      return <Layers className={iconClass} />;
    case 'op-agent':
      return <Cpu className={iconClass} />;
    default:
      // Fallback based on type
      if (resource.type === 'direct_chat') return <MessageSquare className={iconClass} />;
      if (resource.type === 'skill_chat') return <Bot className={iconClass} />;
      if (resource.type === 'kb_websdk') return <BookOpen className={iconClass} />;
      if (resource.type === 'agent_websdk') return <Zap className={iconClass} />;
      if (resource.type === 'openai_compatible_v1') return <Cpu className={iconClass} />;
      return <Sparkles className={iconClass} />;
  }
};

// Get icon background color based on resource
const getResourceIconBg = (resource: Resource): string => {
  switch (resource.id) {
    case 'general-chat':
      return 'bg-gradient-to-br from-blue-400 to-blue-600';
    case 'skill-coding':
      return 'bg-gradient-to-br from-cyan-400 to-cyan-600';
    case 'skill-writing':
      return 'bg-gradient-to-br from-pink-400 to-pink-600';
    case 'skill-data-analysis':
      return 'bg-gradient-to-br from-emerald-400 to-emerald-600';
    case 'kb-policy':
      return 'bg-gradient-to-br from-amber-400 to-amber-600';
    case 'kb-tech':
      return 'bg-gradient-to-br from-teal-400 to-teal-600';
    case 'agent-report':
      return 'bg-gradient-to-br from-violet-400 to-violet-600';
    case 'op-agent':
      return 'bg-gradient-to-br from-indigo-400 to-indigo-600';
    default:
      if (resource.type === 'openai_compatible_v1') {
        return 'bg-gradient-to-br from-slate-500 to-slate-700';
      }
      return 'bg-gradient-to-br from-gray-400 to-gray-600';
  }
};

export function ResourceSidebar({
  resourcesGrouped,
  currentResourceId,
  onSelectResource,
}: ResourceSidebarProps) {
  // Initialize all groups as expanded
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {};
    Object.keys(resourcesGrouped).forEach((group) => {
      initial[group] = true;
    });
    return initial;
  });

  const toggleGroup = (group: string) => {
    setExpandedGroups((prev) => ({
      ...prev,
      [group]: !prev[group],
    }));
  };

  // Sort groups in specific order
  const groupOrder = ['基础对话', '技能助手', '知识库', '智能应用', '集成应用'];
  const sortedGroups = Object.entries(resourcesGrouped).sort(([a], [b]) => {
    const indexA = groupOrder.indexOf(a);
    const indexB = groupOrder.indexOf(b);
    if (indexA === -1 && indexB === -1) return a.localeCompare(b);
    if (indexA === -1) return 1;
    if (indexB === -1) return -1;
    return indexA - indexB;
  });

  return (
    <div className="w-72 bg-white border-r flex flex-col h-full shadow-sm">
      {/* Header */}
      <div className="p-4 border-b bg-gradient-to-r from-primary-50 to-white">
        <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-primary-500" />
          AI 资源中心
        </h2>
        <p className="text-xs text-gray-500 mt-1">选择资源开始对话</p>
      </div>

      {/* Resource Groups */}
      <div className="flex-1 overflow-y-auto py-2">
        {sortedGroups.map(([group, resources]) => {
          const config = groupConfig[group] || {
            icon: <Layers className="w-5 h-5" />,
            color: 'text-gray-600',
            bgColor: 'bg-gray-50',
          };
          const isExpanded = expandedGroups[group] ?? true;

          return (
            <div key={group} className="mb-1">
              {/* Group Header */}
              <button
                onClick={() => toggleGroup(group)}
                className={`w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors ${config.bgColor}`}
              >
                <div className={`flex items-center gap-2 font-semibold ${config.color}`}>
                  {config.icon}
                  <span className="text-sm">{group}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400 bg-white px-2 py-0.5 rounded-full">
                    {resources.length}
                  </span>
                  {isExpanded ? (
                    <ChevronDown className="w-4 h-4 text-gray-400" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-gray-400" />
                  )}
                </div>
              </button>

              {/* Resource List */}
              {isExpanded && (
                <div className="py-1">
                  {resources.map((resource) => {
                    const isSelected = currentResourceId === resource.id;
                    return (
                      <button
                        key={resource.id}
                        onClick={() => onSelectResource(resource)}
                        className={`w-full px-4 py-3 flex items-start gap-3 transition-all duration-200 ${
                          isSelected
                            ? 'bg-primary-50 border-l-4 border-primary-500'
                            : 'hover:bg-gray-50 border-l-4 border-transparent'
                        }`}
                      >
                        {/* Icon */}
                        <div
                          className={`w-10 h-10 rounded-xl flex items-center justify-center text-white flex-shrink-0 shadow-sm ${getResourceIconBg(
                            resource
                          )}`}
                        >
                          {getResourceIcon(resource)}
                        </div>

                        {/* Info */}
                        <div className="flex-1 text-left min-w-0">
                          <h3
                            className={`font-semibold text-sm truncate ${
                              isSelected ? 'text-primary-700' : 'text-gray-900'
                            }`}
                          >
                            {resource.name}
                          </h3>
                          <p className="text-xs text-gray-500 mt-0.5 line-clamp-2 leading-relaxed">
                            {resource.description}
                          </p>
                          
                          {/* Tags */}
                          <div className="flex flex-wrap gap-1 mt-1.5">
                            {resource.tags.slice(0, 2).map((tag) => (
                              <span
                                key={tag}
                                className="text-[10px] px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded"
                              >
                                {tag}
                              </span>
                            ))}
                          </div>
                        </div>

                        {/* Active indicator */}
                        {isSelected && (
                          <div className="w-2 h-2 rounded-full bg-primary-500 mt-2 flex-shrink-0" />
                        )}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer */}
      <div className="p-3 border-t bg-gray-50">
        <div className="text-xs text-gray-400 text-center">
          共 {Object.values(resourcesGrouped).flat().length} 个资源
        </div>
      </div>
    </div>
  );
}
