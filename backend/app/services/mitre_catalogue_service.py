from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.models import MitreTechniqueRecord
from app.schemas.correlation import MitreTechnique

CATALOGUE_VERSION = "aegistwin-mitre-v1"
CATALOGUE = (
    (
        "T1110",
        "Brute Force",
        ["Credential Access"],
        "Repeated attempts to obtain account access.",
        "Requires an explicit repeated-attempt pattern or minimum failed-attempt count.",
    ),
    (
        "T1110.001",
        "Password Guessing",
        ["Credential Access"],
        "Repeated password guesses against a synthetic account.",
        "Requires at least five failed attempts in one synthetic event or related sequence.",
    ),
    (
        "T1078",
        "Valid Accounts",
        ["Defense Evasion", "Persistence", "Privilege Escalation", "Initial Access"],
        "Use of a valid account following relevant synthetic access evidence.",
        "Requires a successful login causally preceded by repeated failures for the same user.",
    ),
    (
        "T1098",
        "Account Manipulation",
        ["Persistence", "Privilege Escalation"],
        "Explicit modification of a synthetic account or its permissions.",
        "Requires account_manipulation metadata; privilege change alone is insufficient.",
    ),
    (
        "T1021",
        "Remote Services",
        ["Lateral Movement"],
        "Use of an explicitly identified synthetic remote service.",
        "Requires remote_service protocol or channel metadata.",
    ),
    (
        "T1041",
        "Exfiltration Over C2 Channel",
        ["Exfiltration"],
        "Transfer over an explicitly identified synthetic C2 channel.",
        "Requires channel_type=synthetic_c2; size alone is insufficient.",
    ),
    (
        "T1567",
        "Exfiltration Over Web Service",
        ["Exfiltration"],
        "Transfer through an explicitly identified synthetic web service.",
        "Requires channel_type=synthetic_web_service and web_service metadata.",
    ),
)


class MitreCatalogueService:
    def ensure(self, session: Session) -> None:
        for technique_id, name, tactics, description, conditions in CATALOGUE:
            if session.get(MitreTechniqueRecord, technique_id) is None:
                session.add(
                    MitreTechniqueRecord(
                        technique_id=technique_id,
                        name=name,
                        tactics_json=tactics,
                        description=description,
                        mapping_conditions=conditions,
                        catalogue_version=CATALOGUE_VERSION,
                        source_name="MITRE ATT&CK (local curated subset)",
                        reference_date="2026-07-22",
                        synthetic_demo_applicable=True,
                        synthetic=True,
                    )
                )
        session.flush()

    def list(self, session: Session) -> list[MitreTechnique]:
        self.ensure(session)
        return [self._schema(session.get(MitreTechniqueRecord, item[0])) for item in CATALOGUE]

    def get(self, session: Session, technique_id: str) -> MitreTechnique:
        self.ensure(session)
        record = session.get(MitreTechniqueRecord, technique_id)
        if record is None:
            raise ApplicationError(
                "MITRE_TECHNIQUE_NOT_FOUND", "The local technique was not found.", 404
            )
        return self._schema(record)

    @staticmethod
    def _schema(record: MitreTechniqueRecord | None) -> MitreTechnique:
        assert record is not None
        return MitreTechnique(
            technique_id=record.technique_id,
            name=record.name,
            tactics=record.tactics_json,
            description=record.description,
            mapping_conditions=record.mapping_conditions,
            catalogue_version=record.catalogue_version,
            source_name=record.source_name,
            reference_date=record.reference_date,
            synthetic_demo_applicable=record.synthetic_demo_applicable,
            synthetic=True,
        )


mitre_catalogue_service = MitreCatalogueService()
