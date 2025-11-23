import logging
import time
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, Tuple, Callable

from .meet_service import MeetService
from .spotify_service import SpotifyService

log = logging.getLogger(__name__)

class Service:
    """Base service - implement real connect/disconnect logic per service.

    connect() / disconnect() must return (bool, message).
    """

    def connect(self) -> Tuple[bool, str]:
        # blocking work; replace with real implementation
        time.sleep(1)
        return True, "Connected (default service)"

    def disconnect(self) -> Tuple[bool, str]:
        time.sleep(0.5)
        return True, "Disconnected (default service)"

class ServiceManager:
    """Run service connect/disconnect logic in background threads."""

    def __init__(self, max_workers: int = 4):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        # register default implementations here
        self._services: Dict[str, Service] = {
            "GMeet": MeetService(),
            "Spotify": SpotifyService(),
            # register other services here as they are implemented
        }

    def register_service(self, name: str, service: Service) -> None:
        """Register or replace a service implementation."""
        self._services[name] = service

    def connect(self, service_name: str) -> Future:
        svc = self._services.get(service_name)
        if not svc:
            fut = Future()
            fut.set_exception(RuntimeError(f"Unknown service: {service_name}"))
            return fut
        # svc.connect must return (bool, message)
        return self._executor.submit(svc.connect)

    def disconnect(self, service_name: str) -> Future:
        svc = self._services.get(service_name)
        if not svc:
            fut = Future()
            fut.set_exception(RuntimeError(f"Unknown service: {service_name}"))
            return fut
        return self._executor.submit(svc.disconnect)

    def list_services(self):
        return list(self._services.keys())