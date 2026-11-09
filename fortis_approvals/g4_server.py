"""OPTIONAL isolated G4 owner portal candidate. Do not deploy over live G2.

Owner controls the state directory, region/organization and private token file.
This runs the G2 browser UI on a different local port, with Sonar POST blocked.
"""
import os

from .g4_candidate import build_candidate
from .server import OwnerHTTPServer, OwnerRequestHandler
from wsgiref.simple_server import make_server


def config():
    organizations=os.environ.get('FORTIS_G4_ORGANIZATIONS','').split(',')
    return dict(token_file=os.environ.get('FORTIS_G4_TOKEN_FILE',''),
                organizations=organizations,
                region=os.environ.get('FORTIS_G4_REGION','eu'))


def main():
    _, _, _, portal, port=build_candidate(**config())
    print('Isolated read-only G4 ASK candidate ready on loopback-mapped port',port,flush=True)
    with make_server('0.0.0.0',port,portal,
                     server_class=OwnerHTTPServer,
                     handler_class=OwnerRequestHandler) as server:
        server.serve_forever()


if __name__=='__main__':
    main()
