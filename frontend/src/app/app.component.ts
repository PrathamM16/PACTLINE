import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <nav>
      <strong>PACTLINE</strong>
      <a routerLink="/voice" routerLinkActive="active">Voice room</a>
      <a routerLink="/engineering" routerLinkActive="active">Engineering</a>
      <a routerLink="/integrations" routerLinkActive="active">Integrations</a>
    </nav>
    <main><router-outlet /></main>
  `,
})
export class AppComponent {}
