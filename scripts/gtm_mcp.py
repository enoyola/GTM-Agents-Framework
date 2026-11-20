#!/usr/bin/env python3
"""Absolute-path stdio entry point; independent of the calling working directory."""
import argparse
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from gtm_agents.mcp_server import create_server

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--db',type=Path,default=ROOT/'data/gtm.sqlite3')
    args=parser.parse_args()
    create_server(args.db.resolve()).run(transport='stdio')
