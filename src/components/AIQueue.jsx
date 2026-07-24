/* ============================================================================
   Cola de entrenamiento — administrar las IAs antes de entrenar
   ----------------------------------------------------------------------------
   Selección, orden, renombrado y borrado de especímenes, en el mismo sitio donde
   se lanza el entrenamiento. El orden IMPORTA: es el orden en que se entrenarán,
   una detrás de otra.

   Este componente no guarda estado propio más allá de qué modal está abierto:
   toda la lógica de cola vive en lib/useTrainingQueue.js y las llamadas a la API
   en components/ModelDialogs.jsx. Aquí solo se pinta y se delega.

   DRAG & DROP SIN LIBRERÍA
   ------------------------
   Se usa la API nativa de arrastre del navegador (draggable + dragstart/drop).
   Meter react-dnd o dnd-kit por una lista de diez filas añadiría ~30 KB al bundle
   y una dependencia que mantener, cuando el proyecto entero solo depende de React
   y Tailwind. El arrastre es además un ATAJO, no la única vía: las flechas ↑↓
   hacen exactamente lo mismo y funcionan con teclado, que es lo que necesita
   quien no puede arrastrar (y lo que hace la función accesible de verdad).
   ============================================================================ */

import { useState } from 'react';
import { Title, Hint, Button, IconButton, LevelBadge } from './ui';
import { RenameModelModal, DeleteModelModal } from './ModelDialogs';

function FilaIA({ m, indice, total, turno, bloqueada, onAlternar, onMover,
                 onRenombrar, onBorrar, arrastrando, onArrastre }) {
  const esArrastrada = arrastrando === m.carpeta;

  return (
    <li
      draggable={!bloqueada}
      onDragStart={(e) => {
        // El dataTransfer es obligatorio en Firefox: sin llamarlo, el arrastre
        // no llega a iniciarse.
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', m.carpeta);
        onArrastre.inicio(m.carpeta);
      }}
      onDragOver={(e) => e.preventDefault()}   // Sin esto el navegador no permite soltar
      onDrop={(e) => { e.preventDefault(); onArrastre.soltar(m.carpeta); }}
      onDragEnd={() => onArrastre.fin()}
      className={`flex items-center gap-3 bg-surface2 border rounded-xl px-3 py-2.5
        transition ${esArrastrada ? 'opacity-40 border-accent' : 'border-line'}
        ${bloqueada ? '' : 'cursor-grab active:cursor-grabbing'}`}
    >
      <input
        type="checkbox"
        checked={m.seleccionada}
        disabled={bloqueada}
        onChange={() => onAlternar(m.carpeta)}
        aria-label={`Entrenar ${m.nombre}`}
        className="w-4 h-4 accent-accent shrink-0 disabled:opacity-40"
      />

      {/* El turno solo se muestra en las marcadas: es su puesto en la cola real,
          no su posición en la lista. Ver la fila 5 con un "2" al lado dice
          exactamente lo que va a pasar. */}
      <span className="w-6 shrink-0 text-xs tabular-nums text-center">
        {turno ? <b className="text-accent">{turno}</b> : <span className="text-muted">·</span>}
      </span>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-sm text-ink truncate">{m.nombre}</span>
          <LevelBadge nivel={m.nivel} etiqueta={m.nivel_etiqueta} className="shrink-0" />
        </div>
        <div className="text-xs text-muted truncate">
          {m.generaciones ?? '?'} gen · récord {m.fitness} · tablero {m.grid}×{m.grid}
        </div>
      </div>

      <div className="flex gap-1 shrink-0">
        <IconButton label="Subir" disabled={bloqueada || indice === 0}
                    onClick={() => onMover(m.carpeta, -1)}
                    className="w-8 h-8 disabled:opacity-30 disabled:pointer-events-none">
          ↑
        </IconButton>
        <IconButton label="Bajar" disabled={bloqueada || indice === total - 1}
                    onClick={() => onMover(m.carpeta, 1)}
                    className="w-8 h-8 disabled:opacity-30 disabled:pointer-events-none">
          ↓
        </IconButton>
        <IconButton label="Renombrar" disabled={bloqueada}
                    onClick={() => onRenombrar(m)}
                    className="w-8 h-8 disabled:opacity-30 disabled:pointer-events-none">
          ✎
        </IconButton>
        <IconButton label="Eliminar" disabled={bloqueada}
                    onClick={() => onBorrar(m)}
                    className="w-8 h-8 disabled:opacity-30 disabled:pointer-events-none
                               hover:!bg-danger hover:!border-danger hover:!text-on-danger">
          🗑
        </IconButton>
      </div>
    </li>
  );
}

