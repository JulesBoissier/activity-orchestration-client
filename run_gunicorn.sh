#!/bin/bash
gunicorn -w 4 -b 127.0.0.1:8050 src.app.app:server &
python main.py
