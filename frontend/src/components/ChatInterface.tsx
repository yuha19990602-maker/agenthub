/** Chat interface component for native/skill conversations with Markdown support and streaming */

import { useState, useEffect, useRef, useCallback } from 'react';
import { Send, Loader2, RefreshCw, Copy, Check, Paperclip, X, Image, FileText } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeHighlight from 'rehype-highlight';
import { sessionApi } from '../api';
import type { Message, Resource, PendingFile } from '../types';

// Import KaTeX styles for math rendering
import 'katex/dist/katex.min.css';
import 'highlight.js/styles/github.css';

interface ChatInterfaceProps {
  sessionId: string;
  resource?: Resource;
  onRestart?: () => void;
}

type ChatMessage = Message & {
  message_id?: string;
  status?: 'streaming' | 'done' | 'error';
};

// Strip empty lines from text
const stripText = (text: string): string => {
  return text
    .split('\n')
    .map((line) => line.trimEnd())
    .join('\n')
    .trim();
};

// Format file size
const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

// Check if file is a text file that can be embedded
const isTextFile = (file: File): boolean => {
  const textTypes = [
    'text/',
    'application/json',
    'application/javascript',
    'application/typescript',
    'application/xml',
    'application/markdown',
    'application/x-python',
    'application/x-yaml',
  ];
  const textExtensions = ['.txt', '.md', '.markdown', '.json', '.js', '.ts', '.jsx', '.tsx', '.py', '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala', '.r', '.m', '.mm', '.sql', '.yaml', '.yml', '.xml', '.html', '.htm', '.css', '.scss', '.sass', '.less', '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd', '.csv', '.log', '.conf', '.config', '.ini', '.properties', '.env', '.dockerfile', '.makefile', '.cmake', '.gradle', '.pom', '.svg'];
  
  if (textTypes.some(type => file.type.startsWith(type))) return true;
  const ext = '.' + file.name.split('.').pop()?.toLowerCase();
  if (textExtensions.includes(ext)) return true;
  return false;
};

