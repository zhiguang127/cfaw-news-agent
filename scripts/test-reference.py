#!/usr/bin/env python3
"""Run native UI tests on an isolated X11 display on Linux; no shared host edits."""
import os, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[1]
env=os.environ.copy(); proc=None
try:
    if sys.platform.startswith('linux'):
        fd_r,fd_w=os.pipe()
        log=tempfile.TemporaryFile()
        proc=subprocess.Popen(['Xvfb','-displayfd',str(fd_w),'-screen','0','1280x1000x24','-nolisten','tcp'],pass_fds=(fd_w,),stdout=log,stderr=log)
        os.close(fd_w)
        with os.fdopen(fd_r) as f: display=f.readline().strip()
        if not display: raise SystemExit('Xvfb failed to allocate a display')
        env.update(DISPLAY=':'+display,WAYLAND_DISPLAY='',XDG_SESSION_TYPE='x11',LIBGL_ALWAYS_SOFTWARE='1',TEST_VISIBLE_VIRTUAL='1')
        mesa=Path('/usr/share/glvnd/egl_vendor.d/50_mesa.json')
        if mesa.exists(): env['__EGL_VENDOR_LIBRARY_FILENAMES']=str(mesa)
    raise SystemExit(subprocess.call([sys.executable,str(root/'tests/test_ui.py'),*sys.argv[1:]],cwd=root,env=env))
finally:
    if proc: proc.terminate();proc.wait(timeout=5)
