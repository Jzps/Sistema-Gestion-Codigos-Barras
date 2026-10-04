"""Errores de dominio.

Los servicios los lanzan sin conocer HTTP; main.py los traduce a respuestas
(404/409) mediante exception handlers. Asi los servicios siguen siendo
independientes de la capa web.
"""


class DomainError(Exception):
    """Error de negocio generico."""


class NotFoundError(DomainError):
    """El recurso no existe o no pertenece al workspace del usuario (404).

    Se usa el mismo error para ambos casos a proposito: no revelar que el
    recurso existe en otro workspace.
    """


class ConflictError(DomainError):
    """Conflicto de estado o de unicidad (409)."""
