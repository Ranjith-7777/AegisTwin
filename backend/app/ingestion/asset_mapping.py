"""Map recorded-dataset endpoints onto testbed identities and twin assets.

Two deliberately separate answers per IP:

* `testbed_identity` - what the host *was* in the dataset's own published
  testbed (e.g. CIC-IDS2017's Ubuntu web server). Factual, from the dataset
  documentation.
* `projected_asset_id` - which AegisArena twin asset that host is *projected*
  onto for visualisation. A projection, never an identity claim: the twin's
  13 cloud assets are not the CIC testbed machines. Hosts with no sensible
  twin counterpart (user workstations) keep their identity and get no
  projection rather than being forced onto an unrelated asset.

CIC-IDS2017 testbed addresses are from the dataset's published description
(https://www.unb.ca/cic/datasets/ids-2017.html). External traffic, including
the attackers', traverses the firewall's NAT, so in the labelled flows the
attack sources mostly appear as 172.16.0.1 - which is why that address is
projected onto the twin's external ingress (`external-user-01`).
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass


@dataclass(frozen=True)
class EndpointMapping:
    testbed_identity: str | None
    projected_asset_id: str | None


@dataclass(frozen=True)
class KnownHost:
    identity: str
    projected_asset_id: str | None


CICIDS2017_TESTBED: dict[str, KnownHost] = {
    # Network edge / external side.
    "172.16.0.1": KnownHost("cic-firewall-nat", "external-user-01"),
    "205.174.165.80": KnownHost("cic-firewall-external", "external-user-01"),
    "205.174.165.73": KnownHost("cic-attacker-kali", "external-user-01"),
    "205.174.165.69": KnownHost("cic-attacker-win-1", "external-user-01"),
    "205.174.165.70": KnownHost("cic-attacker-win-2", "external-user-01"),
    "205.174.165.71": KnownHost("cic-attacker-win-3", "external-user-01"),
    # Servers.
    "192.168.10.50": KnownHost("cic-web-server-ubuntu16", "api-gateway-01"),
    "205.174.165.68": KnownHost("cic-web-server-ubuntu16-public", "api-gateway-01"),
    "192.168.10.51": KnownHost("cic-ubuntu-server-12", "application-pod-01"),
    "205.174.165.66": KnownHost("cic-ubuntu-server-12-public", "application-pod-01"),
    "192.168.10.3": KnownHost("cic-dc-dns-win2016", "iam-service-01"),
    # User workstations: real testbed hosts with no twin counterpart.
    "192.168.10.19": KnownHost("cic-ubuntu14-32", None),
    "192.168.10.17": KnownHost("cic-ubuntu14-64", None),
    "192.168.10.16": KnownHost("cic-ubuntu16-32", None),
    "192.168.10.12": KnownHost("cic-ubuntu16-64", None),
    "192.168.10.9": KnownHost("cic-win7-pro", None),
    "192.168.10.5": KnownHost("cic-win81", None),
    "192.168.10.8": KnownHost("cic-win-vista", None),
    "192.168.10.14": KnownHost("cic-win10-32", None),
    "192.168.10.15": KnownHost("cic-win10-64", None),
    "192.168.10.25": KnownHost("cic-macos", None),
}

EXTERNAL_INTERNET = "external-internet"


def map_endpoint(ip: str, testbed: dict[str, KnownHost] = CICIDS2017_TESTBED) -> EndpointMapping:
    host = testbed.get(ip)
    if host is not None:
        return EndpointMapping(host.identity, host.projected_asset_id)
    address = ipaddress.ip_address(ip)
    if address.is_global:
        # A real Internet endpoint (CDN, update server, ...). Known to be
        # external, but not a twin asset.
        return EndpointMapping(EXTERNAL_INTERNET, None)
    return EndpointMapping(None, None)


def is_internal(ip: str) -> bool:
    address = ipaddress.ip_address(ip)
    return address.is_private and not address.is_loopback
