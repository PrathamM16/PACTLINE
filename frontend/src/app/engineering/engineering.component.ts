import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { api } from '../core/auth';

interface Preview { valid: boolean; errors: string[]; jenkinsfile?: string; }

@Component({
  selector: 'app-engineering',
  standalone: true,
  imports: [FormsModule],
  template: `
    <h2>Pipeline builder</h2>
    <div class="card stack">
      <input placeholder="job name" [(ngModel)]="jobName">
      <input placeholder="owner/repo" [(ngModel)]="repository">
      <input placeholder="branch" [(ngModel)]="branch">
      <input placeholder="node version" [(ngModel)]="nodeVersion">
      <input placeholder="sonar project key" [(ngModel)]="sonarKey">
      <button (click)="preview()">Generate and validate</button>
    </div>
    @if (result(); as r) {
      @if (!r.valid) { <div class="card error">{{ r.errors.join('; ') }}</div> }
      @if (r.jenkinsfile) { <pre>{{ r.jenkinsfile }}</pre> }
    }
  `,
})
export class EngineeringComponent {
  jobName = '';
  repository = '';
  branch = 'develop';
  nodeVersion = '20';
  sonarKey = '';
  readonly result = signal<Preview | null>(null);

  async preview(): Promise<void> {
    const body = {
      job_name: this.jobName,
      repository: this.repository,
      branch: this.branch,
      node_version: this.nodeVersion,
      stages: ['install', 'lint', 'unit_tests', 'sonar_analysis', 'quality_gate', 'build'],
      sonar_project_key: this.sonarKey || null,
    };
    try {
      this.result.set(await api<Preview>('/api/pipelines/preview', { body }));
    } catch (e) {
      this.result.set({ valid: false, errors: [e instanceof Error ? e.message : 'Backend unreachable'] });
    }
  }
}
