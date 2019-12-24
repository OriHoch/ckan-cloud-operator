import click

from ckan_cloud_operator import logs

from . import manager


@click.group()
def labels():
    """Manage Labels"""
    pass


@labels.command()
@click.option('--interactive', is_flag=True)
def initialize(interactive):
    manager.initialize(interactive=interactive)
    logs.exit_great_success()
