IMPORT_REGISTRY = {}


def register(spec_instance):
    """Called once per ImportSpec to add it to the registry."""
    IMPORT_REGISTRY[spec_instance.key] = spec_instance