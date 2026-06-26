import { Users, Shield, Shirt, Fingerprint, Banknote, Sparkles } from "lucide-react";
import { Header } from "@/components/Header";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { CloneSearch } from "@/features/CloneSearch";
import { MatchupView } from "@/features/MatchupView";
import { SquadBuilder } from "@/features/SquadBuilder";
import { ArchetypeView } from "@/features/ArchetypeView";
import { ValueExplorer } from "@/features/ValueExplorer";
import { ChatPanel } from "@/features/ChatPanel";

const TABS = [
  { value: "clones", label: "Clones", icon: Users, el: <CloneSearch /> },
  { value: "matchup", label: "Matchup", icon: Shield, el: <MatchupView /> },
  { value: "squad", label: "Squad", icon: Shirt, el: <SquadBuilder /> },
  { value: "archetype", label: "Archetype", icon: Fingerprint, el: <ArchetypeView /> },
  { value: "value", label: "Value", icon: Banknote, el: <ValueExplorer /> },
  { value: "chat", label: "Agent", icon: Sparkles, el: <ChatPanel /> },
];

export default function App() {
  return (
    <div className="min-h-svh">
      <Header />

      {/* hero */}
      <div className="relative overflow-hidden border-b">
        <div className="bg-grid pointer-events-none absolute inset-0" />
        <div className="relative mx-auto max-w-6xl px-5 py-14 sm:py-20">
          <p className="mb-3 font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">
            Big 5 · 2024/25 · 1,700+ players
          </p>
          <h1 className="max-w-3xl text-4xl font-semibold leading-[1.05] tracking-tight sm:text-5xl">
            Scout every player in Europe's
            <br className="hidden sm:block" /> top five leagues.
          </h1>
          <p className="mt-4 max-w-xl text-base text-muted-foreground sm:text-lg">
            Statistical clones, playing-style archetypes, market-value
            estimates and goalkeeper matches — from one similarity engine.
          </p>
        </div>
      </div>

      {/* main */}
      <main className="mx-auto max-w-6xl px-5 py-8">
        <Tabs defaultValue="clones">
          <TabsList className="h-11">
            {TABS.map(({ value, label, icon: Icon }) => (
              <TabsTrigger key={value} value={value} className="px-3.5">
                <Icon />
                <span className="hidden sm:inline">{label}</span>
              </TabsTrigger>
            ))}
          </TabsList>

          {TABS.map(({ value, el }) => (
            <TabsContent key={value} value={value}>
              {el}
            </TabsContent>
          ))}
        </Tabs>
      </main>

      <footer className="border-t">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-2 px-5 py-6 text-xs text-muted-foreground sm:flex-row">
          <p>
            Built with FastAPI · scikit-learn · PyTorch · LangGraph · React.
          </p>
          <p className="font-mono">data: FBref via worldfootballR</p>
        </div>
      </footer>
    </div>
  );
}