// Copy button component for code blocks
function CopyButton({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <button
      onClick={handleCopy}
      className="absolute top-2 right-2 p-1.5 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 transition-colors"
      title={copied ? '已复制' : '复制代码'}
    >
      {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
    </button>
  );
}

// File preview component
function FilePreview({ file, onRemove, content }: { file: PendingFile; onRemove: () => void; content?: string }) {
  const isImage = file.file.type.startsWith('image/');
  
  return (
    <div className="relative group">
      <div className="flex items-center gap-2 px-3 py-2 bg-gray-100 rounded-lg border border-gray-200">
        {isImage ? (
          <Image className="w-4 h-4 text-blue-500" />
        ) : (
          <FileText className="w-4 h-4 text-orange-500" />
        )}
        <div className="flex-1 min-w-0">
          <p className="text-sm text-gray-700 truncate">{file.file.name}</p>
          <p className="text-xs text-gray-500">{formatFileSize(file.file.size)}</p>
        </div>
        <button
          onClick={onRemove}
          className="p-1 hover:bg-gray-200 rounded transition-colors"
          title="移除文件"
        >
          <X className="w-4 h-4 text-gray-500" />
        </button>
      </div>
      {isImage && file.previewUrl && (
        <div className="mt-2 max-w-xs">
          <img src={file.previewUrl} alt={file.file.name} className="max-h-32 rounded-lg border border-gray-200 object-contain" />
        </div>
      )}
      {content && (
        <div className="mt-2 p-2 bg-gray-50 rounded border border-gray-200 max-h-32 overflow-y-auto">
          <pre className="text-xs text-gray-600 whitespace-pre-wrap">{content.substring(0, 500)}{content.length > 500 ? '...' : ''}</pre>
        </div>
      )}
    </div>
  );
}

export function ChatInterface({ sessionId, resource, onRestart }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([]);
  const [fileContents, setFileContents] = useState<Map<string, string>>(new Map());
  const [, setIsStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => { loadMessages(); }, [sessionId]);
  useEffect(() => { scrollToBottom(); }, [messages]);
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [inputText]);

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) abortControllerRef.current.abort();
      pendingFiles.forEach(file => { if (file.previewUrl) URL.revokeObjectURL(file.previewUrl); });
    };
  }, []);

  const loadMessages = async () => {
    if (!sessionId) {
      console.log('ChatInterface: No sessionId, skipping message load');
      return;
    }
    try {
      setIsLoadingHistory(true);
      console.log('ChatInterface: Loading messages for session', sessionId);
      const response = await sessionApi.getMessages(sessionId);
      const strippedMessages = response.data.map((msg: Message) => ({ ...msg, text: stripText(msg.text) }));
      setMessages(strippedMessages);
    } catch (error) {
      console.error('Failed to load messages:', error);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });

  const readFileContent = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve(e.target?.result as string);
      reader.onerror = (e) => reject(e);
      reader.readAsText(file);
    });
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    for (const file of Array.from(files)) {
      const pendingFile: PendingFile = {
        file,
        id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        status: 'pending',
      };
      if (file.type.startsWith('image/')) pendingFile.previewUrl = URL.createObjectURL(file);
      setPendingFiles(prev => [...prev, pendingFile]);

      if (isTextFile(file) && file.size < 1024 * 1024) {
        try {
          const content = await readFileContent(file);
          setFileContents(prev => new Map(prev).set(pendingFile.id, content));
        } catch (err) {
          console.error('Failed to read file:', err);
        }
      }
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const removePendingFile = (id: string) => {
    setPendingFiles(prev => {
      const file = prev.find(f => f.id === id);
      if (file?.previewUrl) URL.revokeObjectURL(file.previewUrl);
      return prev.filter(f => f.id !== id);
    });
    setFileContents(prev => { const newMap = new Map(prev); newMap.delete(id); return newMap; });
  };

  const buildMessageWithFiles = (): string => {
    const trimmedInput = inputText.trim();
    if (pendingFiles.length === 0) return trimmedInput;

    const textFiles: { name: string; content: string }[] = [];
    const otherFiles: string[] = [];
    
    for (const pendingFile of pendingFiles) {
      const content = fileContents.get(pendingFile.id);
      if (content !== undefined) {
        textFiles.push({ name: pendingFile.file.name, content });
      } else if (pendingFile.file.type.startsWith('image/')) {
        otherFiles.push(`[图片附件: ${pendingFile.file.name}]`);
      } else {
        otherFiles.push(`[文件附件: ${pendingFile.file.name} (${formatFileSize(pendingFile.file.size)})]`);
      }
    }

    let message = trimmedInput;
    
    if (textFiles.length > 0) {
      if (message) message += '\n\n';
      message += '=== 以下是我上传的文件内容，请根据这些内容回答我的问题 ===\n\n';
      for (const file of textFiles) {
        const ext = file.name.split('.').pop() || 'txt';
        message += `----- 文件开始: ${file.name} -----\n`;
        message += `\`\`\`${ext}\n${file.content}\n\`\`\`\n`;
        message += `----- 文件结束: ${file.name} -----\n\n`;
      }
    }
    
    if (otherFiles.length > 0) {
      if (message) message += '\n';
      message += otherFiles.join('\n');
    }
    
    return message;
  };

  const handleSendMessage = async () => {
    const trimmedInput = inputText.trim();
    if ((!trimmedInput && pendingFiles.length === 0) || isLoading) return;

    // Validate sessionId
    if (!sessionId) {
      console.error('ChatInterface: No sessionId available');
      alert('会话未创建，请重新选择资源');
      return;
    }

    const messageText = buildMessageWithFiles();
    if (!messageText) return;

    const userMessage: ChatMessage = { role: 'user', text: messageText, timestamp: new Date().toISOString() };
    setMessages(prev => [...prev, userMessage]);
    setInputText('');
    setIsLoading(true);
    setPendingFiles([]);
    setFileContents(new Map());
    if (textareaRef.current) textareaRef.current.style.height = 'auto';

    setIsStreaming(true);

    console.log('ChatInterface: Sending message to session', sessionId, 'message length:', messageText.length);
    
    try {
      abortControllerRef.current = sessionApi.sendMessageStream(
        sessionId,
        messageText,
        {
        onStart: (messageId: string) => {
          console.log('ChatInterface: Stream started, messageId:', messageId);
          setMessages(prev => [
            ...prev,
            {
              message_id: messageId,
              role: 'assistant',
              text: '',
              status: 'streaming',
              timestamp: new Date().toISOString(),
            },
          ]);
        },
        onDelta: (chunk: string, messageId: string) => {
          setMessages(prev => {
            let matched = false;
            const nextMessages = prev.map((msg) => {
              if (msg.message_id === messageId) {
                matched = true;
                return { ...msg, text: msg.text + chunk };
              }
              return msg;
            });
            if (matched) return nextMessages;
            return [
              ...prev,
              {
                message_id: messageId,
                role: 'assistant',
                text: chunk,
                status: 'streaming',
                timestamp: new Date().toISOString(),
              },
            ];
          });
        },
        onDone: (messageId: string) => {
          console.log('ChatInterface: Stream done');
          setIsLoading(false);
          setIsStreaming(false);
          abortControllerRef.current = null;
          setMessages(prev => prev.map((msg) => (
            msg.message_id === messageId ? { ...msg, status: 'done' } : msg
          )));
        },
        onError: (error: string, messageId?: string) => {
          console.error('ChatInterface: Stream error:', error);
          setIsLoading(false);
          setIsStreaming(false);
          abortControllerRef.current = null;
          setMessages(prev => {
            if (messageId) {
              let found = false;
              const nextMessages = prev.map((msg) => {
                if (msg.message_id === messageId) {
                  found = true;
                  return {
                    ...msg,
                    status: 'error' as const,
                    text: msg.text || '消息发送失败，请重试',
                  };
                }
                return msg;
              });
              if (found) return nextMessages;
            }
            return [
              ...prev,
              { role: 'system', text: '消息发送失败，请重试', timestamp: new Date().toISOString() },
            ];
          });
        }
      }
      );
    } catch (err) {
      console.error('ChatInterface: Error sending message:', err);
      setIsLoading(false);
      setIsStreaming(false);
      setMessages(prev => {
        const lastMsg = prev[prev.length - 1];
        if (lastMsg?.role === 'assistant') {
          return [...prev.slice(0, -1), { role: 'system', text: '消息发送失败，请重试', timestamp: new Date().toISOString() }];
        }
        return prev;
      });
    }
  };

  const handleStopStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsLoading(false);
      setIsStreaming(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const renderMarkdown = useCallback((content: string) => (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeKatex, rehypeHighlight]}
      components={{
        code({ className, children, ...props }: any) {
          const match = /language-(\w+)/.exec(className || '');
          const isInline = !className;
          const code = String(children).replace(/\n$/, '');
          if (!isInline) {
            return (
              <div className="relative my-3">
                <div className="flex items-center justify-between px-4 py-2 bg-gray-800 text-gray-300 text-xs rounded-t-lg">
                  <span>{match ? match[1] : 'code'}</span>
                  <CopyButton code={code} />
                </div>
                <pre className="bg-gray-900 text-gray-100 p-4 rounded-b-lg overflow-x-auto text-sm">
                  <code className={className} {...props}>{children}</code>
                </pre>
              </div>
            );
          }
          return <code className="bg-gray-100 text-gray-800 px-1.5 py-0.5 rounded text-sm font-mono" {...props}>{children}</code>;
        },
        table({ children }) { return <div className="overflow-x-auto my-4"><table className="min-w-full border-collapse border border-gray-300">{children}</table></div>; },
        thead({ children }) { return <thead className="bg-gray-100">{children}</thead>; },
        th({ children }) { return <th className="border border-gray-300 px-4 py-2 text-left font-semibold text-gray-700">{children}</th>; },
        td({ children }) { return <td className="border border-gray-300 px-4 py-2 text-gray-600">{children}</td>; },
        ul({ children }) { return <ul className="list-disc pl-6 my-2 space-y-1">{children}</ul>; },
        ol({ children }) { return <ol className="list-decimal pl-6 my-2 space-y-1">{children}</ol>; },
        li({ children }) { return <li className="text-gray-700">{children}</li>; },
        h1({ children }) { return <h1 className="text-2xl font-bold text-gray-900 my-4">{children}</h1>; },
        h2({ children }) { return <h2 className="text-xl font-bold text-gray-800 my-3">{children}</h2>; },
        h3({ children }) { return <h3 className="text-lg font-bold text-gray-800 my-2">{children}</h3>; },
        p({ children }) { return <p className="my-2 text-gray-700 leading-relaxed">{children}</p>; },
        blockquote({ children }) { return <blockquote className="border-l-4 border-primary-300 pl-4 my-3 text-gray-600 italic bg-gray-50 py-2 pr-4 rounded-r">{children}</blockquote>; },
        a({ href, children }) { return <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary-600 hover:text-primary-700 underline">{children}</a>; },
        hr() { return <hr className="my-4 border-gray-200" />; },
      }}
    >{content}</ReactMarkdown>
  ), []);

  return (
    <div className="flex flex-col h-full bg-gradient-to-b from-gray-50 to-white">
      {resource && (
        <div className="px-6 py-4 border-b bg-white flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-gray-900">{resource.name}</h2>
            <p className="text-sm text-gray-500">{resource.description}</p>
          </div>
          {onRestart && (
            <button onClick={onRestart} className="flex items-center gap-2 px-4 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors">
              <RefreshCw className="w-4 h-4" />新对话
            </button>
          )}
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-6 space-y-6">
        {isLoadingHistory ? (
          <div className="flex justify-center items-center h-full"><Loader2 className="w-8 h-8 animate-spin text-primary-500" /></div>
        ) : messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-500">
            <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mb-4"><Send className="w-8 h-8 text-primary-500" /></div>
            <p className="text-lg font-medium mb-2">开始新的对话</p>
            <p className="text-sm text-gray-400">在下方输入框中输入您的问题，或上传文件</p>
            {resource?.config?.starter_prompts && (
              <div className="mt-6 flex flex-wrap gap-2 justify-center max-w-md">
                {resource.config.starter_prompts.map((prompt, idx) => (
                  <button key={idx} onClick={() => setInputText(prompt)} className="px-4 py-2 bg-white border border-gray-200 rounded-full text-sm text-gray-600 hover:border-primary-300 hover:text-primary-600 transition-colors">{prompt}</button>
                ))}
              </div>
            )}
          </div>
        ) : (
          messages.map((message, index) => (
            <div key={index} className={`flex ${message.role === 'user' ? 'justify-end' : message.role === 'system' ? 'justify-center' : 'justify-start'}`}>
              <div className={`max-w-[85%] sm:max-w-[75%] ${message.role === 'user' ? 'message-user' : message.role === 'assistant' ? 'message-assistant' : 'message-system'}`}>
                {message.role === 'user' && <span className="text-xs opacity-70 mb-1 block font-medium">您</span>}
                {message.role === 'assistant' && <span className="text-xs text-gray-500 mb-1 block font-medium">AI 助手</span>}
                {message.role === 'assistant' ? (
                  <div className="markdown-content">{message.text ? renderMarkdown(message.text) : <div className="flex items-center gap-2 text-gray-400"><Loader2 className="w-4 h-4 animate-spin" /><span>思考中...</span></div>}</div>
                ) : (<p className="whitespace-pre-wrap break-words">{message.text}</p>)}
                {message.timestamp && <span className="text-xs opacity-50 mt-2 block">{new Date(message.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}</span>}
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="border-t bg-white px-4 sm:px-6 py-4">
        <div className="max-w-4xl mx-auto">
          {pendingFiles.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {pendingFiles.map(file => <FilePreview key={file.id} file={file} onRemove={() => removePendingFile(file.id)} content={fileContents.get(file.id)} />)}
            </div>
          )}

          <div className="relative flex items-end gap-3 bg-gray-50 border border-gray-200 rounded-2xl p-3 focus-within:border-primary-400 focus-within:ring-2 focus-within:ring-primary-100 transition-all">
            <input ref={fileInputRef} type="file" multiple accept="*/*" className="hidden" onChange={handleFileSelect} />
            <button onClick={() => fileInputRef.current?.click()} disabled={isLoading} className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded-lg transition-colors disabled:opacity-50" title="上传文件"><Paperclip className="w-5 h-5" /></button>
            <textarea ref={textareaRef} value={inputText} onChange={(e) => setInputText(e.target.value)} onKeyDown={handleKeyDown} placeholder="输入消息... (Enter 发送，Shift+Enter 换行)" className="flex-1 bg-transparent border-0 resize-none focus:outline-none text-gray-800 placeholder-gray-400 min-h-[56px] max-h-[200px] py-2 px-1" rows={2} disabled={isLoading} />
            {isLoading ? (
              <button onClick={handleStopStreaming} className="mb-1 px-4 py-2.5 bg-red-500 text-white rounded-xl hover:bg-red-600 transition-all flex items-center gap-2 font-medium shadow-sm" title="停止生成"><span className="w-2 h-2 bg-white rounded-sm"></span>停止</button>
            ) : (
              <button onClick={handleSendMessage} disabled={(!inputText.trim() && pendingFiles.length === 0)} className="mb-1 px-5 py-2.5 bg-primary-500 text-white rounded-xl hover:bg-primary-600 transition-all disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center gap-2 font-medium shadow-sm hover:shadow"><span>发送</span><Send className="w-4 h-4" /></button>
            )}
          </div>
          <p className="text-xs text-gray-400 mt-2 text-center">AI 生成的内容仅供参考，请核实重要信息</p>
        </div>
      </div>
    </div>
  );
}
