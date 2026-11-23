import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { authenticate } from './auth';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule],
  template: `
    <h2>{{ mode() === 'login' ? 'Sign in' : 'Create account' }}</h2>
    <div class="card stack">
      @if (mode() === 'register') { <input placeholder="Your name" [(ngModel)]="name"> }
      <input placeholder="Email" type="email" [(ngModel)]="email" (keyup.enter)="submit()">
      <input placeholder="Password (10+ characters)" type="password" [(ngModel)]="password" (keyup.enter)="submit()">
      @if (error()) { <p class="error">{{ error() }}</p> }
      <button (click)="submit()" [disabled]="busy()">{{ mode() === 'login' ? 'Sign in' : 'Register' }}</button>
      <button (click)="toggle()" class="secondary">{{ mode() === 'login' ? 'Need an account?' : 'Have an account?' }}</button>
    </div>
  `,
})
export class LoginComponent {
  readonly mode = signal<'login' | 'register'>('login');
  readonly error = signal('');
  readonly busy = signal(false);
  email = '';
  password = '';
  name = '';

  constructor(private readonly router: Router) {}

  toggle(): void {
    this.mode.set(this.mode() === 'login' ? 'register' : 'login');
    this.error.set('');
  }

  async submit(): Promise<void> {
    this.busy.set(true);
    this.error.set('');
    try {
      await authenticate(this.mode(), this.email, this.password, this.name);
      await this.router.navigateByUrl('/voice');
    } catch (e) {
      this.error.set(e instanceof Error ? e.message : 'Sign-in failed');
    } finally {
      this.busy.set(false);
    }
  }
}
