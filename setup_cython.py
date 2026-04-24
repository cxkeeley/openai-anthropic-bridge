from setuptools import setup
from Cython.Build import cythonize
import os

# Ensure we are compiling the right file
setup(
    name='FastAPI Bridge Core',
    ext_modules=cythonize(
        "fastapi_bridge.py",
        compiler_directives={'language_level': "3"}
    ),
    zip_safe=False,
)
