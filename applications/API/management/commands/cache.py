"""
Django management command for cache operations using the generalized caching framework.

Usage examples:
    python manage.py cache_manager --list
    python manage.py cache_manager --stats
    python manage.py cache_manager --warm-all
    python manage.py cache_manager --clear-all
    python manage.py cache_manager --clear Insult
    python manage.py cache_manager --performance-report
"""

import json

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from loguru import logger

from common.cache_managers import cache_registry, get_cache_performance_summary


class Command(BaseCommand):
    help = "Manage application caches using the generalized caching framework"

    def add_arguments(self, parser):
        parser.add_argument(
            "--list",
            action="store_true",
            help="List all registered cache managers",
        )

        parser.add_argument(
            "--stats",
            action="store_true",
            help="Show statistics for all cache managers",
        )

        parser.add_argument(
            "--warm-all",
            action="store_true",
            help="Warm up all cache managers",
        )

        parser.add_argument(
            "--clear-all",
            action="store_true",
            help="Clear all cache managers",
        )

        parser.add_argument(
            "--clear",
            type=str,
            help="Clear specific cache manager by name",
            metavar="CACHE_NAME",
        )

        parser.add_argument(
            "--performance-report",
            action="store_true",
            help="Generate detailed performance report",
        )

        parser.add_argument(
            "--json",
            action="store_true",
            help="Output results in JSON format",
        )

        parser.add_argument(
            "--reason",
            type=str,
            default="management_command",
            help="Reason for cache operations (for logging)",
            metavar="REASON",
        )

    def handle(self, *args, **options):
        """Handle the management command."""

        if options["list"]:
            self._list_cache_managers(options["json"])

        elif options["stats"]:
            self._show_cache_stats(options["json"])

        elif options["warm_all"]:
            self._warm_all_caches(options["json"], options["reason"])

        elif options["clear_all"]:
            self._clear_all_caches(options["json"], options["reason"])

        elif options["clear"]:
            self._clear_specific_cache(
                options["clear"], options["json"], options["reason"]
            )

        elif options["performance_report"]:
            self._performance_report(options["json"])

        else:
            self.stdout.write(
                self.style.WARNING(
                    "No action specified. Use --help to see available options."
                )
            )

    def _list_cache_managers(self, json_output=False):
        """List all registered cache managers."""
        managers = cache_registry.names()

        if json_output:
            self.stdout.write(
                json.dumps(
                    {
                        "registered_managers": managers,
                        "count": len(managers),
                        "timestamp": timezone.now().isoformat(),
                    },
                    indent=2,
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Registered Cache Managers ({len(managers)}):")
            )
            for manager_name in managers:
                manager = cache_registry.get(manager_name)
                manager_type = type(manager).__name__
                self.stdout.write(f"  - {manager_name} ({manager_type})")

    def _show_cache_stats(self, json_output=False):
        """Show statistics for all cache managers."""
        try:
            stats = cache_registry.get_all_stats()

            if json_output:
                self.stdout.write(json.dumps(stats, indent=2, default=str))
            else:
                self.stdout.write(self.style.SUCCESS("Cache Manager Statistics:"))
                for name, stat in stats.items():
                    self.stdout.write(f"\n{name}:")
                    if isinstance(stat, dict):
                        for key, value in stat.items():
                            self.stdout.write(f"  {key}: {value}")
                    else:
                        self.stdout.write(f"  {stat}")

        except Exception as e:
            raise CommandError(f"Error getting cache stats: {e}") from e

    def _warm_all_caches(self, json_output=False, reason="management_command"):
        """Warm up all cache managers."""
        self.stdout.write("Warming up all cache managers...")

        results = {}
        total_managers = cache_registry.count()
        success_count = 0

        for name, manager in cache_registry.items():
            try:
                self.stdout.write(f"  Warming {name}...", ending="")

                # Try different warming strategies based on manager type
                if hasattr(manager, "get_cached_data"):
                    # Generic data managers
                    manager.get_cached_data()
                elif hasattr(manager, "get_all_categories"):
                    # Category managers
                    manager.get_all_categories()
                elif hasattr(manager, "get_form_choices"):
                    # Form choice managers
                    manager.get_form_choices()
                else:
                    self.stdout.write(" [SKIPPED - no warming method]")
                    continue

                results[name] = "success"
                success_count += 1
                self.stdout.write(self.style.SUCCESS(" [OK]"))

            except Exception as e:
                results[name] = f"error: {str(e)}"
                self.stdout.write(self.style.ERROR(f" [FAILED: {e}]"))
                logger.error(f"Error warming cache {name}: {e}")

        if json_output:
            self.stdout.write(
                json.dumps(
                    {
                        "results": results,
                        "summary": {
                            "total": total_managers,
                            "success": success_count,
                            "failed": total_managers - success_count,
                        },
                        "reason": reason,
                        "timestamp": timezone.now().isoformat(),
                    },
                    indent=2,
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nCache warming completed: {success_count}/{total_managers} successful"
                )
            )

    def _clear_all_caches(self, json_output=False, reason="management_command"):
        """Clear all cache managers."""

        if not json_output:
            self.stdout.write(
                self.style.WARNING(
                    "This will clear ALL cache managers. Continue? (y/N): "
                ),
                ending="",
            )

            confirm = input().lower()
            if confirm not in ["y", "yes"]:
                self.stdout.write("Operation cancelled.")
                return

        self.stdout.write("Clearing all cache managers...")

        try:
            cache_registry.invalidate_all(reason)

            if json_output:
                self.stdout.write(
                    json.dumps(
                        {
                            "status": "success",
                            "message": "All caches cleared",
                            "reason": reason,
                            "timestamp": timezone.now().isoformat(),
                        },
                        indent=2,
                    )
                )
            else:
                self.stdout.write(self.style.SUCCESS("All caches cleared successfully"))

        except Exception as e:
            if json_output:
                self.stdout.write(
                    json.dumps(
                        {
                            "status": "error",
                            "message": str(e),
                            "timestamp": timezone.now().isoformat(),
                        },
                        indent=2,
                    )
                )
            else:
                raise CommandError(f"Error clearing caches: {e}") from e

    def _clear_specific_cache(
        self, cache_name, json_output=False, reason="management_command"
    ):
        """Clear a specific cache manager."""
        manager = cache_registry.get(cache_name)

        if not manager:
            if json_output:
                self.stdout.write(
                    json.dumps(
                        {
                            "status": "error",
                            "message": f"Cache manager '{cache_name}' not found",
                            "available_managers": cache_registry.names(),
                            "timestamp": timezone.now().isoformat(),
                        },
                        indent=2,
                    )
                )
            else:
                raise CommandError(f"Cache manager '{cache_name}' not found")
            return

        try:
            manager.invalidate_cache(reason)

            if json_output:
                self.stdout.write(
                    json.dumps(
                        {
                            "status": "success",
                            "message": f"Cache '{cache_name}' cleared",
                            "reason": reason,
                            "timestamp": timezone.now().isoformat(),
                        },
                        indent=2,
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"Cache '{cache_name}' cleared successfully")
                )

        except Exception as e:
            if json_output:
                self.stdout.write(
                    json.dumps(
                        {
                            "status": "error",
                            "message": f"Error clearing cache '{cache_name}': {str(e)}",
                            "timestamp": timezone.now().isoformat(),
                        },
                        indent=2,
                    )
                )
            else:
                raise CommandError(f"Error clearing cache '{cache_name}': {e}") from e

    def _performance_report(self, json_output=False):
        """Generate detailed performance report."""
        try:
            report_data = {
                "performance_summary": get_cache_performance_summary(),
                "manager_details": cache_registry.get_all_stats(),
                "system_info": {
                    "total_managers": cache_registry.count(),
                    "manager_types": {},
                    "timestamp": timezone.now().isoformat(),
                },
            }

            # Collect manager type statistics
            for name, manager in cache_registry.items():
                manager_type = type(manager).__name__
                if manager_type not in report_data["system_info"]["manager_types"]:
                    report_data["system_info"]["manager_types"][manager_type] = 0
                report_data["system_info"]["manager_types"][manager_type] += 1

            if json_output:
                self.stdout.write(json.dumps(report_data, indent=2, default=str))
            else:
                self._format_performance_report(report_data)

        except Exception as e:
            raise CommandError(f"Error generating performance report: {e}") from e

    def _format_performance_report(self, report_data):
        """Format performance report for human-readable output."""
        self.stdout.write(self.style.SUCCESS("=== CACHE PERFORMANCE REPORT ===\n"))

        # System overview
        system_info = report_data["system_info"]
        self.stdout.write(f'Total Cache Managers: {system_info["total_managers"]}')
        self.stdout.write("Manager Types:")
        for manager_type, count in system_info["manager_types"].items():
            self.stdout.write(f"  - {manager_type}: {count}")

        # Performance summary
        perf_summary = report_data.get("performance_summary", {})
        if "managers" in perf_summary:
            self.stdout.write("\n=== PERFORMANCE METRICS ===")
            for manager_name, stats in perf_summary["managers"].items():
                if isinstance(stats, dict) and "error" not in stats:
                    self.stdout.write(f"\n{manager_name}:")
                    for key, value in stats.items():
                        if key != "timestamp":
                            self.stdout.write(f"  {key}: {value}")

        if manager_details := report_data.get("manager_details", {}):
            self.stdout.write("\n=== DETAILED MANAGER STATS ===")
            for name, details in manager_details.items():
                if isinstance(details, dict) and "error" not in details:
                    self.stdout.write(f"\n{name}:")
                    for key, value in details.items():
                        self.stdout.write(f"  {key}: {value}")

        self.stdout.write(f'\nReport generated at: {system_info["timestamp"]}')
