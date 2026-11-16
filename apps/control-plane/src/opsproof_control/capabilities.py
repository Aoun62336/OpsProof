"""Trusted environment identity and observation capability, separate from actuation."""


def observations_enabled(config) -> bool:
    # Existing local recovery configurations continue to include their observer.
    return bool(
        getattr(config, "kubernetes_observation_enabled", False)
        or getattr(config, "kubernetes_recovery_enabled", False)
    )


def environment_description(config) -> dict:
    kind = getattr(config, "environment", "local")
    return {
        "environment": kind,
        "environment_label": "Temporary EKS" if kind == "temporary-eks" else "Local sandbox",
    }
