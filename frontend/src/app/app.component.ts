import { Component } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { currentUserName, isLoggedIn, logout } from './core/auth';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <nav>
      <strong class="brand">PACTLINE</strong>
      @if (loggedIn()) {
        <a routerLink="/voice" routerLinkActive="active">Voice room</a>
        <a routerLink="/engineering" routerLinkActive="active">Engineering</a>
        <a routerLink="/integrations" routerLinkActive="active">Integrations</a>
        <span class="spacer"></span>
        <span class="muted">{{ userName() }}</span>
        <button class="secondary" (click)="signOut()">Sign out</button>
      }
    </nav>
    <main><router-outlet /></main>
  `,
})
export class AppComponent {
  constructor(private readonly router: Router) {}

  loggedIn(): boolean {
    return isLoggedIn();
  }

  userName(): string {
    return currentUserName();
  }

  async signOut(): Promise<void> {
    logout();
    await this.router.navigateByUrl('/login');
  }
}
