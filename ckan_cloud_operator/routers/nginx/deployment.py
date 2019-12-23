from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs
from ckan_cloud_operator.routers.nginx import config as nginx_router_config
from ckan_cloud_operator.routers.routes import manager as routes_manager
from ckan_cloud_operator.labels import manager as labels_manager
from ckan_cloud_operator.config import manager as config_manager


def _get_resource_name(router_name):
    return f'router-nginx-{router_name}'


def _update(router_name, spec, annotations, routes):
    dns_provider = spec.get('dns-provider')
    assert dns_provider == 'cloudflare'
    resource_name = _get_resource_name(router_name)
    router_type = spec['type']
    cloudflare_email, cloudflare_auth_key = get_cloudflare_credentials()
    logs.info('updating nginx deployment', resource_name=resource_name, router_type=router_type,
              cloudflare_email=cloudflare_email, cloudflare_auth_key_len=len(cloudflare_auth_key) if cloudflare_auth_key else 0,
              dns_provider=dns_provider)
    nginx_config = nginx_router_config.get(
        routes, cloudflare_email,
        enable_access_log=bool(spec.get('enable-access-log')),
        wildcard_ssl_domain=spec.get('wildcard-ssl-domain'),
        external_domains=None,
        dns_provider=dns_provider,
        force=True
    )
    kubectl.apply(kubectl.get_configmap(
        resource_name, get_labels(router_name, router_type),
        {'nginx_config': nginx_config}
    ))
    domains = {}
    for route in routes:
        root_domain, sub_domain = routes_manager.get_domain_parts(route)
        domains.setdefault(root_domain, []).append(sub_domain)
        routes_manager.pre_deployment_hook(route, get_labels(router_name, router_type))
    load_balancer_ip = get_load_balancer_ip(router_name)
    print(f'load balancer ip: {load_balancer_ip}')
    from ckan_cloud_operator.providers.routers import manager as routers_manager
    for root_domain, sub_domains in domains.items():
        for sub_domain in sub_domains:
            routers_manager.update_dns_record(
                dns_provider, sub_domain, root_domain,
                load_balancer_ip, cloudflare_email, cloudflare_auth_key
            )


def get_load_balancer_ip(router_name, failfast=False):
    load_balancer_ip = config_manager.get(
        'load-balancer-ip',
        configmap_name=f'nginx-router-{router_name}-deployment',
        required=False,
        default=None
    )
    if not load_balancer_ip:
        load_balancer_ip = config_manager.get(
            'server_public_ip',
            secret_name='cco-kamatera-management-server',
            namespace='ckan-cloud-operator',
            required=True
        )
        config_manager.set('load-balancer-ip', load_balancer_ip, configmap_name=f'nginx-router-{router_name}-deployment')
    return load_balancer_ip


def get_cloudflare_credentials():
    from ckan_cloud_operator.providers.routers import manager as routers_manager
    cloudflare_email, cloudflare_auth_key = routers_manager.get_cloudflare_credentials()
    return cloudflare_email, cloudflare_auth_key


def update(router_name, wait_ready, spec, annotations, routes, dry_run=False):
    raise NotImplementedError()


def get(router_name):
    return {'ready': False}


def get_dns_data(router_name, router, failfast=False):
    return {
        'load-balancer-ip': get_load_balancer_ip(router_name, failfast=failfast),
    }


def get_label_suffixes(router_name, router_type):
    return {
        'router-name': router_name,
        'router-type': router_type
    }


def get_labels(router_name, router_type, for_deployment=False):
    label_prefix = labels_manager.get_label_prefix()
    extra_labels = {'app': f'{label_prefix}-router-{router_name}'} if for_deployment else {}
    return labels_manager.get_resource_labels(
        get_label_suffixes(router_name, router_type),
        extra_labels=extra_labels
    )
