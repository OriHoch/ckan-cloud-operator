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


@kamatera.command()
def print_management_machine_secrets():
    logs.print_yaml_dump(manager.get_management_machine_secrets(), exit_success=True)


@kamatera.command()
@click.argument('SSH_ARGS', nargs=-1)
def ssh_management_machine(ssh_args):
    exitcode = manager.ssh_management_machine(*ssh_args)
    exit(exitcode)


@kamatera.command()
def initialize_docker_registry():
    manager.initialize_docker_registry()
    logs.exit_great_success()
