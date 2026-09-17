"use client";

import {
  IconArrowRight,
  IconBooks,
  IconFlame,
  IconLayoutSidebar,
  IconMessageQuestion,
  IconPlus,
  IconRefresh,
  IconRosetteDiscountCheck,
  IconSchool,
  IconShieldCheck,
} from "@tabler/icons-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Label,
  Pie,
  PieChart,
  XAxis,
  YAxis,
} from "recharts";
import { AiOrb } from "@/components/ai-orb";
import { useAuth } from "@/components/auth-provider";
import { ChatSidebar } from "@/components/chat/chat-sidebar";
import { SidebarDrawer } from "@/components/sidebar-drawer";
import { BorderBeam } from "@/components/ui/border-beam";
import { Button } from "@/components/ui/button";
import {
  type ChartConfig,
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import { MagicCard } from "@/components/ui/magic-card";
import { NumberTicker } from "@/components/ui/number-ticker";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import {
  type ConversationSummary,
  type Dashboard,
  DOC_TYPE_LABELS,
  STAGE_LABELS,
} from "@/lib/types";
import { cn, hasKhmer } from "@/lib/utils";

/**
 * Study dashboard.
 *
 * Built from community shadcn registries as well as the official one: stat cards are
 * Magic UI `MagicCard` + `NumberTicker`, the hero carries a Magic UI `BorderBeam` and
 * the ElevenLabs UI `Orb`, and the charts are shadcn `chart` (Recharts). Colours come
 * from the design tokens, so the charts follow the brand palette and dark mode.
 */

// Spotlight colours for MagicCard: brand blue into the accent red.
const SPOTLIGHT_FROM = "#3F8FE0";
const SPOTLIGHT_TO = "#EA1D24";

const activityConfig = {
  questions: { label: "Questions", color: "var(--color-chart-1)" },
  quizzes: { label: "Quizzes", color: "var(--color-chart-2)" },
  resources: { label: "Resources added", color: "var(--color-chart-3)" },
} satisfies ChartConfig;

const scoreConfig = {
  percent: { label: "Score", color: "var(--color-chart-1)" },
} satisfies ChartConfig;

const PALETTE = [1, 2, 3, 4, 5].map((i) => `var(--color-chart-${i})`);

function parseDay(day: string) {
  const [y, m, d] = day.split("-").map(Number);
  return new Date(y, m - 1, d);
}

const shortDate = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });
const longDate = new Intl.DateTimeFormat(undefined, { weekday: "short", month: "short", day: "numeric" });

function relativeTime(iso: string) {
  const seconds = (new Date(iso).getTime() - Date.now()) / 1000;
  const format = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 31_536_000],
    ["month", 2_592_000],
    ["week", 604_800],
    ["day", 86_400],
    ["hour", 3_600],
    ["minute", 60],
  ];
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return format.format(Math.round(seconds / size), unit);
  }
  return "just now";
}

function greeting(date = new Date()) {
  const hour = date.getHours();
  if (hour < 12) return { km: "អរុណសួស្តី", en: "Good morning" };
  if (hour < 18) return { km: "ទិវាសួស្តី", en: "Good afternoon" };
  return { km: "សាយណ្ហសួស្តី", en: "Good evening" };
}

