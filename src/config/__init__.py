"""Configuration package for weather model selector."""
# This allows imports like: from src.config import settings
# while also supporting: from src.config.regions import get_region

from .settings import settings, Settings

__all__ = ['settings', 'Settings']
