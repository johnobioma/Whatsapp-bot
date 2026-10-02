import asyncio
import logging

from fastapi import FastAPI

from app.database import (
    init_db,
)

from app.routes.webhook import (
    router as webhook_router,
)

from app.scheduler import (
    manager_reminder_loop,
)


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(

    level=logging.INFO,

    format=(
        "%(asctime)s - "
        "%(name)s - "
        "%(levelname)s - "
        "%(message)s"
    ),
)


# =========================================================
# APP
# =========================================================

app = FastAPI(

    title=
        "Digital Waiter Agent",

    description=
        "Agentic AI WhatsApp restaurant customer-service system",

    version=
        "2.0.0",
)


app.include_router(
    webhook_router
)


# =========================================================
# STARTUP
# =========================================================

@app.on_event("startup")
async def startup_event():

    init_db()

    asyncio.create_task(
        manager_reminder_loop()
    )

    logging.getLogger(
        "main"
    ).info(
        "Digital Waiter Agent started"
    )


# =========================================================
# ROOT
# =========================================================

@app.get("/")
async def root():

    return {

        "message":
            "Digital Waiter Agent is running",

        "version":
            "2.0.0",

        "architecture":
            "agentic",

        "status":
            "online",
    }


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
async def health():

    return {

        "status":
            "healthy",

        "agent":
            "online",

        "database":
            "connected",
    }