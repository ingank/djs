import click

@click.command()
@click.option("--name", default="Welt", show_default=True)
@click.pass_context
def bar(ctx, name: str):
    """Sagt hallo (ohne Farben)."""
    log = ctx.obj["logger"]
    log.info(f"bar aufgerufen mit name={name}")
    click.echo(f"Hallo, {name}!")
