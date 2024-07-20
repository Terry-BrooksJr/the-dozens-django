#!/usr/bin/env python3

import os
import subprocess

from dopplersdk import DopplerSDK

doppler = DopplerSDK()
doppler.set_access_token(os.environ["DOPPLER_ACCESS_TOKEN"])
results = doppler.secrets.list(config="dev", project="yo-mama")
secrets = results.secrets.items()

for i in secrets:

    print(os.environ.items())

    # [i[0]] = i[1]['computed']
    # subprocess.run(["export", f"{i[0]}={i[1]['computed']}"])
    # RESULT =     subprocess.call(["export", "$", "?"])

    print(f"{i[0]} - {i[1]['computed']}")
    print("----------------")
    print(RESULT)
