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

    # local-id
    local_id_parser = subparsers.add_parser(
        "local-id", help="Identify a bird using only the local classifier (no Hermes)"
    )
    local_id_parser.add_argument("photo_path", help="Path to the photo file")

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

    # build-dataset
    build_parser = subparsers.add_parser(
        "build-dataset", help="Build photo dataset from iNaturalist, CUB-200, and archive"
    )
    build_parser.add_argument(
        "--species", "-s", default="pnw", choices=["pnw", "kenya", "custom"],
        help="Which species list to use (default: pnw)"
    )
    build_parser.add_argument(
        "--output", "-o", default="data/training", help="Output directory for dataset"
    )
    build_parser.add_argument(
        "--max-per-species", type=int, default=200, help="Max images per species"
    )
    build_parser.add_argument(
        "--sources", nargs="+", default=["inaturalist", "cub200", "archive"],
        help="Sources to use (default: all)"
    )

    # train-classifier
    train_parser = subparsers.add_parser(
        "train-classifier", help="Train the local bird classifier"
    )
    train_parser.add_argument(
        "--dataset", "-d", default="data/training", help="Dataset directory"
    )
    train_parser.add_argument(
        "--output-dir", default="data/models", help="Where to save the trained model"
    )
    train_parser.add_argument(
        "--epochs", type=int, default=10, help="Training epochs"
    )
    train_parser.add_argument(
        "--batch-size", type=int, default=16, help="Batch size"
    )
    train_parser.add_argument(
        "--lr", type=float, default=0.001, help="Learning rate"
    )
    train_parser.add_argument(
        "--export-onnx", action="store_true", help="Also export to ONNX after training"
    )

    # train-audio-classifier
    train_audio_parser = subparsers.add_parser(
        "train-audio-classifier", help="Train the local bird sound classifier"
    )
    train_audio_parser.add_argument(
        "--dataset", "-d", required=True, help="Audio dataset directory (species subfolders of WAVs)"
    )
    train_audio_parser.add_argument(
        "--output-dir", default="data/models", help="Where to save the trained model"
    )
    train_audio_parser.add_argument(
        "--model-name", default="cnn", help="Model name tag for filenames"
    )
    train_audio_parser.add_argument(
        "--epochs", type=int, default=20, help="Training epochs"
    )
    train_audio_parser.add_argument(
        "--batch-size", type=int, default=16, help="Batch size"
    )
    train_audio_parser.add_argument(
        "--lr", type=float, default=0.001, help="Learning rate"
    )
    train_audio_parser.add_argument(
        "--export-onnx", action="store_true", help="Also export to ONNX after training"
    )

    # export-audio-onnx
    export_audio_parser = subparsers.add_parser(
        "export-audio-onnx", help="Export trained audio model to ONNX"
    )
    export_audio_parser.add_argument(
        "--model", required=True, help="Path to trained .pth model"
    )
    export_audio_parser.add_argument(
        "--labels", required=True, help="Path to .pkl label map"
    )
    export_audio_parser.add_argument(
        "--output", required=True, help="Output .onnx path"
    )

    # local-audio-id
    local_audio_parser = subparsers.add_parser(
        "local-audio-id", help="Identify a bird from audio using only the local classifier (no Hermes)"
    )
    local_audio_parser.add_argument("audio_path", help="Path to the audio file")

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


def cmd_local_id(agent, photo_path: str) -> None:
    """Identify a bird using only the local classifier (no Hermes fallback)."""
    if agent.local_classifier is None or not agent.local_classifier.is_ready():
        print("Local classifier is not available.")
        print("Train a model first with: python cli.py train-classifier")
        agent.stop()
        return

    result = agent.local_classifier.identify(photo_path)
    if result.is_bird:
        print(f"\n[Local Classifier] Bird identified: {result.species}")
        print(f"  Confidence: {result.confidence:.0%}")
        print(f"  Description: {result.description}")
        if result.alternative_species:
            print(f"  Alternatives: {', '.join(result.alternative_species)}")
    else:
        print("[Local Classifier] No bird detected (or confidence too low).")
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

    local_info = health.get("local_classifier", {})
    local_status = "ready" if local_info.get("ready") else "not ready"
    print(f"Local AI:   {local_status} ({local_info.get('species_count', 0)} species)")

    db_info = health.get("database", {})
    print(f"Database:   {db_info.get('path', 'unknown')}")

    rarity_info = health.get("rarity_checker", {})
    print(
        f"Rarity DB:  {rarity_info.get('species_count', 0)} species "
        f"({rarity_info.get('location', 'no location')})"
    )

    print(f"SMS sent:   {health.get('sms_sent_count', 0)} alerts")
    agent.stop()


