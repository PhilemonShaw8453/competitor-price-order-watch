from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .infrai_client import InfraiClient, InfraiError
from .order_updates import CatalogCheck, CatalogMonitor, CheckResult

app = FastAPI(title="Catalog checkout watch")


@app.post("/catalog/checks", response_model=CheckResult)
def check_catalog(request: CatalogCheck) -> CheckResult:
    client = InfraiClient()
    try:
        return CatalogMonitor(client).run(request)
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=status, detail={"code": exc.code, "detail": exc.detail}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        client.close()

