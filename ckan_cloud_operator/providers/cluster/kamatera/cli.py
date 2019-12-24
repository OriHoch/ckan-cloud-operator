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
@click.option('--key')
def print_management_machine_secrets(key):
    if key:
        print(manager.get_management_machine_secrets(key))
    else:
        logs.print_yaml_dump(manager.get_management_machine_secrets(), exit_success=True)


@kamatera.command()
@click.argument('SSH_ARGS', nargs=-1)
def ssh_management_machine(ssh_args):
    exitcode = manager.ssh_management_machine(*ssh_args)
    exit(exitcode)


@kamatera.command()
@click.argument('local-file')
@click.argument('remote-file')
def scp_to_management_machine(local_file, remote_file):
    with open(local_file) as f:
        manager.ssh_management_machine(f.read(), scp_to_remote_file=remote_file)


@kamatera.command()
def initialize_docker_registry():
    manager.initialize_docker_registry()
    logs.exit_great_success()


@kamatera.command()
@click.argument('RANCHER_ARGS', nargs=-1)
@click.option('--context', default='Default')
def rancher(rancher_args, context):
    manager.rancher(*rancher_args, context=context)


@kamatera.command()
@click.argument('SSH_ARGS', nargs=-1)
def ssh_rancher_nodes(ssh_args):
    manager.ssh_rancher_nodes(ssh_args)
