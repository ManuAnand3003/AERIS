"""Compatibility shim for legacy imports.

The runtime now lives in inference/model_manager.py.
"""

from inference.model_manager import ModelManager, model_manager


def get_model_manager():
    return model_manager
