"""Prueba de humo: el paquete se importa sin torch y los puertos existen."""
import clasificacion_funcion
from clasificacion_funcion import puertos


def test_paquete_importa():
    assert clasificacion_funcion.__doc__


def test_puertos_declarados():
    for nombre in ("Tokenizador", "Recuperador", "Entrenador", "Predictor", "Reloj"):
        assert hasattr(puertos, nombre)


def test_torch_no_se_importa_al_cargar_el_paquete():
    # El grupo `modelo` es opt-in: importar el paquete no debe requerir torch.
    assert "torch" not in vars(clasificacion_funcion)
    assert "torch" not in vars(puertos)

