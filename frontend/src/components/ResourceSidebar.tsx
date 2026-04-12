/** Resource sidebar component with search, recommendations, recent, and favorites. */

import { useMemo, useState } from 'react';
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
  Search,
  Star,
  Clock3,
  Heart,
} from 'lucide-react';
import type { Resource, ResourceEntrypoint } from '../types';

interface ResourceSidebarProps {
  resourcesGrouped: Record<string, Resource[]>;
  recommendedResources: Resource[];
  recentResources: Resource[];
  favoriteResources: Resource[];
  currentResourceId?: string;
  onSelectResource: (resource: Resource, entrypointId?: string) => void;
  onToggleFavorite: (resource: Resource, favorited: boolean) => void;
}

const groupConfig: Record<string, { icon: React.ReactNode; color: string; bgColor: string }> = {
  '基础对话': { icon: <MessageSquare className="w-5 h-5" />, color: 'text-blue-600', bgColor: 'bg-blue-50' },
  '技能助手': { icon: <Bot className="w-5 h-5" />, color: 'text-purple-600', bgColor: 'bg-purple-50' },
  '知识库': { icon: <BookOpen className="w-5 h-5" />, color: 'text-green-600', bgColor: 'bg-green-50' },
  '智能应用': { icon: <Zap className="w-5 h-5" />, color: 'text-orange-600', bgColor: 'bg-orange-50' },
  '集成应用': { icon: <Globe className="w-5 h-5" />, color: 'text-indigo-600', bgColor: 'bg-indigo-50' },
};

const getResourceIcon = (resource: Resource): React.ReactNode => {
  const iconClass = 'w-5 h-5';
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
      if (resource.type === 'direct_chat') return <MessageSquare className={iconClass} />;
      if (resource.type === 'skill_chat') return <Bot className={iconClass} />;
      if (resource.type === 'kb_websdk') return <BookOpen className={iconClass} />;
      if (resource.type === 'agent_websdk') return <Zap className={iconClass} />;
      if (resource.type === 'openai_compatible_v1') return <Cpu className={iconClass} />;
      return <Sparkles className={iconClass} />;
  }
};

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
      if (resource.type === 'openai_compatible_v1') return 'bg-gradient-to-br from-slate-500 to-slate-700';
      return 'bg-gradient-to-br from-gray-400 to-gray-600';
  }
};

const getModeBadge = (resource: Resource, entrypoint?: ResourceEntrypoint): string => {
  const adapter = entrypoint?.adapter;
  const launchMode = entrypoint?.launch_mode || resource.launch_mode;
  if (adapter === 'skill_chat') return 'skill';
  if (launchMode === 'iframe') return 'iframe';
  if (launchMode === 'websdk') return '应用';
  return 'native';
};

const getDefaultEntrypoint = (resource: Resource): ResourceEntrypoint | undefined => {
  const enabled = (resource.entrypoints || []).filter((item) => item.enabled);
  return enabled.find((item) => item.is_default) || enabled[0];
};

