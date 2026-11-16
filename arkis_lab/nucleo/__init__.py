"""Núcleo de ARKIS AI LAB: reglas de Snake independientes de cualquier modelo."""
from .config import DIFICULTADES, VERSION_MOTOR, Dificultad, obtener_dificultad
from .entorno import ConfigEntorno, Entorno, ResumenEpisodio, Transicion
from .motor import ACCIONES, Accion, EstadoPartida, Partida
from .percepcion import Percepcion, percibir, verificar_sincronia
from .recompensas import ConfigRecompensa

__all__ = [
    "DIFICULTADES", "VERSION_MOTOR", "Dificultad", "obtener_dificultad",
    "ConfigEntorno", "Entorno", "ResumenEpisodio", "Transicion",
    "ACCIONES", "Accion", "EstadoPartida", "Partida",
    "Percepcion", "percibir", "verificar_sincronia", "ConfigRecompensa",
]
