#!/usr/bin/env python3
"""
validate_config.py — Validates Hermes config.yaml structure and provider connectivity.
Run: python validate_config.py [--provider NAME] [--test-connectivity]
"""

import sys
import yaml
import subprocess
import argparse
from pathlib import Path


def load_config():
    config_path = Path.home() / ".hermes" / "config.yaml"
    if not config_path.exists():
        print(f"❌ Config not found: {config_path}")
        sys.exit(1)
    with open(config_path) as f:
        return yaml.safe_load(f)


def validate_structure(config):
    """Check required top-level keys and custom_providers format."""
    errors = []
    warnings = []
    
    # Required sections
    for key in ["model", "providers", "custom_providers"]:
        if key not in config:
            errors.append(f"Missing required key: {key}")
    
    if "custom_providers" in config:
        for i, provider in enumerate(config["custom_providers"]):
            if "name" not in provider:
                errors.append(f"custom_providers[{i}]: missing 'name'")
            if "base_url" not in provider:
                errors.append(f"custom_providers[{i}] ({provider.get('name', '?')}): missing 'base_url'")
            if "api_key" not in provider:
                warnings.append(f"custom_providers[{i}] ({provider.get('name', '?')}): missing 'api_key'")
            if "models" not in provider and "model" not in provider:
                warnings.append(f"custom_providers[{i}] ({provider.get('name', '?')}): no models listed")
            if "api_mode" not in provider:
                warnings.append(f"custom_providers[{i}] ({provider.get('name', '?')}): missing 'api_mode' (default: openai_chat)")
    
    return errors, warnings


def test_connectivity(provider_name):
    """Test if provider is reachable via hermes CLI."""
    try:
        result = subprocess.run(
            ["hermes", "model", "--provider", provider_name],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print(f"✅ Provider '{provider_name}' reachable")
            return True
        else:
            print(f"❌ Provider '{provider_name}' test failed: {result.stderr.strip()}")
            return False
    except subprocess.TimeoutExpired:
        print(f"⏱️ Provider '{provider_name}' test timed out")
        return False
    except FileNotFoundError:
        print("❌ 'hermes' command not found in PATH")
        return False


def main():
    parser = argparse.ArgumentParser(description="Validate Hermes config.yaml")
    parser.add_argument("--provider", help="Test connectivity for specific provider")
    parser.add_argument("--test-connectivity", action="store_true", help="Test all custom providers")
    args = parser.parse_args()
    
    print("🔍 Loading config...")
    config = load_config()
    
    print("🔍 Validating structure...")
    errors, warnings = validate_structure(config)
    
    for w in warnings:
        print(f"⚠️  {w}")
    for e in errors:
        print(f"❌ {e}")
    
    if errors:
        print(f"\n❌ Validation failed with {len(errors)} error(s)")
        sys.exit(1)
    
    print("✅ Structure validation passed")
    
    # Test connectivity
    providers_to_test = []
    if args.provider:
        providers_to_test = [args.provider]
    elif args.test_connectivity:
        providers_to_test = [p["name"] for p in config.get("custom_providers", [])]
    
    if providers_to_test:
        print(f"\n🌐 Testing connectivity for {len(providers_to_test)} provider(s)...")
        for p in providers_to_test:
            test_connectivity(p)
    
    print("\n✅ All checks passed")


if __name__ == "__main__":
    main()