"""Estado explícito compartido por los constructores de la interfaz.

La aplicación conserva sus servicios y su conexión en ``main.py``. Este
objeto evita que los módulos de UI tengan que importar ``main`` (y, por lo
tanto, evita ciclos de importación y globals de widgets).
"""

from dataclasses import dataclass, field
from typing import Any, Callable


def dimensionar_ventana(ventana: Any, screen_w: int, screen_h: int,
                        ancho_relativo: float, alto_relativo: float) -> None:
    """Dimensiona y centra una ventana según la pantalla actual.

    Las proporciones hacen que el tamaño inicial se adapte a cada equipo sin
    imponer topes absolutos en píxeles.
    """
    ancho = int(screen_w * ancho_relativo)
    alto = int(screen_h * alto_relativo)
    x = (screen_w - ancho) // 2
    y = (screen_h - alto) // 2
    ventana.geometry(f"{ancho}x{alto}+{x}+{y}")
    ventana.resizable(True, True)


@dataclass
class UIContext:
    app: Any
    conexion: Any
    cursor: Any
    db_lock: Any
    screen_w: int
    screen_h: int
    base_font: int
    heading_font: int
    rowheight: int
    usuario: str
    rol: str
    carrito: list = field(default_factory=list)
    tema_oscuro: bool = False
    widgets: dict = field(default_factory=dict)
    callbacks: dict = field(default_factory=dict)

    def callback(self, nombre: str) -> Callable:
        return self.callbacks[nombre]

    def __getattr__(self, nombre: str) -> Any:
        """Permite acceder a servicios registrados sin duplicarlos en UI."""
        callbacks = self.__dict__.get("callbacks", {})
        if nombre in callbacks:
            return callbacks[nombre]
        raise AttributeError(nombre)

    def widget(self, nombre: str) -> Any:
        return self.widgets[nombre]
