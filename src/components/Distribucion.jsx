import { Panel } from './ui';

/* Distribución común de los paneles de entrenamiento: visor en vivo + controles del
   modelo arriba (lado a lado en pantallas anchas, apilados en las estrechas) y la
   información detallada debajo. */
export function Distribucion({ visor, controles, children, titulo = 'Entrenamiento en vivo', accion }) {
  return (
    <div className="space-y-4 min-w-0">
      <div className="grid gap-4 grid-cols-[minmax(0,1fr)] xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)] items-start">
        <Panel titulo={titulo} accion={accion}>{visor}</Panel>
        <div className="space-y-4 min-w-0">{controles}</div>
      </div>
      {children}
    </div>
  );
}
