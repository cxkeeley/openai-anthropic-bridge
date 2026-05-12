#!/usr/bin/env python3
"""
Setup script for compiling the OpenAI/Anthropic Bridge with Cython.

This script compiles the entire core/ package and the main bridge module.
"""
from setuptools import setup
from Cython.Build import cythonize
import os

# Ensure we are compiling the right file
setup(
    name='FastAPI Bridge Core',
    ext_modules=cythonize(
        [
            "fastapi_bridge.py", 
            "core/__init__.py",
            "core/persona.py",
            "core/transformers.py",
            "core/security.py",
            "core/logger.py",
            "core/metrics.py"
        ],
        compiler_directives={'language_level': "3"}
    ),
    zip_safe=False,
)
