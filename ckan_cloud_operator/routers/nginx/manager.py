from ckan_cloud_operator import kubectl
from ckan_cloud_operator import logs
from ckan_cloud_operator.routers.annotations import CkanRoutersAnnotations
from ckan_cloud_operator.infra import CkanInfra
from ckan_cloud_operator.routers.nginx import deployment as nginx_deployment


def create(router):
    router_name = router['metadata']['name']
    router_spec = router['spec']
    cloudflare_spec = router_spec.get('cloudflare', {})
    cloudflare_email = cloudflare_spec.get('email')
    cloudflare_api_key = cloudflare_spec.get('api-key')
    default_root_domain = router_spec.get('default-root-domain')
    dns_provider = router_spec.get('dns-provider')
    assert dns_provider == 'cloudflare'
    router_spec['dns-provider'] = dns_provider
    assert all([default_root_domain, dns_provider]), f'invalid nginx router spec: {router_spec}'
    assert cloudflare_email and cloudflare_api_key, 'invalid nginx router spec, missing cloudflare email or api key'
    # cloudflare credentials are stored in a secret, not in the spec
    if 'cloudflare' in router_spec:
        del router_spec['cloudflare']
    kubectl.apply(router)
    annotations = CkanRoutersAnnotations(router_name, router)
    annotations.update_flag('letsencryptCloudflareEnabled', lambda: annotations.set_secrets({
        'LETSENCRYPT_CLOUDFLARE_EMAIL': cloudflare_email,
        'LETSENCRYPT_CLOUDFLARE_API_KEY': cloudflare_api_key
    }), force_update=True)
    return router


def delete(router_name):
    print(f'Deleting nginx router {router_name}')
    if all([
        kubectl.call(f'delete --ignore-not-found -l ckan-cloud/router-name={router_name} secret') == 0,
        kubectl.call(f'delete --ignore-not-found -l ckan-cloud/router-name={router_name} configmap') == 0,
        kubectl.call(f'delete --ignore-not-found -l ckan-cloud/router-name={router_name} CkanCloudRoute') == 0,
        kubectl.call(f'delete --ignore-not-found CkanCloudRouter {router_name}') == 0,
    ]):
        print('Removing finalizers')
        success = True
        routes = kubectl.get_items_by_labels('CkanCloudRoute', {'ckan-cloud/router-name': router_name}, required=False)
        if not routes: routes = []
        for route in routes:
            route_name = route['metadata']['name']
            if kubectl.call(
                    f'patch CkanCloudRoute {route_name} -p \'{{"metadata":{{"finalizers":[]}}}}\' --type=merge',
            ) != 0:
                success = False
        if kubectl.get(f'CkanCloudRouter {router_name}', required=False):
            if kubectl.call(
                    f'patch CkanCloudRouter {router_name} -p \'{{"metadata":{{"finalizers":[]}}}}\' --type=merge',
            ) != 0:
                success = False
        assert success
    else:
        raise Exception('Deletion failed')


def get_dns_data(router_name, router, failfast=False):
    return nginx_deployment.get_dns_data(router_name, router, failfast=failfast)


def get(router_name, attr='deployment', router=None, failfast=False):
    deployment_data = lambda: nginx_deployment.get(router_name)
    dns_data = lambda: get_dns_data(router_name, router, failfast=failfast)
    if attr == 'deployment':
        return deployment_data()
    elif attr == 'dns':
        return dns_data()
    else:
        return {'deployment': deployment_data(), 'dns': dns_data()}


def update(router_name, wait_ready, spec, annotations, routes, dry_run=False):
    logs.debug(f'updating nginx router: {router_name}')
    logs.debug_verbose(router_name=router_name, spec=spec, routes=routes)
    return nginx_deployment.update(router_name, wait_ready, spec, annotations, routes, dry_run=dry_run)


def _init_router(router_name):
    router = kubectl.get(f'CkanCloudRouter {router_name}')
    assert router['spec']['type'] == 'nginx'
    annotations = CkanRoutersAnnotations(router_name, router)
    ckan_infra = CkanInfra()
    return router, annotations, ckan_infra