def cmd_build_dataset(args) -> None:
    """Build a photo dataset for training the local classifier."""
    from core.config import DatasetBuilderConfig
    from modules.photo_dataset_builder import PhotoDatasetBuilder

    # Select species list
    if args.species == "pnw":
        from modules.pnw_birds import SPECIES_DATA

        species_list = [{"name": s["name"], "scientific_name": s["scientific_name"]} for s in SPECIES_DATA]
        print(f"Using Pacific Northwest species list ({len(species_list)} species)")
    elif args.species == "kenya":
        from modules.kenya_birds import SPECIES_DATA

        species_list = [{"name": s["name"], "scientific_name": s["scientific_name"]} for s in SPECIES_DATA]
        print(f"Using Kenya species list ({len(species_list)} species)")
    else:
        print("Custom species list: provide a JSON file path via --species-file (not yet implemented)")
        print("Use --species pnw or --species kenya for built-in lists.")
        return

    config = DatasetBuilderConfig(
        output_dir=args.output,
        max_images_per_species=args.max_per_species,
        sources=args.sources,
        mock_mode=False,
    )
    builder = PhotoDatasetBuilder(config)
    results = builder.build_dataset(species_list)
    stats = builder.get_dataset_stats()

    print(f"\nDataset built: {stats['output_dir']}")
    print(f"  Total species: {stats['total_species']}")
    print(f"  Total images:  {stats['total_images']}")
    print(f"  Species with ≥{stats['min_required']} images: {stats['species_with_minimum']}")
    print(f"\nBreakdown:")
    for slug, count in sorted(stats["species_breakdown"].items(), key=lambda x: -x[1])[:10]:
        print(f"  {slug:30s} {count:4d} images")
    if len(stats["species_breakdown"]) > 10:
        print(f"  ... and {len(stats['species_breakdown']) - 10} more")


def cmd_train_classifier(args) -> None:
    """Train the local bird classifier on a prepared dataset."""
    from modules.local_bird_classifier import LocalBirdClassifier

    print(f"Training classifier on dataset: {args.dataset}")
    result = LocalBirdClassifier.train_model(
        dataset_dir=args.dataset,
        output_dir=args.output_dir,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
    )

    if "error" in result:
        print(f"Training failed: {result['error']}")
        sys.exit(1)

    print(f"\nTraining complete!")
    print(f"  Best validation accuracy: {result['best_val_accuracy']:.1f}%")
    print(f"  Model saved to: {result['model_path']}")
    print(f"  Label map saved to: {result['label_path']}")
    print(f"  Classes: {result['num_classes']}")

    if args.export_onnx:
        print("\nExporting to ONNX...")
        onnx_result = LocalBirdClassifier.export_onnx(
            model_path=result["model_path"],
            label_path=result["label_path"],
            output_path=result["model_path"].replace(".pth", ".onnx"),
        )
        if "error" in onnx_result:
            print(f"ONNX export failed: {onnx_result['error']}")
        else:
            print(f"  ONNX saved to: {onnx_result['output_path']} ({onnx_result['size_mb']:.1f} MB)")


def cmd_train_audio_classifier(args) -> None:
    """Train the local bird sound classifier on a prepared audio dataset."""
    from modules.local_audio_classifier import LocalAudioClassifier

    print(f"Training audio classifier on dataset: {args.dataset}")
    ok = LocalAudioClassifier.train_model(
        dataset_dir=args.dataset,
        output_dir=args.output_dir,
        model_name=args.model_name,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
    )

    if not ok:
        print("Training failed. See logs for details.")
        sys.exit(1)

    model_path = os.path.join(
        args.output_dir, f"audio_classifier_{args.model_name}.pth"
    )
    label_path = os.path.join(args.output_dir, "audio_classifier_labels.pkl")
    print(f"\nTraining complete!")
    print(f"  Model saved to: {model_path}")
    print(f"  Label map saved to: {label_path}")

    if args.export_onnx:
        print("\nExporting to ONNX...")
        onnx_path = model_path.replace(".pth", ".onnx")
        ok = LocalAudioClassifier.export_onnx(
            model_path=model_path,
            labels_path=label_path,
            output_path=onnx_path,
        )
        if ok:
            print(f"  ONNX saved to: {onnx_path}")
        else:
            print("  ONNX export failed. See logs for details.")


def cmd_export_audio_onnx(args) -> None:
    """Export a trained audio model to ONNX."""
    from modules.local_audio_classifier import LocalAudioClassifier

    ok = LocalAudioClassifier.export_onnx(
        model_path=args.model,
        labels_path=args.labels,
        output_path=args.output,
    )
    if ok:
        print(f"ONNX exported to: {args.output}")
    else:
        print("ONNX export failed. See logs for details.")
        sys.exit(1)


def cmd_local_audio_id(agent, audio_path: str) -> None:
    """Identify a bird from audio using only the local classifier (no Hermes fallback)."""
    if (
        agent.local_audio_classifier is None
        or not agent.local_audio_classifier.is_ready()
    ):
        print("Local audio classifier is not available.")
        print("Train a model first with: python cli.py train-audio-classifier")
        agent.stop()
        return

    result = agent.local_audio_classifier.identify(audio_path)
    if result.is_bird:
        print(f"\n[Local Audio Classifier] Bird identified: {result.species}")
        print(f"  Confidence: {result.confidence:.0%}")
        print(f"  Description: {result.description}")
        if result.alternative_species:
            print(f"  Alternatives: {', '.join(result.alternative_species)}")
    else:
        print("[Local Audio Classifier] No bird detected (or confidence too low).")
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

    if args.command == "build-dataset":
        cmd_build_dataset(args)
        return

    if args.command == "train-classifier":
        cmd_train_classifier(args)
        return

    if args.command == "train-audio-classifier":
        cmd_train_audio_classifier(args)
        return

    if args.command == "export-audio-onnx":
        cmd_export_audio_onnx(args)
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
    elif args.command == "local-id":
        cmd_local_id(agent, args.photo_path)
    elif args.command == "local-audio-id":
        cmd_local_audio_id(agent, args.audio_path)
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