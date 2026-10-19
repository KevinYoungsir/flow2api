"""Read-only HTTP checks. Secrets come from env, never command line or output."""

import argparse
import os
import sys
import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    args = parser.parse_args()
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=20, follow_redirects=False, trust_env=False) as client:
        checks = []
        health = client.get("/health")
        checks.append(("health", health.status_code == 200 and health.json() == {"status": "ok"}))
        checks.append(("login page", client.get("/login").status_code == 200))
        checks.append(("manage requires session", client.get("/manage").status_code == 302))
        checks.append(("API rejects wrong key", client.get("/v1/models", headers={"Authorization": "Bearer invalid-deployment-probe"}).status_code == 401))
        checks.append(("metrics requires session", client.get("/metrics").status_code == 401))
        api_key = os.getenv("FLOW2API_CHECK_API_KEY")
        if api_key:
            result = client.get("/v1/models", headers={"Authorization": f"Bearer {api_key}"})
            checks.append(("models with supplied key", result.status_code == 200 and bool(result.json().get("data"))))
        else:
            print("SKIP: authenticated models (FLOW2API_CHECK_API_KEY absent)")
        for name, passed in checks:
            print(f"{'PASS' if passed else 'FAIL'}: {name}")
        return 0 if all(passed for _, passed in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
