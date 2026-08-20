import { useContext, useEffect, useMemo, useState } from 'react';
import { MessageProcessor } from '@a2ui/web_core/v0_9';
import { A2uiSurface, basicCatalog } from '@a2ui/react/v0_9';
import type { SurfaceModel } from '@a2ui/web_core/v0_9';
import type { ReactComponentImplementation } from '@a2ui/react/v0_9';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ChevronDown, ChevronUp, Layout } from 'lucide-react';
import { ChatActionContext } from '@/components/chat/ChatActionContext';

// ─── Component ───────────────────────────────────────────────────────────────

export interface A2UISurfaceProps {
	/** Raw A2UI JSONL text — each line is one A2UI message. */
	rawA2UI: string;
}

export function A2UISurface({ rawA2UI }: A2UISurfaceProps) {
	const [collapsed, setCollapsed] = useState(false);
	const chatAction = useContext(ChatActionContext);

	// Parse messages and normalize catalogId
	const messages = useMemo(() => {
		const lines = rawA2UI.split('\n').filter((l) => l.trim());
		const parsed: unknown[] = [];
		for (const line of lines) {
			try {
				parsed.push(JSON.parse(line));
			} catch {
				// Skip malformed lines
			}
		}
		// Normalize catalogId: the basicCatalog from @a2ui/react uses
		// the full URL as its ID, but agents commonly send "basic".
		const BASIC_CATALOG_ID =
			'https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json';
		for (const msg of parsed) {
			if (typeof msg !== 'object' || msg === null) continue;
			const m = msg as Record<string, unknown>;
			if (
				'createSurface' in m &&
				typeof m.createSurface === 'object' &&
				m.createSurface !== null
			) {
				const cs = m.createSurface as Record<string, unknown>;
				if (cs.catalogId === 'basic') {
					cs.catalogId = BASIC_CATALOG_ID;
				}
			}
		}
		return parsed;
	}, [rawA2UI]);

	// Create a fresh processor + surfaces state for each new set of messages.
	// This avoids "Surface already exists" errors on re-render.
	const [surfaces, setSurfaces] = useState<
		SurfaceModel<ReactComponentImplementation>[]
	>([]);

	useEffect(() => {
		if (messages.length === 0) {
			setSurfaces([]);
			return;
		}

		const processor = new MessageProcessor<ReactComponentImplementation>(
			[basicCatalog],
			(action) => {
				// Send the action back to the agent as a user message
				// so the agent can react to button clicks and other
				// user interactions.
				const actionText = `[A2UI Action] ${action.name}`;
				const contextStr = Object.keys(action.context).length > 0
					? `\nContext: ${JSON.stringify(action.context)}`
					: '';
				if (chatAction) {
					chatAction.send([{
						id: crypto.randomUUID(),
						type: 'text',
						text: actionText + contextStr,
						created_at: new Date().toISOString(),
						finished_at: new Date().toISOString(),
					}]);
				} else {
					console.log('A2UI action (no chat context):', action);
				}
			},
		);

		const sync = () =>
			setSurfaces(Array.from(processor.model.surfacesMap.values()));

		const createdSub = processor.onSurfaceCreated(sync);
		const deletedSub = processor.onSurfaceDeleted(sync);

		try {
			processor.processMessages(messages as never);
		} catch (err) {
			console.error('A2UI processing error:', err);
		}

		return () => {
			createdSub.unsubscribe();
			deletedSub.unsubscribe();
		};
	}, [messages, chatAction]);

	if (surfaces.length === 0) return null;

	return (
		<Card className="w-full border-primary/20">
			<CardHeader className="pb-2">
				<div className="flex items-center justify-between">
					<CardTitle className="flex items-center gap-2 text-sm">
						<Layout className="size-4" />
						A2UI Surface
					</CardTitle>
					<Button
						variant="ghost"
						size="sm"
						onClick={() => setCollapsed(!collapsed)}
					>
						{collapsed ? <ChevronDown className="size-4" /> : <ChevronUp className="size-4" />}
					</Button>
				</div>
			</CardHeader>
			{!collapsed && (
				<CardContent className="space-y-4">
					{surfaces.map((surface) => (
						<div key={surface.id} className="a2ui-surface">
							<A2uiSurface surface={surface} />
						</div>
					))}
				</CardContent>
			)}
		</Card>
	);
}
