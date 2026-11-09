"""Gunicorn entry point for the private gateway."""
from importlib.machinery import SourceFileLoader
from pathlib import Path

gateway = SourceFileLoader('rdg_private_gateway', str(Path(__file__).with_name('rdg-gateway.py'))).load_module()
application = gateway.from_environment()
