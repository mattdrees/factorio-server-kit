from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ServerState:
    status: str  # "none" | "creating" | "starting" | "running" | "error"
    instance_name: Optional[str] = None
    instance_ip: Optional[str] = None
    zone: Optional[str] = None
    started_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    error_message: Optional[str] = None


# Global state (single server only)
_server_state = ServerState(status="none")


def get_state() -> ServerState:
    return _server_state


def set_creating(started_at: datetime):
    _server_state.status = "creating"
    _server_state.started_at = started_at
    _server_state.instance_name = None
    _server_state.instance_ip = None
    _server_state.error_message = None


def set_starting(instance_name: str, instance_ip: str, zone: str, created_at: datetime):
    _server_state.status = "starting"
    _server_state.instance_name = instance_name
    _server_state.instance_ip = instance_ip
    _server_state.zone = zone
    _server_state.created_at = created_at


def set_running(instance_name: str, instance_ip: str, zone: str, created_at: datetime):
    _server_state.status = "running"
    _server_state.instance_name = instance_name
    _server_state.instance_ip = instance_ip
    _server_state.zone = zone
    _server_state.created_at = created_at


def set_error(error_message: str):
    _server_state.status = "error"
    _server_state.error_message = error_message


def set_none():
    _server_state.status = "none"
    _server_state.instance_name = None
    _server_state.instance_ip = None
    _server_state.zone = None
    _server_state.started_at = None
    _server_state.created_at = None
    _server_state.error_message = None
