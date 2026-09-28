#!/usr/bin/env python3
"""Small client of Makepad's official remote bridge (no app-private hooks)."""
import json, time, urllib.request, urllib.parse

class UI:
    def __init__(self, port): self.base = f'http://127.0.0.1:{port}'
    def get(self, path, **params):
        if params: path += '?' + urllib.parse.urlencode(params)
        with urllib.request.urlopen(self.base + path, timeout=12) as r: return r.read()
    def snap(self): return json.loads(self.get('/snap'))['s']
    def texts(self): return [w['t'] for w in self.snap() if w.get('t') and w['ty'] != 'Splash']
    def wait(self, text, timeout=25):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if any(text in t for t in self.texts()): return
            time.sleep(.15)
        raise AssertionError(f'Missing {text!r}; visible: {self.texts()}')
    def click(self, text):
        for w in self.snap():
            if w.get('t') == text and w['ty'] != 'Splash':
                x,y,a,b = w['r']
                self.get('/click', x=x+a/2, y=y+b/2, wait=1)
                time.sleep(.1)
                return
        raise AssertionError(f'Cannot click {text!r}; {self.texts()}')
    def scroll(self, dy=500): self.get('/m', k='scroll', x=250, y=700, dy=dy, wait=1)

if __name__ == '__main__':
    import sys
    u=UI(int(sys.argv[1]))
    if len(sys.argv)>2: u.click(sys.argv[2])
    print('\n'.join(u.texts()))
