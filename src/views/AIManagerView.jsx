/* ============================================================================
   Gestión de IA — Entrenar / Crear (sub-navegación por pestañas)
   ----------------------------------------------------------------------------
   Envuelve dos experiencias bajo el mismo espacio de "Entrenar IA":

     - «Entrenar IA»: REUTILIZA la TrainView existente tal cual. Es la que entrena
       de verdad (WebSocket /ws/train), con su cola, sus parámetros y su modo
       infinito. No se toca su lógica: solo se monta aquí.
     - «Crear IA»: el formulario de creación con previsualización animada del
       motor (CreateAIPanel). Es una PREVISUALIZACIÓN: no entrena por su cuenta;
       "Crear y entrenar" pasa el nombre y el motor a la pestaña Entrenar, que es
       la que dispara la evolución real.

   Estado separado y explícito: `activeTab` ('train' | 'create') y el motor
   elegido, que se comparte con TrainView a través de la MISMA clave de
   localStorage ('entrenar-engine'), de modo que elegir un motor aquí lo deja ya
   seleccionado al saltar a Entrenar.
   ============================================================================ */

import { useState } from 'react';
import TrainView from './TrainView';
import CreateAIPanel from '../components/AICreatePanel';
import { useLocalState } from '../lib/useLocalState';

const TABS = [
  { id: 'train',  label: 'Entrenar IA' },
  { id: 'create', label: 'Crear IA' },
];

export default function AIManagerView({ theme, config, limits, engines = [],
                                       defaultEngine, models, onSaved }) {
  const [activeTab, setActiveTab] = useState('train');
  // Misma clave que usa TrainView: elegir motor en «Crear» lo deja listo en «Entrenar».
  const [engine, setEngine] = useLocalState('entrenar-engine', defaultEngine || 'intermated');
  // Nombre "en borrador" que Crear entrega a Entrenar al pulsar "Crear y entrenar".
  const [draftName, setDraftName] = useState('');

  /* Handoff Crear -> Entrenar: fija motor y nombre y cambia de pestaña. El
     entrenamiento real lo lanza el usuario ya en TrainView (flujo de siempre). */
  const crearYEntrenar = (nombre, eng) => {
    setEngine(eng);
    setDraftName(nombre);
    setActiveTab('train');
  };

  return (
    <div className="space-y-6">
      <nav className="inline-flex p-1 bg-surface2 border border-line rounded-xl gap-1"
           aria-label="Gestión de IA">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            aria-current={activeTab === t.id ? 'page' : undefined}
            className={`px-5 py-2 rounded-lg text-sm transition
              ${activeTab === t.id
                ? 'bg-accent text-on-accent font-medium'
                : 'text-muted hover:text-ink'}`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {activeTab === 'train' ? (
        <TrainView
          theme={theme}
          config={config}
          limits={limits}
          engines={engines}
          defaultEngine={defaultEngine}
          models={models}
          onSaved={onSaved}
          initialName={draftName}
        />
      ) : (
        <CreateAIPanel
          engines={engines}
          models={models}
          engine={engine}
          setEngine={setEngine}
          onCreate={crearYEntrenar}
        />
      )}
    </div>
  );
}
