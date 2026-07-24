/* ============================================================================
   Diálogos de un espécimen: renombrar y borrar
   ----------------------------------------------------------------------------
   Estaban dentro de HistoryView. Se extraen aquí porque la nueva cola de
   entrenamiento necesita exactamente lo mismo, y tener dos copias del mismo
   modal (con sus mismos textos, su mismo manejo de errores y su misma llamada a
   la API) es la forma más segura de que dentro de un mes solo se arregle una.

   Se abren pasándoles un `model`; con `model` a null no pintan nada. Cada uno
   habla con la API por su cuenta y avisa por `onDone`, así quien los usa no
   tiene que llevar estado de formularios.
   ============================================================================ */

import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { Modal, Button, Hint } from './ui';

/* Renombra sin perder el entrenamiento. El servidor mueve la carpeta si el slug
   cambia y responde 409 si el nombre ya pertenece a otro linaje; ese error se
   muestra tal cual llega, que es más útil que un mensaje genérico.

   `onDone(modeloActualizado, carpetaAnterior)` recibe la carpeta vieja además de
   la nueva: renombrar puede cambiar el slug, y quien mantenga referencias por
   carpeta (la cola) necesita saber cuál sustituir. */
export function RenameModelModal({ model, onClose, onDone }) {
  const [nombre, setNombre] = useState('');
  const [error, setError] = useState(null);
  const [guardando, setGuardando] = useState(false);

  // Cada apertura parte del nombre actual y sin errores heredados de la anterior.
  useEffect(() => {
    if (model) { setNombre(model.nombre); setError(null); setGuardando(false); }
  }, [model]);

  if (!model) return null;

  const confirmar = async () => {
    const limpio = nombre.trim();
    if (!limpio) { setError('Escribe un nombre.'); return; }
    if (limpio === model.nombre) { onClose(); return; }
    setGuardando(true);
    try {
      const { model: actualizado } = await api.renameModel(model.carpeta, limpio);
      onDone?.(actualizado, model.carpeta);
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Renombrar IA">
      <Hint className="mb-4">
        Cambia el nombre de <b className="text-ink">{model.nombre}</b> sin
        perder su entrenamiento: conserva sus generaciones, su récord y su nivel.
      </Hint>
      <input
        type="text"
        value={nombre}
        autoFocus
        maxLength={40}
        onChange={(e) => { setNombre(e.target.value); setError(null); }}
        onKeyDown={(e) => { if (e.key === 'Enter') confirmar(); }}
        className="w-full bg-surface2 border border-line rounded-xl px-4 py-2.5
                   text-ink placeholder:text-muted focus:outline-2
                   focus:outline-offset-2 focus:outline-accent"
      />
      {error && <p className="text-xs text-danger mt-2">{error}</p>}
      <div className="flex justify-end gap-2 mt-5">
        <Button onClick={onClose}>Cancelar</Button>
        <Button variant="primary" onClick={confirmar} disabled={guardando}>
          {guardando ? 'Guardando…' : 'Guardar nombre'}
        </Button>
      </div>
    </Modal>
  );
}

/* Borra la carpeta entera del espécimen. `onDone(model)` se llama con el modelo
   ya borrado para que quien lo tuviera referenciado lo suelte. */
export function DeleteModelModal({ model, onClose, onDone }) {
  const [borrando, setBorrando] = useState(false);

  useEffect(() => { if (model) setBorrando(false); }, [model]);

  if (!model) return null;

  const confirmar = async () => {
    setBorrando(true);
    try {
      await api.deleteModel(model.carpeta);
      onDone?.(model);
      onClose();
    } finally {
      setBorrando(false);
    }
  };

  return (
    <Modal open onClose={onClose} danger title="¿Borrar este espécimen?">
      <Hint className="mb-5">
        Se eliminará la carpeta <code className="text-ink">historial/{model.carpeta}/</code>
        {' '}entera, con su red neuronal y su histórico. No se puede deshacer.
      </Hint>
      <div className="flex justify-end gap-2">
        <Button onClick={onClose}>Cancelar</Button>
        <Button variant="danger" onClick={confirmar} disabled={borrando}>
          {borrando ? 'Borrando…' : 'Sí, borrar'}
        </Button>
      </div>
    </Modal>
  );
}
