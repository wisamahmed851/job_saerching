"""
Template Service
================
Manages default email template values and placeholder rendering.
No database or HTTP concerns live here.

Supported placeholders:
    {{ company_name }}  — Name of the company applied to
    {{ position }}      — Position applied for
    {{ user_name }}     — Current user's display name (title-cased)
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Default template content
# ---------------------------------------------------------------------------

DEFAULT_SUBJECT = "Follow-up regarding my application for {{ position }}"

DEFAULT_BODY = """\
Hi {{ company_name }} Team,

I hope you're doing well.

I wanted to follow up regarding my application for the {{ position }} position. \
I remain very interested in the opportunity and wanted to check whether there are \
any updates regarding the hiring process.

Thank you for your time and consideration.

Best Regards,
{{ user_name }}\
"""


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_template(template: str, company_name: str, position: str, user_name: str) -> str:
    """
    Replace all supported placeholders in `template` with actual values.
    Unknown/unsupported placeholders are left as-is.
    """
    return (
        template
        .replace("{{ company_name }}", company_name)
        .replace("{{ position }}", position)
        .replace("{{ user_name }}", user_name)
        # Also handle without spaces inside braces (defensive)
        .replace("{{company_name}}", company_name)
        .replace("{{position}}", position)
        .replace("{{user_name}}", user_name)
    )


def render_subject_and_body(
    subject_template: str,
    body_template: str,
    company_name: str,
    position: str,
    user_name: str,
) -> tuple[str, str]:
    """Render both subject and body, returning (rendered_subject, rendered_body)."""
    rendered_subject = render_template(subject_template, company_name, position, user_name)
    rendered_body = render_template(body_template, company_name, position, user_name)
    return rendered_subject, rendered_body
