#!/usr/bin/env python3
"""
AWS IMDSv2 Enforcement Verification Script

Checks all EC2 instances in an account/region for IMDSv2 enforcement.
Reports instances with HttpTokens=optional (non-compliant).

Usage:
    python3 verify-imdsv2.py --region us-east-1
    python3 verify-imdsv2.py --region us-east-1 --profile prod --output json
"""

import argparse
import boto3
import json
import sys
from botocore.exceptions import ClientError, NoCredentialsError
from typing import List, Dict, Any


def get_ec2_client(region: str, profile: str = None):
    """Create EC2 client with optional profile."""
    session_kwargs = {"region_name": region}
    if profile:
        session_kwargs["profile_name"] = profile
    session = boto3.Session(**session_kwargs)
    return session.client("ec2")


def get_all_instances(ec2_client) -> List[Dict[str, Any]]:
    """Retrieve all EC2 instances with metadata options."""
    instances = []
    paginator = ec2_client.get_paginator("describe_instances")
    
    for page in paginator.paginate():
        for reservation in page["Reservations"]:
            for instance in reservation["Instances"]:
                instances.append(instance)
    return instances


def check_imdsv2_compliance(instance: Dict[str, Any]) -> Dict[str, Any]:
    """Check if instance has IMDSv2 enforced."""
    instance_id = instance["InstanceId"]
    state = instance["State"]["Name"]
    metadata = instance.get("MetadataOptions", {})
    
    http_tokens = metadata.get("HttpTokens", "unknown")
    http_endpoint = metadata.get("HttpEndpoint", "unknown")
    hop_limit = metadata.get("HttpPutResponseHopLimit", "unknown")
    metadata_state = metadata.get("State", "unknown")
    
    # Compliant: http_tokens == "required" AND http_endpoint == "enabled"
    compliant = (http_tokens == "required" and http_endpoint == "enabled")
    
    return {
        "instance_id": instance_id,
        "state": state,
        "compliant": compliant,
        "http_tokens": http_tokens,
        "http_endpoint": http_endpoint,
        "hop_limit": hop_limit,
        "metadata_state": metadata_state,
        "instance_type": instance.get("InstanceType"),
        "launch_time": str(instance.get("LaunchTime", "")),
        "tags": {t["Key"]: t["Value"] for t in instance.get("Tags", [])}
    }


def main():
    parser = argparse.ArgumentParser(description="Verify IMDSv2 enforcement across EC2 instances")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--profile", help="AWS profile name")
    parser.add_argument("--output", choices=["table", "json", "csv"], default="table")
    parser.add_argument("--non-compliant-only", action="store_true", 
                       help="Show only non-compliant instances")
    parser.add_argument("--include-stopped", action="store_true",
                       help="Include stopped/terminated instances")
    args = parser.parse_args()

    try:
        ec2 = get_ec2_client(args.region, args.profile)
    except NoCredentialsError:
        print("Error: AWS credentials not found. Run 'aws configure' or set profile.", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning region: {args.region}...", file=sys.stderr)
    instances = get_all_instances(ec2)
    
    if not args.include_stopped:
        instances = [i for i in instances if i["State"]["Name"] in ("running", "pending")]

    results = [check_imdsv2_compliance(i) for i in instances]
    
    if args.non_compliant_only:
        results = [r for r in results if not r["compliant"]]

    # Output
    if args.output == "json":
        print(json.dumps(results, indent=2, default=str))
    elif args.output == "csv":
        import csv
        writer = csv.DictWriter(sys.stdout, fieldnames=results[0].keys() if results else [])
        writer.writeheader()
        for r in results:
            r_copy = r.copy()
            r_copy["tags"] = json.dumps(r_copy["tags"])
            writer.writerow(r_copy)
    else:  # table
        if not results:
            print("No instances found.")
            return
        
        # Summary
        total = len(results)
        compliant = sum(1 for r in results if r["compliant"])
        non_compliant = total - compliant
        
        print(f"\n{'='*60}")
        print(f"IMDSv2 Compliance Report — Region: {args.region}")
        print(f"{'='*60}")
        print(f"Total instances:     {total}")
        print(f"Compliant (required): {compliant}")
        print(f"Non-compliant:       {non_compliant}")
        print(f"{'='*60}\n")
        
        # Table
        headers = ["Instance ID", "State", "HttpTokens", "HttpEndpoint", "HopLimit", "MetaState", "Compliant"]
        col_widths = [20, 10, 12, 14, 10, 12, 10]
        
        def fmt_row(cells):
            return "  ".join(str(c).ljust(w) for c, w in zip(cells, col_widths))
        
        print(fmt_row(headers))
        print(fmt_row(["-"*w for w in col_widths]))
        
        for r in results:
            cells = [
                r["instance_id"],
                r["state"],
                r["http_tokens"],
                r["http_endpoint"],
                str(r["hop_limit"]),
                r["metadata_state"],
                "✅" if r["compliant"] else "❌"
            ]
            print(fmt_row(cells))

    # Exit code: 1 if any non-compliant
    if any(not r["compliant"] for r in results):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()