export function DashboardView() {
  const { user, ready } = useAuth();
  const router = useRouter();
  const [data, setData] = React.useState<Dashboard | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [conversations, setConversations] = React.useState<ConversationSummary[] | null>(null);
  const [sidebarOpen, setSidebarOpen] = React.useState(false);

  React.useEffect(() => {
    if (ready && !user) router.replace("/sign-in");
  }, [ready, user, router]);

  const load = React.useCallback(
    () =>
      Promise.all([api.getDashboard(), api.listConversations()]).then(
        ([dashboard, chats]) => {
          setData(dashboard);
          setConversations(chats);
          setError(null);
        },
        (err: unknown) => {
          setError(err instanceof Error ? err.message : "Could not load your dashboard");
          setConversations((current) => current ?? []);
        },
      ),
    [],
  );

  // State is only set when the requests settle, never synchronously in the effect.
  const signedIn = Boolean(user);
  React.useEffect(() => {
    if (!signedIn) return;
    let cancelled = false;
    Promise.all([api.getDashboard(), api.listConversations()]).then(
      ([dashboard, chats]) => {
        if (cancelled) return;
        setData(dashboard);
        setConversations(chats);
      },
      (err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Could not load your dashboard");
        setConversations([]);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [signedIn]);

  // Refresh while something is processing, so progress bars move.
  const processing = (data?.processing.length ?? 0) > 0;
  React.useEffect(() => {
    if (!processing) return;
    const timer = window.setInterval(() => void load(), 4000);
    return () => window.clearInterval(timer);
  }, [processing, load]);

  if (!ready || !user) {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <p className="text-sm text-text-muted">Loading…</p>
      </div>
    );
  }

  return (
    <div className="flex h-dvh overflow-hidden bg-canvas">
      <SidebarDrawer open={sidebarOpen} onClose={() => setSidebarOpen(false)}>
        <ChatSidebar
          conversations={conversations}
          activeId={null}
          onSelect={(id) => router.push(`/c/${id}`)}
          onNew={() => router.push("/")}
          onRename={async (id, title) => {
            await api.renameConversation(id, title).catch(() => {});
            void load();
          }}
          onDelete={async (id) => {
            await api.deleteConversation(id).catch(() => {});
            void load();
          }}
        />
      </SidebarDrawer>

      <main className="min-w-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-5 px-4 py-5 sm:px-6 sm:py-8">
          <header className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              aria-label="Open navigation"
              onClick={() => setSidebarOpen(true)}
            >
              <IconLayoutSidebar size={18} />
            </Button>
            <div className="min-w-0 flex-1">
              <h1 lang="km" className="font-display-km text-2xl text-text">
                ផ្ទាំងសិក្សា
              </h1>
              <p className="-mt-1 text-sm font-semibold text-emphasis">Study dashboard</p>
            </div>
            <Button variant="outline" size="icon" aria-label="Refresh" onClick={() => void load()}>
              <IconRefresh size={17} stroke={1.75} />
            </Button>
            <Button size="lg" nativeButton={false} render={<Link href="/" />}>
              <IconPlus size={17} stroke={2} />
              <span className="hidden sm:inline">New chat</span>
            </Button>
          </header>

          {error && !data ? (
            <div
              role="alert"
              className="flex items-center justify-between gap-3 rounded-lg border border-danger/30 bg-danger-bg px-4 py-3 text-sm text-danger"
            >
              {error}
              <Button variant="outline" size="sm" onClick={() => void load()}>
                Try again
              </Button>
            </div>
          ) : !data ? (
            <DashboardSkeleton />
          ) : data.totals.resources === 0 && data.totals.chats === 0 ? (
            <EmptyDashboard name={user.displayName} />
          ) : (
            <Loaded data={data} name={user.displayName} />
          )}
        </div>
      </main>
    </div>
  );
}

function Loaded({ data, name }: { data: Dashboard; name: string }) {
  const { totals } = data;
  const hello = greeting();
  const lastChat = data.recentChats[0];
  const thisWeek = data.activity.slice(-7).reduce((sum, d) => sum + d.questions, 0);
  const groundedRate = totals.answers ? totals.groundedAnswers / totals.answers : 0;

  return (
    <>
      <div className="grid gap-4 lg:grid-cols-12">
        {/* Hero */}
        <section className="relative overflow-hidden rounded-xl border border-border bg-surface shadow-sm lg:col-span-8">
          <div className="flex flex-col-reverse items-center gap-4 p-6 sm:flex-row sm:p-7">
            <div className="flex min-w-0 flex-1 flex-col gap-3 text-center sm:text-left">
              <div>
                <h2 lang="km" className="font-display-km text-2xl text-text">
                  {hello.km}
                </h2>
                <p className="text-base font-semibold text-emphasis">
                  {hello.en}, {name}
                </p>
              </div>
              <p className="max-w-md text-sm text-text-muted">
                {thisWeek > 0
                  ? `You asked ${thisWeek} ${thisWeek === 1 ? "question" : "questions"} this week.`
                  : "No questions yet this week — pick up where you left off."}{" "}
                {totals.processing > 0 &&
                  `${totals.processing} ${totals.processing === 1 ? "resource is" : "resources are"} still being processed.`}
              </p>
              <div className="flex flex-wrap justify-center gap-2 sm:justify-start">
                <Button size="lg" nativeButton={false} render={<Link href="/" />}>
                  <IconPlus size={17} /> New chat
                </Button>
                {lastChat && (
                  <Button
                    size="lg"
                    variant="outline"
                    className="max-w-72"
                    nativeButton={false} render={<Link href={`/c/${lastChat.id}`} />}
                  >
                    <span className="truncate" lang={hasKhmer(lastChat.title) ? "km" : undefined}>
                      Continue: {lastChat.title}
                    </span>
                    <IconArrowRight size={16} />
                  </Button>
                )}
              </div>
            </div>
            <AiOrb className="size-32 sm:size-40" />
          </div>
          <BorderBeam
            size={120}
            duration={9}
            colorFrom={SPOTLIGHT_FROM}
            colorTo={SPOTLIGHT_TO}
            borderWidth={1.5}
          />
        </section>

        {/* Streak */}
        <StreakCard data={data} />
      </div>

      {/* Headline numbers */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={IconBooks}
          label="Resources"
          value={totals.resources}
          detail={`${totals.ready} ready${totals.failed ? ` · ${totals.failed} failed` : ""}`}
        />
        <StatCard
          icon={IconMessageQuestion}
          label="Questions asked"
          value={totals.questions}
          detail={`across ${totals.chats} ${totals.chats === 1 ? "chat" : "chats"}`}
        />
        <StatCard
          icon={IconShieldCheck}
          label="Answered from sources"
          value={Math.round(groundedRate * 100)}
          suffix="%"
          detail={`${totals.groundedAnswers} of ${totals.answers} answers cited your materials`}
        />
        <StatCard
          icon={IconRosetteDiscountCheck}
          label="Quiz average"
          value={Math.round(totals.averageScore * 100)}
          suffix="%"
          detail={`${totals.quizzes} ${totals.quizzes === 1 ? "quiz" : "quizzes"} taken`}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-12">
        <ActivityCard data={data} />
        <ResourceMixCard data={data} />
      </div>

      <div className="grid gap-4 lg:grid-cols-12">
        <QuizTrendCard data={data} />
        <MostCitedCard data={data} />
      </div>

      <div className="grid gap-4 lg:grid-cols-12">
        <RecentChatsCard data={data} />
        <ProcessingCard data={data} />
      </div>
    </>
  );
}

function Panel({
  title,
  description,
  action,
  className,
  children,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section
      className={cn(
        "flex flex-col gap-4 rounded-lg border border-border bg-surface p-5 shadow-sm",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="micro-label text-text-muted">{title}</h2>
          {description && <p className="mt-1 text-sm text-text-subtle">{description}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  suffix,
  detail,
}: {
  icon: typeof IconBooks;
  label: string;
  value: number;
  suffix?: string;
  detail: string;
}) {
  return (
    <MagicCard
      className="rounded-lg shadow-sm"
      gradientFrom={SPOTLIGHT_FROM}
      gradientTo={SPOTLIGHT_TO}
      gradientColor="color-mix(in oklch, var(--color-primary) 12%, transparent)"
      gradientOpacity={1}
      gradientSize={220}
    >
      <div className="flex flex-col gap-3 p-5">
        <div className="flex items-center justify-between">
          <span className="micro-label text-text-muted">{label}</span>
          <span className="flex size-8 items-center justify-center rounded-md bg-primary-soft text-primary-text">
            <Icon size={17} stroke={1.75} aria-hidden />
          </span>
        </div>
        <p className="text-2xl font-semibold tracking-tight text-text tabular-nums">
          {value > 0 ? <NumberTicker value={value} className="text-text" /> : 0}
          {suffix}
        </p>
        <p className="truncate text-xs text-text-subtle" title={detail}>
          {detail}
        </p>
      </div>
    </MagicCard>
  );
}

function StreakCard({ data }: { data: Dashboard }) {
  const days = data.activity.slice(-14);
  const max = Math.max(1, ...days.map((d) => d.questions + d.quizzes));
  const streak = data.totals.streakDays;

  return (
    <MagicCard
      mode="orb"
      className="rounded-xl shadow-sm lg:col-span-4"
      glowFrom={SPOTLIGHT_FROM}
      glowTo={SPOTLIGHT_TO}
      glowOpacity={0.35}
      glowSize={320}
    >
      <div className="flex h-full flex-col gap-4 p-6">
        <div className="flex items-center justify-between">
          <span className="micro-label text-text-muted">Study streak</span>
          <IconFlame
            size={20}
            stroke={1.75}
            className={streak > 0 ? "text-emphasis" : "text-text-subtle"}
            aria-hidden
          />
        </div>
        <p className="flex items-baseline gap-2">
          <span className="text-4xl font-semibold tracking-tight text-text tabular-nums">
            {streak > 0 ? <NumberTicker value={streak} className="text-text" /> : 0}
          </span>
          <span className="text-sm text-text-muted">{streak === 1 ? "day" : "days"} in a row</span>
        </p>
        <div>
          <ol className="grid grid-cols-14 gap-1" aria-label="Activity over the last 14 days">
            {days.map((day) => {
              const count = day.questions + day.quizzes;
              return (
                <li
                  key={day.day}
                  title={`${longDate.format(parseDay(day.day))}: ${day.questions} questions, ${day.quizzes} quizzes`}
                  className="aspect-square rounded-sm"
                  style={{
                    background:
                      count === 0
                        ? "var(--color-surface-muted)"
                        : `color-mix(in oklch, var(--color-primary) ${25 + (count / max) * 75}%, transparent)`,
                  }}
                >
                  <span className="sr-only">
                    {longDate.format(parseDay(day.day))}: {count} activities
                  </span>
                </li>
              );
            })}
          </ol>
          <div className="mt-1.5 flex justify-between text-[11px] text-text-subtle">
            <span>2 weeks ago</span>
            <span>Today</span>
          </div>
        </div>
        <p className="mt-auto text-xs text-text-muted">
          {streak > 0
            ? "Ask a question or take a quiz today to keep it going."
            : "Ask one question today to start a streak."}
        </p>
      </div>
    </MagicCard>
  );
}

function ActivityCard({ data }: { data: Dashboard }) {
  const [range, setRange] = React.useState("30");
  const rows = data.activity.slice(-Number(range));

  return (
    <Panel
      title="Activity"
      description="Questions, quizzes and resources per day"
      className="lg:col-span-8"
      action={
        <Tabs value={range} onValueChange={(value) => setRange(String(value))}>
          <TabsList>
            <TabsTrigger value="7" className="px-2.5 text-xs">
              7 days
            </TabsTrigger>
            <TabsTrigger value="30" className="px-2.5 text-xs">
              30 days
            </TabsTrigger>
          </TabsList>
        </Tabs>
      }
    >
      <ChartContainer config={activityConfig} className="aspect-auto h-64 w-full">
        <AreaChart data={rows} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
          <defs>
            {Object.keys(activityConfig).map((key) => (
              <linearGradient key={key} id={`fill-${key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={`var(--color-${key})`} stopOpacity={0.35} />
                <stop offset="95%" stopColor={`var(--color-${key})`} stopOpacity={0.02} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid vertical={false} />
          <XAxis
            dataKey="day"
            tickLine={false}
            axisLine={false}
            tickMargin={8}
            minTickGap={28}
            tickFormatter={(day: string) => shortDate.format(parseDay(day))}
          />
          <YAxis allowDecimals={false} width={28} tickLine={false} axisLine={false} />
          <ChartTooltip
            cursor={false}
            content={
              <ChartTooltipContent
                indicator="dot"
                labelFormatter={(_, payload) => {
                  const day = payload?.[0]?.payload?.day as string | undefined;
                  return day ? longDate.format(parseDay(day)) : "";
                }}
              />
            }
          />
          {(["resources", "quizzes", "questions"] as const).map((key) => (
            <Area
              key={key}
              dataKey={key}
              type="monotone"
              fill={`url(#fill-${key})`}
              stroke={`var(--color-${key})`}
              strokeWidth={2}
              animationDuration={600}
            />
          ))}
          <ChartLegend content={<ChartLegendContent />} />
        </AreaChart>
      </ChartContainer>
    </Panel>
  );
}

function ResourceMixCard({ data }: { data: Dashboard }) {
  const rows = data.resourceTypes.map((row, i) => ({
    key: row.docType.toLowerCase(),
    type: row.docType,
    count: row.count,
    fill: `var(--color-${row.docType.toLowerCase()})`,
    color: PALETTE[i % PALETTE.length],
  }));
  const config = Object.fromEntries(
    rows.map((row) => [row.key, { label: DOC_TYPE_LABELS[row.type], color: row.color }]),
  ) satisfies ChartConfig;
  const total = rows.reduce((sum, row) => sum + row.count, 0);

  return (
    <Panel title="Resource mix" description="What your chats draw on" className="lg:col-span-4">
      {total === 0 ? (
        <EmptyNote>No resources yet.</EmptyNote>
      ) : (
        <>
          <ChartContainer config={config} className="mx-auto aspect-square h-52">
            <PieChart>
              <ChartTooltip
                cursor={false}
                content={<ChartTooltipContent hideLabel nameKey="key" />}
              />
              <Pie
                data={rows}
                dataKey="count"
                nameKey="key"
                innerRadius={58}
                outerRadius={84}
                strokeWidth={3}
                stroke="var(--color-surface)"
                paddingAngle={2}
              >
                <Label
                  content={({ viewBox }) =>
                    viewBox && "cx" in viewBox && "cy" in viewBox ? (
                      <text x={viewBox.cx} y={viewBox.cy} textAnchor="middle" dominantBaseline="middle">
                        <tspan
                          x={viewBox.cx}
                          y={viewBox.cy}
                          className="fill-foreground text-2xl font-semibold tabular-nums"
                        >
                          {total}
                        </tspan>
                        <tspan
                          x={viewBox.cx}
                          y={(viewBox.cy ?? 0) + 20}
                          className="fill-muted-foreground text-xs"
                        >
                          resources
                        </tspan>
                      </text>
                    ) : null
                  }
                />
              </Pie>
            </PieChart>
          </ChartContainer>
          <ul className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
            {rows.map((row) => (
              <li key={row.key} className="flex items-center gap-2">
                <span className="size-2.5 shrink-0 rounded-sm" style={{ background: row.color }} />
                <span className="truncate text-text-muted">{DOC_TYPE_LABELS[row.type]}</span>
                <span className="ml-auto text-text tabular-nums">{row.count}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </Panel>
  );
}

function QuizTrendCard({ data }: { data: Dashboard }) {
  const rows = data.quizTrend.map((attempt, i) => ({
    index: i + 1,
    percent: attempt.total ? Math.round((attempt.score / attempt.total) * 100) : 0,
    label: `${attempt.score}/${attempt.total}`,
    filename: attempt.filename,
    takenAt: attempt.takenAt,
  }));

  return (
    <Panel
      title="Quiz scores"
      description={rows.length ? `Your last ${rows.length} attempts` : undefined}
      className="lg:col-span-7"
    >
      {rows.length === 0 ? (
        <EmptyNote>
          Open a resource in a chat and choose <span className="font-medium">Quiz</span> to test
          yourself.
        </EmptyNote>
      ) : (
        <ChartContainer config={scoreConfig} className="aspect-auto h-56 w-full">
          <BarChart data={rows} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="index"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              tickFormatter={(i: number) => `#${i}`}
            />
            <YAxis
              domain={[0, 100]}
              ticks={[0, 50, 100]}
              width={36}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: number) => `${v}%`}
            />
            <ChartTooltip
              cursor={false}
              content={
                <ChartTooltipContent
                  hideIndicator
                  labelFormatter={(_, payload) => {
                    const row = payload?.[0]?.payload as (typeof rows)[number] | undefined;
                    return row ? `${row.filename} · ${relativeTime(row.takenAt)}` : "";
                  }}
                  formatter={(_, __, item) => {
                    const row = item.payload as (typeof rows)[number];
                    return (
                      <span className="font-medium tabular-nums">
                        {row.label} correct ({row.percent}%)
                      </span>
                    );
                  }}
                />
              }
            />
            <Bar dataKey="percent" radius={[6, 6, 2, 2]} maxBarSize={44} animationDuration={600}>
              {rows.map((row) => (
                <Cell
                  key={row.index}
                  fill={
                    row.percent >= 80
                      ? "var(--color-success)"
                      : row.percent >= 50
                        ? "var(--color-chart-1)"
                        : "var(--color-warning)"
                  }
                />
              ))}
            </Bar>
          </BarChart>
        </ChartContainer>
      )}
    </Panel>
  );
}

function MostCitedCard({ data }: { data: Dashboard }) {
  const max = Math.max(1, ...data.mostCited.map((r) => r.citations));
  return (
    <Panel
      title="Most cited"
      description="Resources your answers relied on most"
      className="lg:col-span-5"
    >
      {data.mostCited.length === 0 ? (
        <EmptyNote>Citations appear here once you start asking questions.</EmptyNote>
      ) : (
        <ol className="flex flex-col gap-3">
          {data.mostCited.map((resource, i) => (
            <li key={resource.id} className="flex flex-col gap-1.5">
              <div className="flex items-center gap-2 text-sm">
                <span className="w-4 text-xs text-text-subtle tabular-nums">{i + 1}</span>
                <span className="min-w-0 flex-1 truncate text-text" title={resource.filename}>
                  {resource.filename}
                </span>
                <span className="rounded-sm bg-surface-muted px-1.5 py-0.5 text-[11px] text-text-muted">
                  {DOC_TYPE_LABELS[resource.docType]}
                </span>
                <span className="w-8 text-right text-text tabular-nums">{resource.citations}</span>
              </div>
              <div className="ml-6 h-1.5 overflow-hidden rounded-full bg-surface-muted">
                <div
                  className="h-full rounded-full bg-citation transition-[width] duration-500 ease-out"
                  style={{ width: `${(resource.citations / max) * 100}%` }}
                />
              </div>
            </li>
          ))}
        </ol>
      )}
    </Panel>
  );
}

function RecentChatsCard({ data }: { data: Dashboard }) {
  return (
    <Panel title="Recent chats" className="lg:col-span-7">
      {data.recentChats.length === 0 ? (
        <EmptyNote>No chats yet.</EmptyNote>
      ) : (
        <ul className="-mx-2 flex flex-col">
          {data.recentChats.map((chat) => (
            <li key={chat.id}>
              <Link
                href={`/c/${chat.id}`}
                className="group flex items-center gap-3 rounded-md px-2 py-2.5 transition-colors duration-150 ease-out hover:bg-surface-muted"
              >
                <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary-soft text-primary-text">
                  <IconSchool size={16} stroke={1.75} aria-hidden />
                </span>
                <span className="min-w-0 flex-1">
                  <span
                    className="block truncate text-sm font-medium text-text"
                    lang={hasKhmer(chat.title) ? "km" : undefined}
                  >
                    {chat.title}
                  </span>
                  <span className="block text-xs text-text-subtle tabular-nums">
                    {chat.questions} {chat.questions === 1 ? "question" : "questions"} ·{" "}
                    {chat.resources} {chat.resources === 1 ? "resource" : "resources"} ·{" "}
                    {relativeTime(chat.updatedAt)}
                  </span>
                </span>
                <IconArrowRight
                  size={16}
                  className="text-text-subtle transition-transform duration-150 ease-out group-hover:translate-x-0.5"
                  aria-hidden
                />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function ProcessingCard({ data }: { data: Dashboard }) {
  const { totals } = data;
  return (
    <Panel
      title={data.processing.length ? "Processing now" : "Library health"}
      className="lg:col-span-5"
    >
      {data.processing.length ? (
        <ul className="flex flex-col gap-3">
          {data.processing.map((item) => (
            <li key={item.id} className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between gap-3 text-sm">
                <span className="truncate text-text">{item.filename}</span>
                <span className="shrink-0 text-xs text-primary-text tabular-nums">
                  {STAGE_LABELS[item.stage]} · {item.progress}%
                </span>
              </div>
              <div
                role="progressbar"
                aria-valuenow={item.progress}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`${item.filename} processing`}
                className="h-1.5 overflow-hidden rounded-full bg-surface-muted"
              >
                <div
                  className="h-full rounded-full bg-primary transition-[width] duration-500 ease-out"
                  style={{ width: `${item.progress}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <dl className="grid grid-cols-3 gap-3 text-center">
          {[
            { label: "Ready", value: totals.ready, tone: "text-success" },
            { label: "Processing", value: totals.processing, tone: "text-primary-text" },
            { label: "Failed", value: totals.failed, tone: totals.failed ? "text-danger" : "text-text-subtle" },
          ].map((item) => (
            <div key={item.label} className="rounded-md bg-surface-muted px-2 py-3">
              <dt className="micro-label text-text-subtle">{item.label}</dt>
              <dd className={cn("mt-1 text-xl font-semibold tabular-nums", item.tone)}>
                {item.value}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </Panel>
  );
}

function EmptyNote({ children }: { children: React.ReactNode }) {
  return (
    <p className="flex min-h-24 items-center justify-center rounded-md border border-dashed border-border px-4 text-center text-sm text-text-subtle">
      {children}
    </p>
  );
}

function EmptyDashboard({ name }: { name: string }) {
  const steps = [
    { icon: IconBooks, title: "Add a resource", text: "Upload slides, a recording, a link or your notes." },
    { icon: IconMessageQuestion, title: "Ask in English or ខ្មែរ", text: "Type or speak. Every answer cites its source." },
    { icon: IconRosetteDiscountCheck, title: "Quiz yourself", text: "Generate questions from any resource." },
  ];
  return (
    <section className="relative overflow-hidden rounded-xl border border-border bg-surface p-8 text-center shadow-sm">
      <AiOrb className="mx-auto size-36" />
      <h2 lang="km" className="font-display-km mt-4 text-2xl text-text">
        សូមស្វាគមន៍
      </h2>
      <p className="text-base font-semibold text-emphasis">Welcome, {name}</p>
      <p className="mx-auto mt-2 max-w-md text-sm text-text-muted">
        Your dashboard fills in as you study. Start by adding something to learn from.
      </p>
      <div className="mx-auto mt-6 grid max-w-3xl gap-3 sm:grid-cols-3">
        {steps.map((step, i) => (
          <div key={step.title} className="rounded-lg border border-border p-4 text-left">
            <span className="flex size-8 items-center justify-center rounded-md bg-primary-soft text-primary-text">
              <step.icon size={17} stroke={1.75} aria-hidden />
            </span>
            <p className="mt-3 text-sm font-semibold text-text">
              <span className="text-text-subtle tabular-nums">{i + 1}.</span> {step.title}
            </p>
            <p className="mt-1 text-xs text-text-muted">{step.text}</p>
          </div>
        ))}
      </div>
      <Button size="lg" className="mt-6" nativeButton={false} render={<Link href="/" />}>
        <IconPlus size={17} /> Start a chat
      </Button>
      <BorderBeam size={140} duration={10} colorFrom={SPOTLIGHT_FROM} colorTo={SPOTLIGHT_TO} />
    </section>
  );
}

function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-busy aria-label="Loading dashboard">
      <div className="grid gap-4 lg:grid-cols-12">
        <Skeleton className="h-52 rounded-xl lg:col-span-8" />
        <Skeleton className="h-52 rounded-xl lg:col-span-4" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-32 rounded-lg" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-12">
        <Skeleton className="h-80 rounded-lg lg:col-span-8" />
        <Skeleton className="h-80 rounded-lg lg:col-span-4" />
      </div>
    </div>
  );
}
