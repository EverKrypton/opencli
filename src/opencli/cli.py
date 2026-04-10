#!/usr/bin/env python3
"""OPENCLI - Command line interface."""

import sys
import os
import argparse
import asyncio

def main():
    parser = argparse.ArgumentParser(
        prog="opencli",
        description="AI-powered CLI agent for Terminal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  opencli                    Start interactive TUI
  opencli login sk-xxx       Set API key
  opencli models             List available models
  opencli config             Show current configuration
  opencli --provider ollama  Use Ollama (local models)

Environment Variables:
  OPENCLI_API_KEY     API key for authentication
  OPENCLI_BASE_URL    Custom API base URL
  OPENCLI_PROVIDER    Provider name (openai, anthropic, ollama...)
  OPENCLI_MODEL       Default model to use
        """
    )
    
    parser.add_argument(
        "command",
        nargs="?",
        choices=["login", "logout", "models", "config", "providers"],
        help="Command to run"
    )
    
    parser.add_argument(
        "args",
        nargs="*",
        help="Command arguments"
    )
    
    parser.add_argument(
        "--provider", "-p",
        help="Provider to use (openai, anthropic, ollama, groq, openrouter)"
    )
    
    parser.add_argument(
        "--model", "-m",
        help="Model to use"
    )
    
    parser.add_argument(
        "--base-url", "-u",
        help="Custom API base URL"
    )
    
    parser.add_argument(
        "--key", "-k",
        help="API key"
    )
    
    parser.add_argument(
        "--version", "-v",
        action="store_true",
        help="Show version"
    )
    
    args = parser.parse_args()
    
    if args.version:
        from opencli import __version__
        print(f"OPENCLI v{__version__}")
        return
    
    if args.command == "login":
        handle_login(args.args, args)
    elif args.command == "logout":
        handle_logout()
    elif args.command == "models":
        asyncio.run(handle_models(args))
    elif args.command == "config":
        handle_config()
    elif args.command == "providers":
        handle_providers()
    else:
        start_tui()


def handle_login(args_list, args):
    """Handle login command."""
    from opencli.utils.config import Config
    
    config = Config.load()
    
    if args_list:
        api_key = args_list[0]
    elif args.key:
        api_key = args.key
    else:
        import getpass
        api_key = getpass.getpass("Enter API key: ")
    
    if not api_key:
        print("Error: No API key provided")
        sys.exit(1)
    
    from opencli.providers import detect_provider
    
    provider = args.provider or detect_provider(api_key)
    
    config.ai.api_key = api_key
    config.ai.base_url = args.base_url or config.ai.base_url
    
    if args.model:
        config.ai.model = args.model
    
    config.save()
    
    print(f"✓ Logged in as: {provider}")
    print(f"✓ Config saved to: ~/.opencli/config.json")
    print()
    print("You can also export the API key:")
    print(f'  export OPENCLI_API_KEY="{api_key[:10]}..."')


def handle_logout():
    """Handle logout command."""
    from opencli.utils.config import Config
    
    config = Config.load()
    config.ai.api_key = ""
    config.save()
    
    print("✓ Logged out")
    print("✓ API key removed from config")


async def handle_models(args):
    """Handle models command."""
    from opencli.utils.config import Config
    from opencli.providers import fetch_models, get_provider_config, PROVIDERS
    
    config = Config.load()
    
    provider = args.provider or os.environ.get("OPENCLI_PROVIDER", "openai")
    api_key = config.ai.api_key or os.environ.get("OPENCLI_API_KEY", "")
    
    if provider == "ollama":
        print("Fetching models from Ollama (local)...")
        models = await fetch_models("ollama", "")
    elif api_key:
        print(f"Fetching models from {provider}...")
        try:
            models = await fetch_models(provider, api_key)
        except Exception as e:
            print(f"Error: {e}")
            print("Using default model list:")
            models = get_provider_config(provider).models
    else:
        print("No API key configured. Default models for", provider + ":")
        models = get_provider_config(provider).models
    
    print()
    print("Available models:")
    for m in models[:30]:
        print(f"  • {m}")
    
    if len(models) > 30:
        print(f"  ... and {len(models) - 30} more")
    
    print()
    print("Use: opencli --model <name>  to set a model")


def handle_config():
    """Handle config command."""
    from opencli.utils.config import Config
    
    config = Config.load()
    
    print("Current Configuration:")
    print()
    print(f"  Provider:   {os.environ.get('OPENCLI_PROVIDER', 'from config')}")
    print(f"  API Key:    {'configured' if config.ai.api_key else 'not set'}")
    print(f"  Base URL:   {config.ai.base_url}")
    print(f"  Model:      {config.ai.model}")
    print(f"  Max Tokens: {config.ai.max_tokens}")
    print()
    print(f"  Config file: ~/.opencli/config.json")
    print()
    print("Environment variables (override config):")
    print(f"  OPENCLI_API_KEY    {'set' if os.environ.get('OPENCLI_API_KEY') else 'not set'}")
    print(f"  OPENCLI_PROVIDER   {os.environ.get('OPENCLI_PROVIDER', 'not set')}")
    print(f"  OPENCLI_MODEL      {os.environ.get('OPENCLI_MODEL', 'not set')}")


def handle_providers():
    """Handle providers command."""
    from opencli.providers import PROVIDERS
    
    print("Supported Providers:")
    print()
    
    for name, config in PROVIDERS.items():
        print(f"  {name}")
        print(f"    Base URL: {config.base_url}")
        print(f"    Default model: {config.default_model}")
        print()


def start_tui():
    """Start the interactive TUI."""
    from opencli.tui.app import OpenCLIApp
    
    app = OpenCLIApp()
    try:
        app.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
