import { createContext } from 'react';
import type { ContentBlock } from '@agentscope-ai/agentscope/message';

/**
 * Context that exposes the chat `send` function to deeply-nested
 * components (e.g. A2UI surfaces rendered inside tool-result blocks)
 * without prop-drilling through the `ToolRenderer` interface.
 *
 * When no provider is mounted, `useChatAction` returns `null` and
 * interactive surfaces should degrade gracefully (e.g. log to console).
 */
export interface ChatActionContextValue {
	/** Send a message to the agent as if the user typed it. */
	send: (content: ContentBlock[]) => void;
}

export const ChatActionContext = createContext<ChatActionContextValue | null>(null);
