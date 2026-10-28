from typing import Optional, List

CLIENT = "CLIENT"
EMPLOYEE = "EMPLOYEE"
MANAGER = "MANAGER"
ADMIN = "ADMIN"
ALL_ROLES = [CLIENT, EMPLOYEE, MANAGER, ADMIN]


class RouteRule:
    def __init__(self, method: str, template: str, service: str, roles: Optional[List[str]], scope_to_client: bool = False):
        self.method = method
        self.template = template
        self.service = service
        self.roles = roles
        self.scope_to_client = scope_to_client

    def matches_path(self, path: str) -> bool:
        path_parts = path.strip("/").split("/")
        template_parts = self.template.strip("/").split("/")
        if len(path_parts) != len(template_parts):
            return False
        for path_part, template_part in zip(path_parts, template_parts):
            if template_part.startswith("{"):
                continue
            if path_part != template_part:
                return False
        return True


ROUTES = [
    RouteRule("POST", "/api/v1/auth/register", "users-service", None),
    RouteRule("POST", "/api/v1/auth/login", "users-service", None),
    RouteRule("GET", "/api/v1/users/{id}", "users-service", [EMPLOYEE, MANAGER]),

    RouteRule("GET", "/api/v1/products", "catalog-service", ALL_ROLES),
    RouteRule("GET", "/api/v1/products/{id}", "catalog-service", ALL_ROLES),
    RouteRule("POST", "/api/v1/purchases", "catalog-service", [CLIENT]),
    RouteRule("GET", "/api/v1/purchases", "catalog-service", [CLIENT]),
    RouteRule("GET", "/api/v1/purchases/{id}", "catalog-service", [CLIENT, EMPLOYEE]),

    RouteRule("GET", "/api/v1/requests/statuses", "request-service", [EMPLOYEE, MANAGER]),
    RouteRule("POST", "/api/v1/requests", "request-service", [CLIENT]),
    RouteRule("GET", "/api/v1/requests", "request-service", [CLIENT, EMPLOYEE, MANAGER], scope_to_client=True),
    RouteRule("GET", "/api/v1/requests/{id}", "request-service", [CLIENT, EMPLOYEE, MANAGER]),
    RouteRule("POST", "/api/v1/requests/{id}/assign", "request-service", [EMPLOYEE]),
    RouteRule("POST", "/api/v1/requests/{id}/status", "request-service", [EMPLOYEE]),

    RouteRule("GET", "/api/v1/cells", "locker-service", [EMPLOYEE]),
    RouteRule("POST", "/api/v1/cells", "locker-service", [ADMIN]),

    RouteRule("GET", "/api/v1/stats/requests", "stats-service", [MANAGER]),
    RouteRule("GET", "/api/v1/stats/employees", "stats-service", [MANAGER]),
    RouteRule("GET", "/api/v1/stats/products", "stats-service", [MANAGER]),
]


def find_route(method: str, path: str):
    path_found = False
    for rule in ROUTES:
        if rule.matches_path(path):
            path_found = True
            if rule.method == method:
                return rule, path_found
    return None, path_found
