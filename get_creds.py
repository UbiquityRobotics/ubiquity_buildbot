#! /usr/bin/python3

import os
import importlib.util
spec = importlib.util.spec_from_file_location("", os.getenv("BUILDBOT_CREDS_FILE", "creds/fake_creds.py"))
creds = importlib.util.module_from_spec(spec)
spec.loader.exec_module(creds)

