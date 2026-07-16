/* ============================================================================
   Configuracion
   ----------------------------------------------------------------------------
   Tema, generaciones (1-100) y tamano del tablero. Todo se guarda en el
   servidor (config.json) y se aplica al instante.
   ============================================================================ */

import { Panel, Title, Hint, Field, Segmented } from '../components/ui';

/* Las miniaturas llevan colores FIJOS a proposito: muestran como se ve cada
   tema, asi que no deben seguir al tema activo. */
const TEMAS = [
  {
    id: 'oscura',
    nombre: 'Oscura',
    desc: 'Sobria y de bajo contraste. La de por defecto.',
    colores: ['#0e0e12', '#5ad19a', '#6e8bff'],
  },
  {
    id: 'minimalista',
    nombre: 'Minimalista',
    desc: 'Clara y limpia, con mucho aire.',
    colores: ['#fbfbfd', '#34c759', '#0071e3'],
  },
  {
    id: 'verde',
    nombre: 'Verde',
    desc: 'Monocromo de fósforo, estilo terminal.',
    colores: ['#071108', '#4ad64a', '#5ce65c'],
  },
];

export default function ConfigView({ config, limits, grids, onChange }) {
  return (
    <div className="space-y-5 max-w-3xl">
      <Title>Configuración</Title>

      <Panel>
        <h3 className="font-medium text-ink mb-1">Estilo</h3>
        <Hint className="mb-5">Se guarda en el servidor y se aplica al instante.</Hint>

        <div className="grid gap-3 sm:grid-cols-3">
          {TEMAS.map((t) => (
            <button
              key={t.id}
              onClick={() => onChange({ theme: t.id })}
              className={`text-left p-4 rounded-panel border-2 transition
                hover:-translate-y-0.5
                ${config.theme === t.id ? 'border-accent' : 'border-line'}`}
            >
              <div className="flex gap-1.5 mb-3">
                {t.colores.map((c) => (
                  <span key={c} className="w-6 h-6 rounded-md border border-black/10"
                        style={{ background: c }} />
                ))}
              </div>
              <div className="font-medium text-ink text-sm">{t.nombre}</div>
              <div className="text-xs text-muted mt-1 leading-relaxed">{t.desc}</div>
            </button>
          ))}
        </div>
      </Panel>

      <Panel>
        <h3 className="font-medium text-ink mb-1">Generaciones por entrenamiento</h3>
        <Hint className="mb-5">
          Cuántas veces se reproduce la población. Más generaciones = IA más lista,
          pero el entrenamiento tarda más.
        </Hint>

        <Field
          label={`${config.generations} ${config.generations === 1 ? 'generación' : 'generaciones'}`}
          help={`Entre ${limits.min_generations} y ${limits.max_generations}.`}
        >
          <div className="flex items-center gap-4">
            <input
              type="range"
              min={limits.min_generations}
              max={limits.max_generations}
              value={config.generations}
              onChange={(e) => onChange({ generations: Number(e.target.value) })}
              className="flex-1 accent-accent"
            />
            <input
              type="number"
              min={limits.min_generations}
              max={limits.max_generations}
              value={config.generations}
              onChange={(e) => onChange({ generations: Number(e.target.value) })}
              className="w-20 bg-surface2 border border-line rounded-xl px-3 py-2
                         text-ink text-center tabular-nums focus:outline-2
                         focus:outline-offset-2 focus:outline-accent"
            />
          </div>
        </Field>
      </Panel>

      <Panel>
        <h3 className="font-medium text-ink mb-1">Dimensiones del tablero</h3>
        <Hint className="mb-5">
          Afecta al juego manual y a los entrenamientos nuevos. Los sensores de la
          red están normalizados, así que una IA entrenada en 8×8 también sabe
          jugar en 15×15 (aunque lo hará peor: nunca vio tanto espacio).
        </Hint>

        <Segmented
          value={config.grid}
          onChange={(g) => onChange({ grid: g })}
          options={grids.map((g) => ({ value: g, label: `${g}×${g}` }))}
        />
      </Panel>
    </div>
  );
}
