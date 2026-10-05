"""Tiny `/ws/live/` client: subscribe and print one line per message (acceptance checks)."""

import json
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from websockets.sync.client import connect


class Command(BaseCommand):
    help = "Connect to /ws/live/, subscribe and print a summary line per message."

    def add_arguments(self, parser):
        # through nginx, the same path a browser takes
        parser.add_argument("--url", default="ws://nginx/ws/live/")
        parser.add_argument("--origin", default="http://localhost:8800")
        parser.add_argument(
            "--bbox", default=",".join(str(v) for v in settings.REGION_BBOX),
            help="minLon,minLat,maxLon,maxLat (default: the region)",
        )  # fmt: skip
        parser.add_argument("--seconds", type=float, default=15)
        parser.add_argument("--raw", action="store_true", help="print full JSON frames")

    def handle(self, *args, **opts):
        bbox = [float(v) for v in opts["bbox"].split(",")]
        deadline = time.monotonic() + opts["seconds"]
        with connect(opts["url"], origin=opts["origin"]) as ws:
            ws.send(json.dumps({"type": "subscribe", "bbox": bbox}))
            while (left := deadline - time.monotonic()) > 0:
                try:
                    frame = ws.recv(timeout=left)
                except TimeoutError:
                    break
                self.stdout.write(frame if opts["raw"] else summarize(json.loads(frame)))


def summarize(m: dict) -> str:
    clock = time.strftime("%H:%M:%S")
    match m["type"]:
        case "snapshot":
            return f"{clock} snapshot  aircraft={len(m['aircraft'])}"
        case "delta":
            return f"{clock} delta     upserts={len(m['upserts'])} removes={len(m['removes'])}"
        case "geofence_event":
            return (f"{clock} GEOFENCE  {m['event']:<5} {m['icao24']} {m['callsign'] or '-'} "
                    f"{m['geofence']['name']} (event id {m['id']})")  # fmt: skip
        case _:
            return f"{clock} {m['type']:<9} {json.dumps(m)}"
