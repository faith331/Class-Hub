
import sys
sys.path.append(r'/mnt/data/ClassHub_HomepageAuth_Fixed')
import app as m
from flask import Flask
a = m.app
with a.app_context():
    m.init_db(); m.seed_demo()
print('OK')
