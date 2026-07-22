from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.database.models import ProgressionCatalogueEntryRecord

PROGRESSION_CATALOGUE_VERSION = "aegistwin-progression-v1"


@dataclass(frozen=True)
class ProgressionEntry:
    entry_id: str
    source_technique_id: str
    destination_technique_id: str
    source_tactic: str
    destination_tactic: str
    rationale: str
    prerequisites: tuple[str, ...]
    contradictions: tuple[str, ...]
    transition_weight: float


ENTRIES = (
    ProgressionEntry(
        "guess-to-valid",
        "T1110.001",
        "T1078",
        "Credential Access",
        "Initial Access",
        "Repeated authentication pressure may be followed by valid account use.",
        ("repeated authentication failures",),
        ("no successful login evidence yet",),
        0.90,
    ),
    ProgressionEntry(
        "valid-to-account",
        "T1078",
        "T1098",
        "Initial Access",
        "Persistence",
        "Valid account use may precede explicit account permission modification.",
        ("successful synthetic login",),
        ("account manipulation metadata absent",),
        0.82,
    ),
    ProgressionEntry(
        "account-to-remote",
        "T1098",
        "T1021",
        "Persistence",
        "Lateral Movement",
        "Account modification may increase access to explicitly identified remote services.",
        ("account manipulation observed",),
        ("remote service metadata absent",),
        0.84,
    ),
    ProgressionEntry(
        "remote-to-web-transfer",
        "T1021",
        "T1567",
        "Lateral Movement",
        "Exfiltration",
        "Remote access may precede a metadata-qualified synthetic web-service transfer.",
        ("remote service observed",),
        ("web service channel absent",),
        0.76,
    ),
    ProgressionEntry(
        "remote-to-c2-transfer",
        "T1021",
        "T1041",
        "Lateral Movement",
        "Exfiltration",
        "Remote access may precede a transfer over an explicitly identified synthetic C2 channel.",
        ("remote service observed",),
        ("synthetic C2 channel absent",),
        0.70,
    ),
)


class ProgressionCatalogueService:
    def ensure(self, session: Session) -> None:
        for item in ENTRIES:
            if session.get(ProgressionCatalogueEntryRecord, item.entry_id) is None:
                session.add(
                    ProgressionCatalogueEntryRecord(
                        entry_id=item.entry_id,
                        source_technique_id=item.source_technique_id,
                        destination_technique_id=item.destination_technique_id,
                        source_tactic=item.source_tactic,
                        destination_tactic=item.destination_tactic,
                        rationale=item.rationale,
                        prerequisites_json=list(item.prerequisites),
                        contradictions_json=list(item.contradictions),
                        transition_weight=item.transition_weight,
                        catalogue_version=PROGRESSION_CATALOGUE_VERSION,
                        synthetic=True,
                    )
                )
        session.flush()


progression_catalogue_service = ProgressionCatalogueService()
