"""Architecture steps 8-11 and 16-19: the sole persistence service."""
from .database import Database


class PictureSaver:
    def __init__(self, settings, database=None):
        self.settings = settings
        self.database = database or Database(settings.resolve(settings.data["database"]))

    def save_picture(self, packet, scenario):
        return self.database.create(packet, self.settings, scenario)

    def save_result(self, inspection_id, decision, reason, analysis, elapsed_ms):
        self.database.complete(inspection_id, decision, reason, analysis, elapsed_ms)

    def save_operator_decision(self, inspection_id, decision):
        self.database.save_operator_decision(inspection_id, decision, self.settings.data["demo"])
