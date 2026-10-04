import { Component, OnInit, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';

import { ReportsService } from '../reports/reports.service';
import { ScanRow } from '../shared/models';
import { HistoryService } from './history.service';

@Component({
  selector: 'app-history',
  imports: [DatePipe, DecimalPipe],
  templateUrl: './history.html',
  styleUrl: './history.scss',
})
export class History implements OnInit {
  private readonly historyService = inject(HistoryService);
  private readonly reportsService = inject(ReportsService);

  readonly rows = signal<ScanRow[]>([]);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.historyService.list(200).subscribe({
      next: (rows) => {
        this.rows.set(rows);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('No se pudo cargar el historial');
        this.loading.set(false);
      },
    });
  }

  export(): void {
    this.reportsService.downloadScansXlsx();
  }
}
