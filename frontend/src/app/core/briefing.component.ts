import { Component, OnDestroy, OnInit, signal } from '@angular/core';
import { api } from './auth';

interface CalendarEvent { id: string; summary: string; start: string; end: string; link: string | null; }
interface Task { id: string; title: string; assignee: string | null; due_date: string | null; }
interface Commitment { id: string; owner: string; description: string; deadline: string | null; confirmation: string; }
interface ShoppingItem { item: string; quantity: string | null; assignee: string | null; }
interface ShoppingList { id: string; name: string; items: ShoppingItem[]; }
interface Reminder { id: string; text: string; remind_at: string; delivery: string; error?: string | null; }
interface Briefing {
  date: string;
  preferences: Record<string, string>;
  calendar: { connected: boolean; events?: CalendarEvent[]; error?: string };
  pending_tasks: Task[];
  pending_commitments: Commitment[];
  deadline_disagreements: Commitment[];
  shopping_lists: ShoppingList[];
  reminders: Reminder[];
  reminder_delivery_configured: boolean;
  follow_ups: { overdue_tasks: Task[]; unassigned_tasks: Task[] };
}

@Component({
  selector: 'app-briefing',
  standalone: true,
  template: `
    <div class="card">
      <h3>Outcome</h3>
      @if (error()) { <p class="error">{{ error() }}</p> }
      @if (notice()) { <p class="ok">{{ notice() }}</p> }
      <button (click)="seed()">Load demo context</button>
      <button (click)="runReminders()">Send due reminders now</button>
      @if (data(); as b) {
        <h4>Preferences</h4>
        @for (entry of preferenceList(b); track entry) { <p>{{ entry }}</p> } @empty { <p class="muted">None saved.</p> }

        <h4>Calendar (today and tomorrow)</h4>
        @if (!b.calendar.connected) { <p class="error">Google Calendar not connected.</p> }
        @if (b.calendar.error) { <p class="error">{{ b.calendar.error }}</p> }
        @for (e of b.calendar.events ?? []; track e.id) {
          <p>{{ e.start }} {{ e.summary }} @if (e.link) { <a [href]="e.link" target="_blank" rel="noopener">open</a> }</p>
        } @empty { @if (b.calendar.connected && !b.calendar.error) { <p class="muted">No events.</p> } }

        <h4>Pending tasks</h4>
        @for (t of b.pending_tasks; track t.id) { <p>{{ t.title }} <span class="muted">{{ t.assignee ?? 'unassigned' }} {{ t.due_date ?? '' }}</span></p> } @empty { <p class="muted">None.</p> }

        <h4>Commitments</h4>
        @for (c of b.pending_commitments; track c.id) { <p>{{ c.owner }}: {{ c.description }} <span class="muted">{{ c.deadline ?? 'no date' }} ({{ c.confirmation }})</span></p> } @empty { <p class="muted">None.</p> }
        @for (c of b.deadline_disagreements; track c.id) { <p class="error">Deadline disagreement: {{ c.description }}</p> }

        <h4>Shopping lists</h4>
        @for (l of b.shopping_lists; track l.id) {
          <p><strong>{{ l.name }}</strong></p>
          @for (i of l.items; track i.item) { <p>{{ i.item }} {{ i.quantity ?? '' }} <span class="muted">{{ i.assignee ?? 'unassigned' }}</span></p> }
        } @empty { <p class="muted">None.</p> }

        <h4>Reminders</h4>
        @if (!b.reminder_delivery_configured) { <p class="error">Email delivery not configured: reminders stay pending.</p> }
        @for (r of b.reminders; track r.id) {
          <p>{{ r.text }} <span class="muted">{{ r.remind_at }}</span> <span [class]="r.delivery === 'sent' ? 'ok' : r.delivery === 'failed' ? 'error' : 'muted'">{{ r.delivery }}</span> @if (r.error) { <span class="error">{{ r.error }}</span> }</p>
        } @empty { <p class="muted">None.</p> }

        <h4>Follow-ups</h4>
        @for (t of b.follow_ups.overdue_tasks; track t.id) { <p class="error">Overdue: {{ t.title }}</p> }
        @for (t of b.follow_ups.unassigned_tasks; track t.id) { <p>Unassigned: {{ t.title }}</p> }
      }
    </div>
  `,
})
export class BriefingComponent implements OnInit, OnDestroy {
  readonly data = signal<Briefing | null>(null);
  readonly error = signal('');
  readonly notice = signal('');
  private timer?: ReturnType<typeof setInterval>;

  ngOnInit(): void {
    void this.refresh();
    this.timer = setInterval(() => void this.refresh(), 3000);
  }

  ngOnDestroy(): void {
    clearInterval(this.timer);
  }

  preferenceList(b: Briefing): string[] {
    return Object.entries(b.preferences).map(([key, value]) => `${key}: ${value}`);
  }

  async refresh(): Promise<void> {
    try {
      this.data.set(await api<Briefing>('/api/briefing'));
      this.error.set('');
    } catch (e) {
      this.error.set(e instanceof Error ? e.message : 'Could not load outcome');
    }
  }

  async seed(): Promise<void> {
    await this.act('/api/demo/seed', 'Demo context loaded.');
  }

  async runReminders(): Promise<void> {
    await this.act('/api/reminders/run', 'Reminder run finished.');
  }

  private async act(path: string, message: string): Promise<void> {
    this.notice.set('');
    try {
      await api(path, { body: {} });
      this.notice.set(message);
      this.error.set('');
    } catch (e) {
      this.error.set(e instanceof Error ? e.message : 'Request failed');
    }
    await this.refresh();
  }
}
