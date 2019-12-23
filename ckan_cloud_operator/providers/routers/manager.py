from ckan_cloud_operator import logs
from ckan_cloud_operator.config import manager as config_manager
from ckan_cloud_operator.routers import manager as routers_manager
from ckan_cloud_operator.providers.cluster import manager as cluster_manager


def initialize(interactive=False):
    logs.info('env-id is a single character identified of hte environment')
    logs.info('.e.g p for production, s for staging, d for development')
    default_dns_provider = {
        'aws': 'route53',
    }.get(cluster_manager.get_provider_id(), 'cloudflare')
    config_manager.interactive_set(
        {
            'env-id': None,
            'default-root-domain': None,
            'dns-provider': default_dns_provider
        },
        configmap_name='routers-config',
        interactive=interactive
    )
    dns_provider = config_manager.get(key='dns-provider', configmap_name='routers-config')
    logs.info(dns_provider=dns_provider)
    if dns_provider == 'cloudflare':
        if cluster_manager.get_provider_id() == 'kamatera':
            cloudflare_api_key = config_manager.get(
                'CloudflareApiKey',
                secret_name='cco-kamatera-management-server',
                namespace='ckan-cloud-operator',
                required=True
            )
            cloudflare_email = config_manager.get(
                'CloudflareEmail',
                secret_name='cco-kamatera-management-server',
                namespace='ckan-cloud-operator',
                required=True
            )
            config_manager.set(values={
                'cloudflare-email': cloudflare_email,
                'cloudflare-api-key': cloudflare_api_key
            }, secret_name='routers-secrets')
        else:
            config_manager.interactive_set(
                {
                    'cloudflare-email': None,
                    'cloudflare-api-key': None
                },
                secret_name='routers-secrets',
                interactive=interactive
            )
    routers_manager.install_crds()
    infra_router_name = routers_manager.get_default_infra_router_name()
    default_root_domain = config_manager.get('default-root-domain', configmap_name='routers-config', required=True)
    router_type = {
        'kamatera': 'nginx'
    }.get(cluster_manager.get_provider_id(), 'traefik')
    logs.info('Creating infra router', infra_router_name=infra_router_name, default_root_domain=default_root_domain, router_type=router_type)
    if router_type == 'traefik':
        router_spec = routers_manager.get_traefik_router_spec(
            default_root_domain,
            config_manager.get('cloudflare-email', secret_name='routers-secrets', required=False, default=None),
            config_manager.get('cloudflare-api-key', secret_name='routers-secrets', required=False, default=None),
            dns_provider=dns_provider
        )
    else:
        router_spec = routers_manager.get_nginx_router_spec(
            default_root_domain,
            config_manager.get('cloudflare-email', secret_name='routers-secrets', required=False, default=None),
            config_manager.get('cloudflare-api-key', secret_name='routers-secrets', required=False, default=None),
            dns_provider=dns_provider
        )
    routers_manager.create(infra_router_name, router_spec)


def get_env_id():
    return config_get('env-id') or 'p'


def get_default_root_domain():
    return config_get('default-root-domain')


def config_get(key):
    return config_manager.get(key, configmap_name='routers-config')


def get_cloudflare_credentials():
    return (
        config_manager.get('cloudflare-email', configmap_name='routers-config'),
        config_manager.get('cloudflare-api-key', configmap_name='routers-config')
    )


def update_dns_record(dns_provider, sub_domain, root_domain, load_balancer_ip_or_hostname, cloudflare_email=None,
                      cloudflare_auth_key=None):
    logs.info('updating DNS record', dns_provider=dns_provider, sub_domain=sub_domain, root_domain=root_domain,
              load_balancer_ip_or_hostname=load_balancer_ip_or_hostname,
              cloudflare_email=cloudflare_email,
              cloudflare_auth_key_len=len(cloudflare_auth_key) if cloudflare_auth_key else 0)
    if dns_provider == 'cloudflare':
        from ckan_cloud_operator import cloudflare
        cloudflare.update_a_record(cloudflare_email, cloudflare_auth_key, root_domain,
                                   f'{sub_domain}.{root_domain}', load_balancer_ip_or_hostname)
    elif dns_provider == 'route53':
        from ckan_cloud_operator.providers.cluster.aws import manager as aws_manager
        aws_manager.update_dns_record(sub_domain, root_domain, load_balancer_ip_or_hostname)
    else:
        raise NotImplementedError()
