"""
application_status_service.py
------------------------------
Automatic ghosting logic for Phase 12.

Business rule:
  - An ACTIVE application with >= 3 follow-ups
  - whose most recent follow-up was logged >= 2 days ago
  → is automatically moved to GHOSTED status.

Only ACTIVE applications are ever touched.
REJECTED, OFFER, INTERVIEW, and already-GHOSTED applications are never changed.

Call update_ghosted_applications(db) at the start of any frequently-visited
page (dashboard, applications list, application detail) so the update happens
transparently without Celery or cron jobs.
"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.application import JobApplication, ApplicationStatus
from app.models.followup import ApplicationFollowUp
from app.core.config import settings


def update_ghosted_applications(db: Session) -> int:
    """
    Scan all ACTIVE applications across all users and auto-ghost any that qualify.

    Qualification criteria:
      1. status == ACTIVE
      2. number of follow-ups >= MAX_FOLLOWUPS (default 3)
      3. the latest follow-up's followup_date + 2 days <= today
         (i.e. at least 2 full days have passed since the last follow-up)

    Returns the number of applications that were ghosted in this call.
    """
    today = date.today()
    ghosted_count = 0

    # Fetch every ACTIVE application.
    # We intentionally do NOT filter by user_id so a single call covers everyone.
    active_apps = (
        db.query(JobApplication)
        .filter(JobApplication.status == ApplicationStatus.ACTIVE)
        .all()
    )

    for app in active_apps:
        followups = app.followups  # already loaded via relationship
        if len(followups) < settings.MAX_FOLLOWUPS:
            continue

        # Find the most recent follow-up by date
        latest_followup = max(followups, key=lambda f: f.followup_date)
        cutoff_date = latest_followup.followup_date + timedelta(days=2)

        if cutoff_date <= today:
            app.status = ApplicationStatus.GHOSTED
            ghosted_count += 1

    if ghosted_count:
        db.commit()

    return ghosted_count
