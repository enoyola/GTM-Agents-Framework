"""Explicit local environment-file loading; never execute file contents."""
import os
from pathlib import Path

from .store import DomainError

ALLOWED={'OPENAI_API_KEY','GTM_MODEL','GTM_PROVIDER','GTM_MAX_OUTPUT_TOKENS'}


def load_env(path):
    if not path:return
    try:
        file=Path(path)
        if file.stat().st_size>16000:raise DomainError('Environment file is too large.')
        lines=file.read_text().splitlines()
    except (OSError,UnicodeError):
        raise DomainError('Cannot read the specified environment file.') from None
    values={}
    for number,line in enumerate(lines,1):
        line=line.strip()
        if not line or line.startswith('#'):continue
        key,sep,value=line.partition('=')
        key=key.strip();value=value.strip()
        if not sep or key not in ALLOWED:
            raise DomainError(f'Unsupported environment setting on line {number}.')
        if value[:1] in ('"',"'"):
            if len(value)<2 or value[-1]!=value[0]:raise DomainError(f'Invalid quotation on line {number}.')
            value=value[1:-1]
        values[key]=value
    for key,value in values.items():os.environ.setdefault(key,value)
