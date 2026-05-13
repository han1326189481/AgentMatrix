'use client';

import { useState } from 'react';
import { Copy, Check, FileText, ChevronDown } from 'lucide-react';

interface ResultPreviewProps {
  content: string;
}

export default function ResultPreview({ content }: ResultPreviewProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const renderMarkdown = (text: string) => {
    const lines = text.split('\n');
    const elements: JSX.Element[] = [];
    let key = 0;

    lines.forEach((line) => {
      if (line.startsWith('# ')) {
        elements.push(<h1 key={key++} className="text-2xl font-bold text-white mb-4 mt-6">{line.slice(2)}</h1>);
      } else if (line.startsWith('## ')) {
        elements.push(<h2 key={key++} className="text-xl font-semibold text-white mb-3 mt-5">{line.slice(3)}</h2>);
      } else if (line.startsWith('### ')) {
        elements.push(<h3 key={key++} className="text-lg font-medium text-white mb-2 mt-4">{line.slice(4)}</h3>);
      } else if (line.startsWith('- ')) {
        elements.push(<li key={key++} className="text-dark-300 ml-4 mb-1 flex items-start gap-2">
          <span className="text-green-400 mt-1">-</span>
          <span>{line.slice(2)}</span>
        </li>);
      } else if (line.startsWith('|')) {
        const parts = line.split('|').filter(p => p.trim());
        if (line.includes('---')) {
          elements.push(<div key={key++} className="border-b border-dark-600" />);
        } else {
          elements.push(<div key={key++} className="flex border-b border-dark-700">
            {parts.map((cell, i) => (
              <div key={i} className={`flex-1 px-4 py-2 ${i === 0 ? 'font-medium text-white' : 'text-dark-300'}`}>
                {cell.trim()}
              </div>
            ))}
          </div>);
        }
      } else if (line.trim()) {
        elements.push(<p key={key++} className="text-dark-300 mb-2">{line}</p>);
      }
    });

    return elements;
  };

  return (
    <div className="relative">
      <div className="absolute top-0 right-0 flex items-center gap-2">
        <button
          onClick={handleCopy}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
            copied 
              ? 'bg-green-500/20 text-green-400' 
              : 'bg-dark-700 hover:bg-dark-600 text-dark-300'
          }`}
        >
          {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
          <span>{copied ? '已复制' : '复制'}</span>
        </button>
      </div>

      <div className="bg-dark-700/50 rounded-lg border border-dark-600 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 bg-dark-600/50 border-b border-dark-600">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-dark-400" />
            <span className="text-sm text-dark-300">Markdown 预览</span>
          </div>
          <button className="text-xs text-dark-500 hover:text-dark-400 transition-colors">
            查看详情
          </button>
        </div>
        
        <div className="p-6 prose prose-invert max-w-none">
          {renderMarkdown(content)}
        </div>
      </div>
    </div>
  );
}