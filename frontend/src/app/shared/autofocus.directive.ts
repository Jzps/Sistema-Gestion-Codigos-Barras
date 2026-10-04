import { AfterViewInit, Directive, ElementRef, inject } from '@angular/core';

/**
 * Enfoca el elemento al renderizarse. Clave para el flujo de escaneo:
 * el campo de código debe quedar listo para el lector USB sin clics.
 */
@Directive({
  selector: '[appAutofocus]',
})
export class AutofocusDirective implements AfterViewInit {
  private readonly el = inject(ElementRef<HTMLElement>);

  ngAfterViewInit(): void {
    // setTimeout evita conflictos con el ciclo de renderizado inicial.
    setTimeout(() => this.el.nativeElement.focus());
  }
}
