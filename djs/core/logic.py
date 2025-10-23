from djs.core.errors import DomainError

def do_something(x: int, *, mult: int = 2) -> int:
    if mult <= 0:
        raise DomainError("Multiplikator muss > 0 sein.")
    return x * mult
