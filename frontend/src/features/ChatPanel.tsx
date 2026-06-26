import * as React from "react";
import { Send, Sparkles, Bot, User } from "lucide-react";
import { api, type ChatResult, type ChatTurn } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/shared";
import { AgentMessage } from "@/components/AgentMessage";
import { cn } from "@/lib/utils";

type Msg = {
  role: "user" | "assistant";
  content?: string;
  result?: ChatResult;
  error?: boolean;
};

const PROMPTS = [
  "Find me a defender that can stop Haaland",
  "Build me a €150M front three that presses",
  "Compare Saliba and Gvardiol aerially",
  "Who has the most assists in the Premier League",
];

export function ChatPanel() {
  const [messages, setMessages] = React.useState<Msg[]>([]);
  const [input, setInput] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const endRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send(text?: string) {
    const msg = (text ?? input).trim();
    if (!msg || loading) return;
    setInput("");
    // build conversation history (last 8 turns) so the agent can resolve
    // follow-ups like "now under 23" against what came before
    const history: ChatTurn[] = messages
      .map((m): ChatTurn | null => {
        if (m.role === "user" && m.content) return { role: "user", content: m.content };
        if (m.role === "assistant" && m.result?.answer)
          return { role: "assistant", content: m.result.answer };
        return null;
      })
      .filter((t): t is ChatTurn => t !== null)
      .slice(-8);
    setMessages((m) => [...m, { role: "user", content: msg }]);
    setLoading(true);
    try {
      const res = await api.chat(msg, history);
      setMessages((m) => [...m, { role: "assistant", result: res }]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          error: true,
          content:
            "The agent is unavailable. The /chat endpoint needs GROQ_API_KEY set on the backend. " +
            `(${(e as Error).message})`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-[min(70vh,640px)] flex-col rounded-xl border">
      {/* messages */}
      <div className="flex-1 space-y-5 overflow-y-auto p-5">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-5 text-center">
            <div className="flex size-12 items-center justify-center rounded-xl bg-muted">
              <Sparkles className="size-5 text-muted-foreground" />
            </div>
            <div>
              <p className="text-sm font-medium">Ask the scouting agent</p>
              <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                Natural-language scouting — clones, counters, trait search,
                comparisons and squad building. It remembers the conversation,
                so follow-ups like "now under 23" just work.
              </p>
            </div>
            <div className="flex max-w-md flex-wrap justify-center gap-2">
              {PROMPTS.map((p) => (
                <Button
                  key={p}
                  variant="secondary"
                  size="sm"
                  onClick={() => void send(p)}
                >
                  {p}
                </Button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className="flex gap-3">
            <div
              className={cn(
                "flex size-7 shrink-0 items-center justify-center rounded-md",
                m.role === "user"
                  ? "bg-foreground text-background"
                  : "bg-muted text-muted-foreground"
              )}
            >
              {m.role === "user" ? (
                <User className="size-4" />
              ) : (
                <Bot className="size-4" />
              )}
            </div>
            <div className="min-w-0 flex-1 space-y-2">
              {m.result ? (
                <>
                  <Badge variant="muted" className="font-mono">
                    intent: {m.result.intent}
                  </Badge>
                  <AgentMessage result={m.result} />
                </>
              ) : (
                <p
                  className={cn(
                    "whitespace-pre-wrap text-sm leading-relaxed",
                    m.error && "text-negative"
                  )}
                >
                  {m.content}
                </p>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <div className="flex size-7 items-center justify-center rounded-md bg-muted">
              <Bot className="size-4" />
            </div>
            <Spinner /> thinking…
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* composer */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
        className="flex gap-2 border-t p-3"
      >
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask anything — e.g. ‘a deep-lying playmaker like Rodri’"
          className="h-10"
        />
        <Button type="submit" size="icon" className="size-10" disabled={loading}>
          <Send />
        </Button>
      </form>
    </div>
  );
}
