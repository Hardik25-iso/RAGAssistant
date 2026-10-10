"""Load secrets from AWS SSM Parameter Store (SecureString, KMS-encrypted).

The EC2 instance role grants ssm:GetParametersByPath on /studyrag/* only, so
the app never needs stored AWS access keys.
Parameter /studyrag/DATABASE_URL becomes the setting DATABASE_URL, and so on.
"""
import logging

import boto3

log = logging.getLogger(__name__)


def load_ssm_overrides(prefix: str, region: str) -> dict[str, str]:
    client = boto3.client("ssm", region_name=region)
    values: dict[str, str] = {}
    paginator = client.get_paginator("get_parameters_by_path")
    for page in paginator.paginate(Path=prefix, WithDecryption=True, Recursive=False):
        for param in page["Parameters"]:
            key = param["Name"][len(prefix):]
            values[key] = param["Value"]
    log.info("Loaded %d parameters from SSM (%s)", len(values), ", ".join(sorted(values)))
    return values
