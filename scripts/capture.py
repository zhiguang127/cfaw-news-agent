#!/usr/bin/env python3
"""Capture the actual app rectangle from a dedicated X11 display; no compositing."""
import json, os, subprocess, sys, urllib.request
port, output = int(sys.argv[1]), sys.argv[2]
state=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/s'))
w=state['w'][0]; x,y=w['pos']; width,height=w['px']
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','x11grab','-video_size',f'{width}x{height}','-i',f'{os.environ["DISPLAY"]}+{int(x)},{int(y)}','-frames:v','1','-y',output],check=True)
