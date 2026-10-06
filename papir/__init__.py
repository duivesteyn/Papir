#!/usr/bin/env python3
# coding: utf-8
#
# duivesteyn // Python // papir
# https://github.com/duivesteyn/papir
#
# # bmd 2026

"""Papir — beam reading material to your e-reader via API."""

from papir.papir import (
    clean_title,
    get_default_author,
    get_default_target,
    papirDevices,
    papirLogin,
    papirLogout,
    papirSend,
    resolve_author,
    resolve_title,
    set_default_author,
    set_default_target,
)

__all__ = ["papirSend", "papirLogin", "papirDevices", "papirLogout",
           "clean_title", "resolve_author", "resolve_title",
           "get_default_target", "set_default_target",
           "get_default_author", "set_default_author"]
__version__ = "0.2.2"
