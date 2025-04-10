import sys
import os

# Get the directory of the script
script_dir = os.path.dirname(os.path.realpath(__file__))

# Get parent directory (scripts directory)
parent_dir = os.path.dirname(script_dir)

sys.path.append(parent_dir)