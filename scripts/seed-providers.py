#!/usr/bin/env python3
"""Seed provider data into the database (if needed in the future).

Currently providers are stored in the static registry (registry.py).
This script is a placeholder for when provider data moves to the database.
"""

from api.app.providers.registry import get_all_providers


def main():
    providers = get_all_providers()
    print(f"🌊 Windy Clone — {len(providers)} providers registered:\n")

    for p in providers:
        status = "🔒 Coming Soon" if p.coming_soon else "✅ Available"
        featured = " ⭐" if p.featured else ""
        print(f"  {p.logo}  {p.name:<22} {p.provider_type:<8} ${p.starting_price:<6} {status}{featured}")

    print(f"\nTotal: {len(providers)} providers")
    print("Provider data is currently in the static registry. No database seeding needed.")


if __name__ == "__main__":
    main()
