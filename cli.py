"""
cli.py — Command-line interface for the Bird Cam Agent.

NOTE: Provides subcommands for running the agent, capturing single photos,
      identifying existing photos, viewing stats, and testing SMS alerts.

WHY: The CLI wraps the orchestrator for interactive use. It's the primary
     interface for users on the Pi — they run `python cli.py run` to start
     monitoring or `python cli.py capture` for a one-shot capture.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from core.config import Config

logger = logging.getLogger(__name__)

VERSION = "0.1.0"


def create_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="bird-cam",
        description="Bird Cam Agent — record, photograph, and identify birds at your feeder",
    )
    parser.add_argument(
        "--version", action="version", version=f"bird-cam {VERSION}"
    )
    parser.add_argument(
        "--config", "-c", default=None, help="Path to config YAML file"
    )
    parser.add_argument(
        "--mock", action="store_true", help="Force mock mode (no hardware)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose debug logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run
    subparsers.add_parser("run", help="Start the camera monitoring loop")

    # capture
    subparsers.add_parser("capture", help="Take a single photo and identify the bird")

    # identify
    identify_parser = subparsers.add_parser(
        "identify", help="Identify a bird in an existing photo"
    )
    identify_parser.add_argument("photo_path", help="Path to the photo file")

    # dashboard
    subparsers.add_parser("dashboard", help="Start the web dashboard only")

    # stats
    subparsers.add_parser("stats", help="Print sighting statistics")

    # list
    list_parser = subparsers.add_parser("list", help="List recent sightings")
    list_parser.add_argument(
        "--limit", "-n", type=int, default=20, help="Number of sightings to show"
    )

    # init
    init_parser = subparsers.add_parser("init", help="Create a default config file")
    init_parser.add_argument(
        "--output", "-o", default="config.yaml", help="Output path for config file"
    )

    # test-sms
    subparsers.add_parser("test-sms", help="Send a test SMS notification")

    # health
    subparsers.add_parser("health", help="Check health of all subsystems")

    return parser


def cmd_run(agent) -> None:
    """Run the main monitoring loop."""
    agent.start_dashboard()
    agent.run()


def cmd_capture(agent) -> None:
    """Take a single photo and identify the bird."""
    sighting = agent.run_single_capture()
    if sighting:
        print(f"\nBird identified: {sighting.species}")
        print(f"  Scientific name: {sighting.scientific_name}")
        print(f"  Confidence: {sighting.confidence:.0%}")
        print(f"  Rarity: {sighting.rarity_level.value}")
        print(f"  Photo: {sighting.photo_path}")
        if sighting.is_rare:
            print(f"  ** RARE BIRD ALERT **")
    else:
        print("No bird detected in this capture.")
    agent.stop()


def cmd_identify(agent, photo_path: str) -> None:
    """Identify a bird in an existing photo."""
    result = agent.identifier.identify(photo_path)
    if result.is_bird:
        print(f"\nBird identified: {result.species}")
        print(f"  Scientific name: {result.scientific_name}")
        print(f"  Confidence: {result.confidence:.0%}")
        print(f"  Description: {result.description}")
        if result.alternative_species:
            print(f"  Alternatives: {', '.join(result.alternative_species)}")

        rarity = agent.rarity_checker.check_rarity(result.species)
        print(f"  Rarity: {rarity.value}")
        if agent.rarity_checker.is_rare(result.species):
            print(f"  ** RARE BIRD **")
    else:
        print("No bird detected in this photo.")
    agent.stop()


def cmd_dashboard(agent) -> None:
    """Start the web dashboard only."""
    agent.start_dashboard()
    print(f"Dashboard running. Press Ctrl+C to stop.")
    try:
        import time

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        agent.stop()


def cmd_stats(agent) -> None:
    """Print sighting statistics."""
    stats = agent.get_stats()
    print(f"\nBird Cam Statistics")
    print(f"=" * 40)
    print(f"Total sightings:  {stats.get('total_count', 0)}")
    print(f"Unique species:   {stats.get('unique_species', 0)}")

    rarity = stats.get("rarity_breakdown", {})
    if rarity:
        print(f"\nBy rarity level:")
        for level, count in sorted(rarity.items()):
            print(f"  {level:15s} {count}")

    agent.stop()


def cmd_list(agent, limit: int) -> None:
    """List recent sightings."""
    sightings = agent.list_sightings(limit=limit)
    if not sightings:
        print("No sightings recorded yet.")
        agent.stop()
        return

    print(f"\nRecent Sightings (last {len(sightings)})")
    print(f"{'Date':<22} {'Species':<25} {'Rarity':<12} {'Confidence'}")
    print(f"-" * 75)
    for s in sightings:
        date_str = s.timestamp[:19].replace("T", " ")
        print(
            f"{date_str:<22} {s.species:<25} {s.rarity_level.value:<12} {s.confidence:.0%}"
        )
    agent.stop()


def cmd_init(args) -> None:
    """Create a default config file."""
    output_path = args.output
    if os.path.exists(output_path):
        print(f"Config file already exists: {output_path}")
        response = input("Overwrite? (y/N): ")
        if response.lower() != "y":
            print("Aborted.")
            return

    Config.write_default_config(output_path)
    print(f"Config file created: {output_path}")
    print(f"Edit this file to configure your bird cam settings.")


def cmd_test_sms(agent) -> None:
    """Send a test SMS notification."""
    print("Sending test SMS...")
    result = agent.notifier.test_notification()
    if result:
        print("Test SMS sent successfully!")
    else:
        print("Failed to send test SMS.")
    agent.stop()


def cmd_health(agent) -> None:
    """Check health of all subsystems."""
    health = agent.health_check()
    print(f"\nBird Cam Health Check")
    print(f"=" * 40)

    camera_info = health.get("camera", {})
    print(f"Camera:     {camera_info.get('type', 'unknown')}")

    bridge_info = health.get("hermes_bridge", {})
    bridge_status = "healthy" if bridge_info.get("healthy") else "unhealthy"
    print(f"Hermes:     {bridge_status} ({bridge_info.get('mode', 'unknown')})")

    db_info = health.get("database", {})
    print(f"Database:   {db_info.get('path', 'unknown')}")

    rarity_info = health.get("rarity_checker", {})
    print(
        f"Rarity DB:  {rarity_info.get('species_count', 0)} species "
        f"({rarity_info.get('location', 'no location')})"
    )

    print(f"SMS sent:   {health.get('sms_sent_count', 0)} alerts")
    agent.stop()


def main() -> None:
    """CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Set up logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Handle commands that don't need an agent
    if args.command == "init":
        cmd_init(args)
        return

    if not args.command:
        parser.print_help()
        return

    # Create the agent
    from main import BirdCamAgent

    agent = BirdCamAgent(args.config)

    # Override mock mode if --mock flag is set
    if args.mock:
        # NOTE: Force mock mode across all subsystems
        agent.config = Config.from_dict(agent.config.to_dict())
        # The agent is already initialized with mock defaults if no config was provided
        logger.info("Mock mode forced via --mock flag")

    # Dispatch to command handler
    if args.command == "run":
        cmd_run(agent)
    elif args.command == "capture":
        cmd_capture(agent)
    elif args.command == "identify":
        cmd_identify(agent, args.photo_path)
    elif args.command == "dashboard":
        cmd_dashboard(agent)
    elif args.command == "stats":
        cmd_stats(agent)
    elif args.command == "list":
        cmd_list(agent, args.limit)
    elif args.command == "test-sms":
        cmd_test_sms(agent)
    elif args.command == "health":
        cmd_health(agent)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()