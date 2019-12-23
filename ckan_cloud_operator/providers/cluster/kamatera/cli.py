import click

from ckan_cloud_operator import logs

from . import manager


@click.group()
def kamatera():
    """Manage Kamatera clusters"""
    pass


@kamatera.command()
@click.option('--interactive', is_flag=True)
def create_management_server(interactive):
    manager.create_management_server(interactive)
    logs.exit_great_success()
