import click
from djs.core.logic import do_something

@click.command()
@click.argument("value", type=int)
@click.option("--mult", type=int, default=2, show_default=True, help="Multiplikator")
@click.pass_context
def foo(ctx, value: int, mult: int):
    """Beispiel-Unterbefehl: multipliziert VALUE mit --mult."""
    log = ctx.obj["logger"]
    cfg = ctx.obj["config"]
    if value > cfg.limit:
        log.warning(f"Wert {value} überschreitet limit={cfg.limit}")
    result = do_something(value, mult=mult)
    click.echo(f"Ergebnis: {result}")
