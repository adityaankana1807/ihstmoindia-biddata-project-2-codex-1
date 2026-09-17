import argparse
import os
from ihstmo.server import serve

if __name__=='__main__':
    p=argparse.ArgumentParser(description='I-HSTMO India local research application')
    p.add_argument('--port',type=int,default=int(os.environ.get('PORT','8765')))
    p.add_argument('--no-browser',action='store_true')
    args=p.parse_args()
    serve(args.port,not args.no_browser)
