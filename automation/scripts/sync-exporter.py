import os
import subprocess
import logging
from dotenv import load_dotenv
import json

load_dotenv()

SITES = {
    "A": {
        "KEYRING": os.getenv("SITEA_KEYRING"),
        "REALM": os.getenv("SITEA_REALM"),
        "ZONEGROUP": os.getenv("SITEA_ZONEGROUP"),
        "ZONE": os.getenv("SITEA_ZONE"),
        "LOGFILE": os.getenv("SITEA_LOGFILE", "exporter-siteA.log"),
    },
    "B": {
        "KEYRING": os.getenv("SITEB_KEYRING"),
        "REALM": os.getenv("SITEB_REALM"),
        "ZONEGROUP": os.getenv("SITEB_ZONEGROUP"),
        "ZONE": os.getenv("SITEB_ZONE"),
        "LOGFILE": os.getenv("SITEB_LOGFILE", "exporter-siteB.log"),
    }
}

CEPH_CONF = os.getenv("CEPH_CONF", "/etc/ceph/ceph.conf")

def setup_logger(logfile):
    logger = logging.getLogger(logfile)
    logger.setLevel(logging.INFO)

    if logger.hasHandlers():
        logger.handlers.clear()

    fh = logging.FileHandler(logfile)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    return logger

def run_radosgw_admin(site_name, config):
    logger = setup_logger(config["LOGFILE"])
    logger.info(f"Starting radosgw-admin for site {site_name}")

    base_cmd = [
        "radosgw-admin",
        f"--conf={CEPH_CONF}",
        f"--keyring={config['KEYRING']}",
    ]

    if config.get("REALM"):
        base_cmd.append(f"--rgw-realm={config['REALM']}")
    if config.get("ZONEGROUP"):
        base_cmd.append(f"--rgw-zonegroup={config['ZONEGROUP']}")
    if config.get("ZONE"):
        base_cmd.append(f"--rgw-zone={config['ZONE']}")

    full_cmd = base_cmd + ["bucket", "list"]

    logger.info(f"Running command: {' '.join(full_cmd)}")
    try:
        result = subprocess.run(full_cmd, capture_output=True, text=True, check=True)
        logger.info(f"Command succeeded, output length: {len(result.stdout)}")
        buckets = json.loads(result.stdout)
        logger.info(f"Retrieved {len(buckets)} buckets for site {site_name}")
        for bucket in buckets:
            logger.info(f"Site {site_name} bucket: {bucket}")
        return buckets
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with code {e.returncode}, stderr: {e.stderr.strip()}")
    except json.JSONDecodeError as je:
        logger.error(f"JSON decode error: {je}")
    return None

def main():
    all_data = {}
    for site_name, config in SITES.items():
        buckets = run_radosgw_admin(site_name, config)
        all_data[site_name] = buckets

    print("Buckets summary:")
    for site, buckets in all_data.items():
        if buckets is None:
            print(f"Site {site}: Failed to retrieve buckets")
        else:
            print(f"Site {site}: {len(buckets)} buckets")
            for b in buckets:
                print(f"  - {b}")

if __name__ == "__main__":
    main()

