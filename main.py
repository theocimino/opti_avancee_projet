import os
import sys
from dotenv import load_dotenv

load_dotenv()
pythonpath = os.getenv("PYTHONPATH")
print(pythonpath)
sys.path.insert(0, os.getenv("PYTHONPATH"))


for path in sys.path:
    print("  ", path)

from windfarm_eval import *


eap, spacing_constraint, placing_constraint = windfarm_eval('path/to/your/param.txt', 'path/to/your/X.txt')