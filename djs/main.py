import click
from djs.cli.foo import foo
from djs.cli.bar import bar
from djs.utils.logging import setup_logging
from djs.config.loader import load_config

@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-v", "--verbose", count=True, help="-v / -vv / -vvv: mehr Details")
@click.option("-q", "--quiet", count=True, help="-q / -qq: weniger Ausgaben")
@click.option("--config", type=click.Path(exists=True, dir_okay=False), help="Pfad zu TOML-Konfig")
@click.option("--log-file", type=click.Path(dir_okay=False), help="Schreibe Logs zusätzlich in Datei")
@click.pass_context
def djs(ctx, verbose, quiet, config, log_file):
    """DJ-Suite (minimal): Hauptbefehl 'djs'."""
    ctx.ensure_object(dict)
    ctx.obj["logger"] = setup_logging(verbose=verbose, quiet=quiet, log_file=log_file)
    ctx.obj["config"] = load_config(config)

djs.add_command(foo)
djs.add_command(bar)

if __name__ == "__main__":
    djs()
