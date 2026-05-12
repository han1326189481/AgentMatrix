import { useState } from 'react';
import { Copy, Check, FileText } from 'lucide-react';

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
    const parts = text.split('\n');
    return parts.map((part, index) => {
      if (part.startsWith('# ')) {
        return <h2 key={index} className="text-xl font-bold text-white mt-6 mb-3">{part.slice(2)}</h2>;
      }
      if (part.startsWith('## ')) {
        return <h3 key={index} className="text-lg font-semibold text-blue-400 mt-4 mb-2">{part.slice(3)}</h3>;
      }
      if (part.startsWith('### ')) {
        return <h4 key={index} className="text-md font-medium text-blue-300 mt-3 mb-1">{part.slice(4)}</h4>;
      }
      if (part.startsWith('- ')) {
        return <li key={index} className="text-dark-300 ml-4">{part.slice(2)}</li>;
      }
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={index} className="text-white">{part.slice(2, -2)}</strong>;
      }
      if (part.trim()) {
        return <p key={index} className="text-dark-300 mb-2">{part}</p>;
      }
      return null;
    });
  };

  return (
    <div className="bg-dark-800/50 rounded-xl border border-dark-700 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-dark-700 bg-dark-800">
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5 text-blue-400" />
          <span className="text-sm font-medium text-white">Markdown 预览</span>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-dark-700 hover:bg-dark-600 text-sm text-dark-300 transition-colors"
        >
          {copied ? (
            <>
              <Check className="w-4 h-4 text-green-400" />
              已复制
            </>
          ) : (
            <>
              <Copy className="w-4 h-4" />
              复制
            </>
          )}
        </button>
      </div>

      <div className="p-6 overflow-y-auto max-h-96">
        {renderMarkdown(content)}
      </div>
    </div>
  );
}