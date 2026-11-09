"""Gunicorn entry point. Exactly one worker preserves actor-owned view sessions."""
from importlib.machinery import SourceFileLoader
from pathlib import Path

host = SourceFileLoader('rdg_server_host', str(Path(__file__).with_name('rdg-server.py'))).load_module()
application = host.from_environment()