export default function AIQueue({ cola, bloqueada = false, onCambiado }) {
  const [renombrar, setRenombrar] = useState(null);
  const [borrar, setBorrar] = useState(null);
  const [arrastrando, setArrastrando] = useState(null);

  const { filas, seleccionadas, mover, soltarSobre, alternar,
          marcarTodas, desmarcarTodas, renombrada, olvidar } = cola;

  // Puesto en la cola de cada IA marcada: 1, 2, 3… en el orden en que se ven.
  const turnos = new Map(seleccionadas.map((m, i) => [m.carpeta, i + 1]));

  const onArrastre = {
    inicio: setArrastrando,
    soltar: (destino) => { if (arrastrando) soltarSobre(arrastrando, destino); },
    fin: () => setArrastrando(null),
  };

  if (filas.length === 0) {
    return (
      <div className="border border-dashed border-line rounded-xl py-6 px-4 mb-5
                      text-center text-xs text-muted leading-relaxed">
        Todavía no hay IAs guardadas.<br />
        Escribe un nombre arriba y entrena la primera: aparecerá aquí.
      </div>
    );
  }

  return (
    <div className="mb-5">
      <div className="flex items-end justify-between gap-3 mb-2 flex-wrap">
        <div>
          <Title className="!text-sm">Cola de entrenamiento</Title>
          <Hint className="!text-xs mt-0.5">
            {seleccionadas.length === 0
              ? 'Marca las IAs que quieres entrenar. Se entrenarán de arriba abajo.'
              : `${seleccionadas.length} IA${seleccionadas.length === 1 ? '' : 's'} en cola · arrastra o usa ↑↓ para cambiar el orden.`}
          </Hint>
        </div>
        <div className="flex gap-2">
          <Button onClick={marcarTodas} disabled={bloqueada}
                  className="!px-3 !py-1.5 !text-xs">
            Marcar todas
          </Button>
          <Button onClick={desmarcarTodas}
                  disabled={bloqueada || seleccionadas.length === 0}
                  className="!px-3 !py-1.5 !text-xs">
            Ninguna
          </Button>
        </div>
      </div>

      <ul className="space-y-2 max-h-72 overflow-y-auto pr-1">
        {filas.map((m, i) => (
          <FilaIA
            key={m.carpeta}
            m={m}
            indice={i}
            total={filas.length}
            turno={turnos.get(m.carpeta)}
            bloqueada={bloqueada}
            onAlternar={alternar}
            onMover={mover}
            onRenombrar={setRenombrar}
            onBorrar={setBorrar}
            arrastrando={arrastrando}
            onArrastre={onArrastre}
          />
        ))}
      </ul>

      <RenameModelModal
        model={renombrar}
        onClose={() => setRenombrar(null)}
        onDone={(actualizado, carpetaVieja) => {
          // La carpeta es la identidad en disco y renombrar puede cambiarla: se
          // traslada la referencia para que la IA no pierda su sitio en la cola.
          renombrada(carpetaVieja, actualizado.carpeta);
          onCambiado?.();
        }}
      />
      <DeleteModelModal
        model={borrar}
        onClose={() => setBorrar(null)}
        onDone={(m) => { olvidar(m.carpeta); onCambiado?.(); }}
      />
    </div>
  );
}
