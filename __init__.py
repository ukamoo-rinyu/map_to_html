# -*- coding: utf-8 -*-
def classFactory(iface):
    from .plugin import FacilityAppGeneratorPlugin
    return FacilityAppGeneratorPlugin(iface)