function ResourceItem({
  resource,
  currentResourceId,
  isFavorite,
  onSelectResource,
  onToggleFavorite,
}: {
  resource: Resource;
  currentResourceId?: string;
  isFavorite: boolean;
  onSelectResource: (resource: Resource, entrypointId?: string) => void;
  onToggleFavorite: (resource: Resource, favorited: boolean) => void;
}) {
  const isSelected = currentResourceId === resource.id;
  const defaultEntrypoint = getDefaultEntrypoint(resource);
  const enabledEntrypoints = (resource.entrypoints || []).filter((item) => item.enabled);

  return (
    <div
      className={`px-4 py-3 transition-all duration-200 ${
        isSelected ? 'bg-primary-50 border-l-4 border-primary-500' : 'hover:bg-gray-50 border-l-4 border-transparent'
      }`}
    >
      <div className="flex items-start gap-3">
        <button className="contents" onClick={() => onSelectResource(resource, defaultEntrypoint?.entrypoint_id)}>
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-white flex-shrink-0 shadow-sm ${getResourceIconBg(resource)}`}>
            {getResourceIcon(resource)}
          </div>
          <div className="flex-1 text-left min-w-0">
            <div className="flex items-center gap-2">
              <h3 className={`font-semibold text-sm truncate ${isSelected ? 'text-primary-700' : 'text-gray-900'}`}>
                {resource.name}
              </h3>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 uppercase">
                {getModeBadge(resource, defaultEntrypoint)}
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-0.5 line-clamp-2 leading-relaxed">{resource.description}</p>
            <div className="flex flex-wrap gap-1 mt-1.5">
              {resource.tags.slice(0, 2).map((tag) => (
                <span key={tag} className="text-[10px] px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded">
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </button>
        <button
          onClick={() => onToggleFavorite(resource, isFavorite)}
          className={`mt-0.5 p-1 rounded ${isFavorite ? 'text-amber-500' : 'text-gray-300 hover:text-amber-500'}`}
          title={isFavorite ? '取消收藏' : '收藏'}
        >
          <Star className={`w-4 h-4 ${isFavorite ? 'fill-current' : ''}`} />
        </button>
      </div>
      {enabledEntrypoints.length > 1 && (
        <div className="mt-2 pl-[52px] flex flex-wrap gap-1">
          {enabledEntrypoints.map((entrypoint) => (
            <button
              key={entrypoint.entrypoint_id}
              onClick={() => onSelectResource(resource, entrypoint.entrypoint_id)}
              className={`text-[11px] px-2 py-1 rounded border ${
                defaultEntrypoint?.entrypoint_id === entrypoint.entrypoint_id
                  ? 'border-primary-200 bg-white text-primary-600'
                  : 'border-gray-200 text-gray-600 hover:bg-white'
              }`}
            >
              {entrypoint.title}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function ResourceSection({
  title,
  icon,
  resources,
  currentResourceId,
  favoriteIds,
  onSelectResource,
  onToggleFavorite,
}: {
  title: string;
  icon: React.ReactNode;
  resources: Resource[];
  currentResourceId?: string;
  favoriteIds: Set<string>;
  onSelectResource: (resource: Resource, entrypointId?: string) => void;
  onToggleFavorite: (resource: Resource, favorited: boolean) => void;
}) {
  if (!resources.length) return null;
  return (
    <div className="mb-3">
      <div className="px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide flex items-center gap-2">
        {icon}
        {title}
      </div>
      <div className="bg-white">
        {resources.map((resource) => (
          <ResourceItem
            key={`${title}-${resource.id}`}
            resource={resource}
            currentResourceId={currentResourceId}
            isFavorite={favoriteIds.has(resource.id)}
            onSelectResource={onSelectResource}
            onToggleFavorite={onToggleFavorite}
          />
        ))}
      </div>
    </div>
  );
}

export function ResourceSidebar({
  resourcesGrouped,
  recommendedResources,
  recentResources,
  favoriteResources,
  currentResourceId,
  onSelectResource,
  onToggleFavorite,
}: ResourceSidebarProps) {
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({});
  const [query, setQuery] = useState('');

  const favoriteIds = useMemo(() => new Set(favoriteResources.map((item) => item.id)), [favoriteResources]);
  const groupOrder = ['基础对话', '技能助手', '知识库', '智能应用', '集成应用'];

  const filteredGroups = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    const entries = Object.entries(resourcesGrouped).map(([group, resources]) => {
      if (!normalizedQuery) return [group, resources] as const;
      return [
        group,
        resources.filter((resource) => {
          const haystack = [
            resource.name,
            resource.description,
            resource.group,
            resource.resource_kind || '',
            resource.tags.join(' '),
            ...resource.entrypoints.map((item) => `${item.title} ${item.skill_name || ''} ${item.workspace_id || ''}`),
          ]
            .join(' ')
            .toLowerCase();
          return haystack.includes(normalizedQuery);
        }),
      ] as const;
    });
    return entries
      .filter(([, resources]) => resources.length > 0)
      .sort(([a], [b]) => {
        const indexA = groupOrder.indexOf(a);
        const indexB = groupOrder.indexOf(b);
        if (indexA === -1 && indexB === -1) return a.localeCompare(b);
        if (indexA === -1) return 1;
        if (indexB === -1) return -1;
        return indexA - indexB;
      });
  }, [query, resourcesGrouped]);

  const toggleGroup = (group: string) => {
    setExpandedGroups((prev) => ({ ...prev, [group]: !(prev[group] ?? true) }));
  };

  return (
    <div className="w-72 bg-white border-r flex flex-col h-full shadow-sm">
      <div className="p-4 border-b bg-gradient-to-r from-primary-50 to-white">
        <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-primary-500" />
          AI 资源中心
        </h2>
        <p className="text-xs text-gray-500 mt-1">搜索、收藏和快速打开资源</p>
        <div className="mt-3 relative">
          <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="搜索资源、标签、技能"
            className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-200"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto py-2 bg-gray-50">
        <ResourceSection
          title="推荐"
          icon={<Heart className="w-4 h-4 text-rose-500" />}
          resources={recommendedResources}
          currentResourceId={currentResourceId}
          favoriteIds={favoriteIds}
          onSelectResource={onSelectResource}
          onToggleFavorite={onToggleFavorite}
        />
        <ResourceSection
          title="最近"
          icon={<Clock3 className="w-4 h-4 text-sky-500" />}
          resources={recentResources}
          currentResourceId={currentResourceId}
          favoriteIds={favoriteIds}
          onSelectResource={onSelectResource}
          onToggleFavorite={onToggleFavorite}
        />
        <ResourceSection
          title="收藏"
          icon={<Star className="w-4 h-4 text-amber-500" />}
          resources={favoriteResources}
          currentResourceId={currentResourceId}
          favoriteIds={favoriteIds}
          onSelectResource={onSelectResource}
          onToggleFavorite={onToggleFavorite}
        />

        {filteredGroups.map(([group, resources]) => {
          const config = groupConfig[group] || {
            icon: <Layers className="w-5 h-5" />,
            color: 'text-gray-600',
            bgColor: 'bg-gray-50',
          };
          const isExpanded = expandedGroups[group] ?? true;

          return (
            <div key={group} className="mb-1">
              <button
                onClick={() => toggleGroup(group)}
                className={`w-full px-4 py-3 flex items-center justify-between hover:bg-gray-100 transition-colors ${config.bgColor}`}
              >
                <div className={`flex items-center gap-2 font-semibold ${config.color}`}>
                  {config.icon}
                  <span className="text-sm">{group}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400 bg-white px-2 py-0.5 rounded-full">{resources.length}</span>
                  {isExpanded ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
                </div>
              </button>
              {isExpanded && (
                <div className="py-1 bg-white">
                  {resources.map((resource) => (
                    <ResourceItem
                      key={resource.id}
                      resource={resource}
                      currentResourceId={currentResourceId}
                      isFavorite={favoriteIds.has(resource.id)}
                      onSelectResource={onSelectResource}
                      onToggleFavorite={onToggleFavorite}
                    />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="p-3 border-t bg-white">
        <div className="text-xs text-gray-400 text-center">共 {Object.values(resourcesGrouped).flat().length} 个资源</div>
      </div>
    </div>
  );
}
