#!/usr/bin/env python3
"""
Terraform Apply Retry Script

Runs terraform apply repeatedly until it succeeds, handling
temporary failures like OCI "Out of host capacity" errors.
"""

import argparse
import logging
import re
import subprocess
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path


class ColorFilterHandler(RotatingFileHandler):
    def emit(self, record):
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = re.sub(r'\x1b\[[0-9;]*m', '', record.msg)
        if hasattr(record, 'args') and record.args:
            record.args = tuple(
                re.sub(r'\x1b\[[0-9;]*m', '', str(arg)) if isinstance(arg, str) else arg
                for arg in record.args
            )
        super().emit(record)


def setup_logging(log_file: str = 'terraform_retry.log', log_level: int = logging.INFO):
    """Set up logging to both console and rotating file."""
    logger = logging.getLogger(__name__)
    logger.setLevel(log_level)

    logger.handlers.clear()

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logs_dir = Path.cwd() / 'logs'
    logs_dir.mkdir(exist_ok=True)

    log_path = logs_dir / log_file

    file_handler = ColorFilterHandler(
        log_path, maxBytes=10 * 1024 * 1024, backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def run_terraform_apply(  # noqa: PLR0913, PLR0915, PLR0912, PLR0911
    config_dir: Path,
    max_attempts: int = 50,
    retry_delay: int = 30,
    *,
    auto_approve: bool = True,
    availability_domains: list[str],
    logger: logging.Logger,
    timeout: int = 1800,
    no_cleanup: bool = False,
    plan_only: bool = False,
) -> bool:
    """
    Run terraform apply repeatedly until it succeeds.
    Automatically destroys all resources on failure.

    Args:
        config_dir: Directory containing terraform configuration
        max_attempts: Maximum number of attempts
        retry_delay: Delay between retries in seconds
        auto_approve: Whether to auto-approve terraform apply
        availability_domains: List of availability domains to cycle through
        logger: Logger instance
        timeout: Timeout for terraform operations in seconds
        no_cleanup: Whether to skip resource cleanup on failure
        plan_only: Whether to run terraform plan instead of apply


    Returns:
        True if terraform operation succeeded, False otherwise

    """
    if not config_dir.exists():
        logger.error('Terraform config directory does not exist: %s', config_dir)
        return False

    cmd = ['terraform', 'plan' if plan_only else 'apply']
    if auto_approve and not plan_only:
        cmd.append('-auto-approve')

    attempt = 1

    while attempt <= max_attempts:
        # Cycle through regions and ADs based on attempt number
        region_index = (attempt - 1) % len(availability_domains)
        current_ad = availability_domains[region_index]

        logger.info(
            'Attempt %d/%d: Using AD %s',
            attempt,
            max_attempts,
            current_ad,
        )

        # Update main.tf with current availability domain
        update_main_tf(config_dir, current_ad, logger)

        logger.info('Running %s', cmd)

        try:
            result = subprocess.run(  # noqa: S603
                cmd,
                check=False,
                cwd=config_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode == 0:
                operation = 'plan' if plan_only else 'apply'
                logger.info('Terraform %s succeeded!', operation)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug('Output:\n%s', result.stdout)
                return True
            operation = 'plan' if plan_only else 'apply'
            logger.warning(
                'Terraform %s failed (exit code: %d)', operation, result.returncode
            )
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug('Error output:\n%s', result.stderr)

            # For plan-only mode, don't clean up or retry
            if plan_only:
                return False

            # Clean up resources after any failure, then check if we should retry
            if not no_cleanup:
                cleanup_resources(config_dir, auto_approve=auto_approve, logger=logger)

            # Check for specific recoverable errors
            error_output = result.stderr.lower()
            if (
                'out of host capacity' in error_output
                or 'internalerror' in error_output
            ):
                if attempt < max_attempts:
                    logger.info(
                        'Detected recoverable error (host capacity). Retrying in %d seconds...',
                        retry_delay,
                    )
                    time.sleep(retry_delay)
                    attempt += 1
                    continue
                logger.error(
                    'Detected recoverable error but no more attempts available.'
                )
                return False

            logger.error('Non-recoverable error detected. Stopping retries.')

        except subprocess.TimeoutExpired:
            logger.warning('Terraform apply timed out. Retrying...')
            attempt += 1
            continue

        except Exception:
            operation = 'plan' if plan_only else 'apply'
            logger.exception('Unexpected error running terraform %s:', operation)
            if not plan_only and not no_cleanup:
                logger.info('Cleaning up resources due to unexpected error...')
                cleanup_resources(config_dir, auto_approve=auto_approve, logger=logger)
            return False

        else:
            return False

    logger.error('Maximum attempts (%d) exceeded.', max_attempts)
    if not plan_only and not no_cleanup:
        logger.info('Cleaning up resources...')
        cleanup_resources(config_dir, auto_approve=auto_approve, logger=logger)
    return False


def check_availability_domain_in_tfvars(config_dir: Path) -> bool:
    """Check if availability_domain is set in terraform.tfvars."""
    tfvars_file = config_dir / 'terraform.tfvars'
    if not tfvars_file.exists():
        return False

    content = tfvars_file.read_text()
    # Look for availability_domain = "non-empty-value"
    match = re.search(r'availability_domain\s*=\s*"([^"]*)"', content)
    return match is not None and match.group(1).strip() != ''


def update_main_tf(
    config_dir: Path,
    availability_domain: str,
    logger: logging.Logger,
) -> None:
    """Update terraform.tfvars with the specified availability domain."""
    # Try to update terraform.tfvars first
    tfvars_file = config_dir / 'terraform.tfvars'
    if tfvars_file.exists():
        content = tfvars_file.read_text()
        # Replace the availability_domain line in terraform.tfvars
        updated_content = re.sub(
            r'availability_domain\s*=\s*"[^"]*"',
            f'availability_domain = "{availability_domain}"',
            content,
        )
        if updated_content != content:
            tfvars_file.write_text(updated_content)
            logger.info(
                'Updated terraform.tfvars with availability domain: %s',
                availability_domain,
            )
            return
        logger.warning(
            'Could not find availability_domain line in terraform.tfvars to update'
        )

    # Fallback: Try to update main.tf (for older configurations)
    main_tf_file = config_dir / 'main.tf'
    if not main_tf_file.exists():
        logger.warning('main.tf not found, skipping AD update')
        return

    content = main_tf_file.read_text()
    # Replace the availability_domain line
    updated_content = re.sub(
        r'availability_domain\s*=\s*"[^"]*"',
        f'availability_domain = "{availability_domain}"',
        content,
    )
    if updated_content != content:
        main_tf_file.write_text(updated_content)
        logger.info('Updated main.tf with availability domain: %s', availability_domain)
    else:
        logger.warning('Could not find availability_domain line in main.tf to update')


def cleanup_resources(
    config_dir: Path, *, auto_approve: bool, logger: logging.Logger
) -> None:
    """
    Clean up all terraform resources by running terraform destroy.

    Args:
        config_dir: Directory containing terraform configuration
        auto_approve: Whether to auto-approve terraform destroy
        logger: Logger instance

    """
    logger.info('Running terraform destroy to clean up all resources...')

    destroy_cmd = ['terraform', 'destroy']
    if auto_approve:
        destroy_cmd.append('-auto-approve')

    try:
        result = subprocess.run(  # noqa: S603
            destroy_cmd,
            check=False,
            cwd=config_dir,
            capture_output=True,
            text=True,
            timeout=1800,
        )

        if result.returncode == 0:
            logger.info('Successfully cleaned up all resources')
            logger.info('Destroy output:\n%s', result.stdout)
        else:
            logger.error(
                'Failed to clean up resources (exit code: %d)', result.returncode
            )
            logger.error('Destroy error output:\n%s', result.stderr)

    except subprocess.TimeoutExpired:
        logger.exception('Terraform destroy timed out')
    except Exception:
        logger.exception('Unexpected error during resource cleanup:')


def main():  # noqa: PLR0915
    parser = argparse.ArgumentParser(
        description='Run terraform apply repeatedly until it succeeds. Automatically cleans up resources on failure.'
    )
    parser.add_argument(
        'config_dir',
        nargs='?',
        default='.',
        metavar='DIR',
        help='Path to terraform configuration directory (default: current directory)',
    )
    parser.add_argument(
        '--max-attempts',
        type=int,
        default=50,
        metavar='N',
        help='Maximum number of attempts (default: 50)',
    )
    parser.add_argument(
        '--retry-delay',
        type=int,
        default=30,
        metavar='SECONDS',
        help='Delay between retries in seconds (default: 30)',
    )
    parser.add_argument(
        '--no-auto-approve',
        action='store_true',
        help='Do not auto-approve terraform apply/destroy (requires manual confirmation)',
    )
    parser.add_argument(
        '--log-file',
        type=str,
        default='terraform_retry.log',
        metavar='FILENAME',
        help='Log file name (will be placed in logs/ directory, default: terraform_retry.log)',
    )
    parser.add_argument(
        '--availability-domains',
        nargs='+',
        metavar='DOMAIN',
        help='List of availability domains to cycle through, with tenancy prefix (e.g. your-tenancy-prefix:US-ASHBURN-AD-1, your-tenancy-prefix:US-ASHBURN-AD-2)',
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=1800,
        metavar='SECONDS',
        help='Timeout for terraform operations in seconds (default: 1800)',
    )
    parser.add_argument(
        '--no-cleanup',
        action='store_true',
        help='Do not automatically destroy resources on failure',
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Reduce log output (only errors and important info)',
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Increase log output (show terraform stdout/stderr)',
    )
    parser.add_argument(
        '--plan-only',
        action='store_true',
        help='Run terraform plan instead of apply',
    )

    args = parser.parse_args()

    # Handle conflicting verbosity options
    if args.quiet and args.verbose:
        parser.error('--quiet and --verbose cannot be used together')

    # Set up logging with appropriate level
    log_level = (
        logging.ERROR if args.quiet else logging.DEBUG if args.verbose else logging.INFO
    )
    logger = setup_logging(args.log_file, log_level)

    config_dir = Path(args.config_dir).resolve()
    auto_approve = not args.no_auto_approve

    logger.info('Starting terraform apply retry script with automatic cleanup')
    logger.info('Log file: %s', Path.cwd() / 'logs' / args.log_file)
    logger.info('Config directory: %s', config_dir)
    logger.info('Max attempts: %d', args.max_attempts)
    logger.info('Retry delay: %d seconds', args.retry_delay)
    logger.info('Auto approve: %s', auto_approve)
    logger.info('Availability domains: %s', args.availability_domains)

    # Check if availability_domain is set in terraform.tfvars
    ad_in_tfvars = check_availability_domain_in_tfvars(config_dir)

    if args.availability_domains is None and not ad_in_tfvars:
        logger.error(
            'No --availability-domains provided and availability_domain not set in terraform.tfvars'
        )
        logger.error(
            'Please either provide --availability-domains or set availability_domain in terraform.tfvars'
        )
        sys.exit(1)
    elif args.availability_domains is not None:
        # Use provided availability domains (this will override any existing value in tfvars)
        availability_domains = args.availability_domains
        if ad_in_tfvars:
            logger.info(
                'availability_domain is set in terraform.tfvars, but will be overridden by --availability-domains'
            )
    else:
        # Use existing availability domain from terraform.tfvars (no cycling)
        logger.info(
            'No --availability-domains provided, using existing availability_domain from terraform.tfvars'
        )
        # Read the current value from terraform.tfvars
        tfvars_file = config_dir / 'terraform.tfvars'
        content = tfvars_file.read_text()
        match = re.search(r'availability_domain\s*=\s*"([^"]*)"', content)
        if match:
            current_ad = match.group(1)
            availability_domains = [current_ad]
            logger.info(
                'Using availability domain from terraform.tfvars: %s', current_ad
            )
        else:
            logger.error('Could not read availability_domain from terraform.tfvars')
            sys.exit(1)

    success = run_terraform_apply(
        config_dir=config_dir,
        max_attempts=args.max_attempts,
        retry_delay=args.retry_delay,
        auto_approve=auto_approve,
        availability_domains=availability_domains,
        logger=logger,
        timeout=args.timeout,
        no_cleanup=args.no_cleanup,
        plan_only=args.plan_only,
    )

    if success:
        logger.info('Script completed successfully!')
        sys.exit(0)
    else:
        logger.error('Script failed! All resources have been cleaned up.')
        sys.exit(1)


if __name__ == '__main__':
    main()
