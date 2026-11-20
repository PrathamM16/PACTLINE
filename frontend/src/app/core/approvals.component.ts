import { Component, OnDestroy, OnInit, signal } from '@angular/core';
import { api } from './auth';

interface Approval {
  id: string;
  summary: string;
  status: string;
}

@Component({
  selector: 'app-approvals',
  standalone: true,
  template: `
    <div class="card">
      <h3>Approvals</h3>
      <p class="muted">Nothing changes until you press Approve.</p>
      @if (error()) { <p class="error">{{ error() }}</p> }
      @for (item of items(); track item.id) {
        <div class="card">
          <p>{{ item.summary }}</p>
          <button (click)="decide(item, true)">Approve</button>
          <button (click)="decide(item, false)">Reject</button>
        </div>
      } @empty {
        <p class="muted">No pending requests.</p>
      }
    </div>
  `,
})
export class ApprovalsComponent implements OnInit, OnDestroy {
  readonly items = signal<Approval[]>([]);
  readonly error = signal('');
  private timer?: ReturnType<typeof setInterval>;

  ngOnInit(): void {
    void this.refresh();
    this.timer = setInterval(() => void this.refresh(), 2000);
  }

  ngOnDestroy(): void {
    clearInterval(this.timer);
  }

  async refresh(): Promise<void> {
    try {
      this.items.set(await api<Approval[]>('/api/approvals'));
      this.error.set('');
    } catch (e) {
      this.error.set(e instanceof Error ? e.message : 'Could not load approvals');
    }
  }

  async decide(item: Approval, approve: boolean): Promise<void> {
    try {
      await api(`/api/approvals/${item.id}/decide`, { body: { approve } });
    } catch (e) {
      this.error.set(e instanceof Error ? e.message : 'Decision failed');
    }
    await this.refresh();
  }
}
