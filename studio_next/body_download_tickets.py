"""Single-use, short-lived, capability-scoped browser media delivery tickets.

The long-lived BODY API token is NEVER placed into a URL, cookie, HTML or
browser storage. A ticket may download only one previously authorized,
registered immutable media artifact. The ticket is useless after consumption,
expiry, service restart, or an underlying hash mismatch.
"""
from __future__ import annotations

import hashlib
import re
import secrets
import threading
import time

_TICKET = re.compile(r"^[A-Za-z0-9_-]{43}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class DownloadTickets:
    def __init__(self, *, ttl=45, max_outstanding=256, clock=None):
        if not isinstance(ttl,(int,float)) or not 0<ttl<=300:
            raise ValueError("Invalid finite browser delivery ticket lifetime")
        if type(max_outstanding) is not int or not 1<=max_outstanding<=4096:
            raise ValueError("Invalid bounded outstanding ticket count")
        self._ttl=float(ttl)
        self._max=max_outstanding
        self._clock=clock or time.monotonic
        self._lock=threading.Lock()
        self._issued={}

    @staticmethod
    def _key(token):
        return hashlib.sha256(token.encode("ascii")).digest()

    def issue(self, job_id, relative, *, sha256, length):
        if not isinstance(job_id,str) or not job_id or not isinstance(relative,str) or not relative:
            raise ValueError("Ticket must bind one validated original film output")
        if not isinstance(sha256,str) or not _DIGEST.fullmatch(sha256):
            raise ValueError("Ticket requires original server-verifiable artifact digest")
        if type(length) is not int or length<=0:
            raise ValueError("Ticket requires physical media byte size")
        with self._lock:
            now=self._clock()
            self._issued={k:v for k,v in self._issued.items() if v[0]>now}
            if len(self._issued)>=self._max:
                raise RuntimeError("Bounded browser artifact tickets exhausted")
            token=secrets.token_urlsafe(32)
            key=self._key(token)
            while key in self._issued:
                token=secrets.token_urlsafe(32);key=self._key(token)
            self._issued[key]=(now+self._ttl,job_id,relative,sha256,length)
        return {"url":"/v1/download/"+token,"expires_in_seconds":self._ttl,
                "sha256":sha256,"bytes":length,"single_use":True}

    def consume(self, token):
        if not isinstance(token,str) or not _TICKET.fullmatch(token):
            return None
        with self._lock:
            entry=self._issued.pop(self._key(token),None)
        if entry is None or entry[0]<=self._clock():
            return None
        _,job_id,relative,sha,length=entry
        return {"job_id":job_id,"relative":relative,"sha256":sha,"bytes":length}
