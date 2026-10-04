import { create } from 'zustand';

export type ErrorLevel = 'info' | 'warning' | 'error';
export type ErrorMode = 'idle' | 'toast' | 'fullscreen';

interface ErrorState {
  level: ErrorLevel;
  message: string;
  mode: ErrorMode;
  visible: boolean;
  retryAction: (() => void) | null;

  showError: (message: string, retryAction?: () => void) => void;
  showWarning: (message: string) => void;
  showInfo: (message: string) => void;
  showFullscreen: (message: string, retryAction?: () => void) => void;
  dismiss: () => void;
}

let autoDismissTimer: ReturnType<typeof setTimeout> | null = null;
let lastMessage = '';
let lastMessageTime = 0;
const DEDUP_INTERVAL = 5000; // 相同消息 5 秒内不重复显示
const AUTO_DISMISS_MS = 8000;

function clearAutoDismiss() {
  if (autoDismissTimer) {
    clearTimeout(autoDismissTimer);
    autoDismissTimer = null;
  }
}

function isDuplicate(message: string): boolean {
  const now = Date.now();
  if (message === lastMessage && now - lastMessageTime < DEDUP_INTERVAL) {
    return true;
  }
  lastMessage = message;
  lastMessageTime = now;
  return false;
}

export const useErrorStore = create<ErrorState>((set, get) => ({
  level: 'info',
  message: '',
  mode: 'idle',
  visible: false,
  retryAction: null,

  showError: (message, retryAction) => {
    if (isDuplicate(message)) return;
    clearAutoDismiss();
    set({ level: 'error', message, mode: 'toast', visible: true, retryAction: retryAction ?? null });
  },

  showWarning: (message) => {
    if (isDuplicate(message)) return;
    clearAutoDismiss();
    set({ level: 'warning', message, mode: 'toast', visible: true, retryAction: null });
    autoDismissTimer = setTimeout(() => get().dismiss(), AUTO_DISMISS_MS);
  },

  showInfo: (message) => {
    if (isDuplicate(message)) return;
    clearAutoDismiss();
    set({ level: 'info', message, mode: 'toast', visible: true, retryAction: null });
    autoDismissTimer = setTimeout(() => get().dismiss(), AUTO_DISMISS_MS);
  },

  showFullscreen: (message, retryAction) => {
    if (isDuplicate(message)) return;
    clearAutoDismiss();
    set({ level: 'error', message, mode: 'fullscreen', visible: true, retryAction: retryAction ?? null });
  },

  dismiss: () => {
    clearAutoDismiss();
    set({ mode: 'idle', visible: false, message: '', retryAction: null });
  },
}));