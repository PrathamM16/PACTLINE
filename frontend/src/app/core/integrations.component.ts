import { Component, OnInit, signal } from '@angular/core';
import { KeyValuePipe } from '@angular/common';
import { api } from './auth';

interface ServiceState { configured: boolean; verified_live: boolean; }

@Component({
  selector: 'app-integrations',
  standalone: true,
  imports: [KeyValuePipe],
  template: `
    <h2>Integrations</h2>
    <p class="muted">"Configured" means the required environment variables are present. It does not mean the provider was contacted.</p>
    @if (error()) { <p class="error">{{ error() }}</p> }
    @for (entry of services() | keyvalue; track entry.key) {
      <div class="card">
        <strong>{{ entry.key }}</strong>
        <span class="badge" [class.live]="entry.value.configured" [class.bad]="!entry.value.configured" style="margin-left: 8px">{{ entry.value.configured ? 'configured' : 'not configured' }}</span>
      </div>
    }
  `,
})
export class IntegrationsComponent implements OnInit {
  readonly services = signal<Record<string, ServiceState>>({});
  readonly error = signal('');

  async ngOnInit(): Promise<void> {
    try {
      this.services.set(await api<Record<string, ServiceState>>('/api/integrations/status'));
    } catch (e) {
      this.error.set(e instanceof Error ? e.message : 'Backend unreachable');
    }
  }
}
