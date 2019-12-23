import traceback

from ckan_cloud_operator import logs

import ckan_cloud_operator.routers.routes.manager as routes_manager


def _add_route(config, domains, route, enable_ssl_redirect):
    route_name = routes_manager.get_name(route)
    logs.info(f'adding route to nginx config: {route_name}')
    logs.debug_verbose(config=config, domains=domains, route=route, enable_ssl_redirect=enable_ssl_redirect)
    backend_url = routes_manager.get_backend_url(route)
    frontend_hostname = routes_manager.get_frontend_hostname(route)
    print(f'F/B = {frontend_hostname} {backend_url}')
    root_domain, sub_domain = routes_manager.get_domain_parts(route)
    domains.setdefault(root_domain, []).append(sub_domain)
    # if route['spec'].get('extra-no-dns-subdomains'):
    #     extra_hostnames = ',' + ','.join([f'{s}.{root_domain}' for s in route['spec']['extra-no-dns-subdomains']])
    # else:
    extra_hostnames = ''
    logs.debug_verbose(route_name=route_name, backend_url=backend_url, frontend_hostname=frontend_hostname, root_domain=root_domain,
                       sub_domain=sub_domain, domains=domains, extra_hostnames=extra_hostnames)
    if backend_url:
        raise NotImplementedError()


def get(routes, letsencrypt_cloudflare_email, enable_access_log=False, wildcard_ssl_domain=None, external_domains=False, dns_provider=None, force=False):
    assert dns_provider == 'cloudflare'
    logs.info('Generating nginx configuration', routes_len=len(routes) if routes else 0,
              letsencrypt_cloudflare_email=letsencrypt_cloudflare_email, enable_access_log=enable_access_log,
              wildcard_ssl_domain=wildcard_ssl_domain, external_domains=external_domains)
    config = {}
    domains = {}
    enable_ssl_redirect = True
    logs.info('Adding routes')
    i = 0
    errors = 0
    for route in routes:
        try:
            _add_route(config, domains, route, enable_ssl_redirect)
            i += 1
        except Exception as e:
            if force:
                logs.error(traceback.format_exc())
                logs.error(str(e))
                errors += 1
            else:
                raise
    logs.info(f'Added {i} routes')
    if errors > 0:
        logs.warning(f'Encountered {errors} errors')
    return config
