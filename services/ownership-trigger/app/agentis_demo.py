import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from libs.agentis.context_pipeline import retrieve_minimal_context, load_fixture, preprocess_for_prompt, assemble_prompt
from libs.agentis.llm_client import LLMClient
from libs.agentis.pipelines import sense, plan, explain, normalize, predict
from libs.agentis.tools.orchestration import create_task
from libs.agentis.tools.messaging import send_message

FIX_DIR = os.path.join("data", "fixtures")


def run_demo(patient_id: str) -> Dict[str, Any]:
    ctx = retrieve_minimal_context(patient_id)
    discharge_notes = load_fixture(os.path.join(FIX_DIR, "discharge_notes.json"))
    goals = load_fixture(os.path.join(FIX_DIR, "goals.json"))
    consent = load_fixture(os.path.join(FIX_DIR, "consent_policy_snippets.json"))

    pre = preprocess_for_prompt({"bundle": ctx["patient_bundle"], "consent": consent})
    prompt = assemble_prompt("system", "policy", "task", pre, [])

    llm = LLMClient()
    llm_out = llm.complete(prompt["system"], json.dumps(prompt))

    out_a = sense.run(discharge_notes["cases"][0]["text"], pre)
    out_b = plan.run(goals["sets"][0], pre)
    out_d = normalize.run(out_a["handover_facts"])
    out_e = predict.run({"scores": {"readmission": 0.3}}, {"rules": []})
    out_c = explain.run("", "low", "2025-11-09")

    return {
        "prompt": {
            "system": prompt.get("system"),
            "user": json.dumps(prompt),
        },
        "llm_output": llm_out,
        "sense": out_a,
        "plan": out_b,
        "normalize": out_d,
        "predict": out_e,
        "explain": out_c,
    }


def run_referral_demo(patient_id: str, extra_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """LLM proposes referral-related actions; then we execute create_task/send_message with consent checks."""
    ctx = retrieve_minimal_context(patient_id)
    if extra_context and isinstance(extra_context, dict):
        eb = extra_context.get("patient_bundle")
        if eb:
            ctx["patient_bundle"] = eb
    # Attach per-patient discharge notes and risk facts (rotate every 3 patients)
    try:
        dn = load_fixture(os.path.join(FIX_DIR, "discharge_notes.json"))
        cases = dn.get("cases", [])
        idx = max((int(patient_id) - 1) % 3, 0) if cases else 0
        note_text = (cases[idx] or {}).get("text", "") if cases else ""
    except Exception:
        note_text = ""
    # Derive a compact risk summary for inclusion in GP communications.
    # Align with Epic mock convention: any patient_id containing '5' represents
    # active suicide risk with NO documented safety plan completed.
    pid_str = str(patient_id)
    if "5" in pid_str:
        risk_summary = (
            "Risk: suicide risk flagged (active ideation, no safety plan documented). "
            "Do not treat safety planning as completed; ensure plan is created and reviewed before discharge."
        )
    else:
        try:
            mod = (int(patient_id) - 1) % 3
        except Exception:
            mod = 0
        risk_summary = (
            "Risk: suicide risk flagged (passive ideation, safety plan completed)." if mod == 0 else
            "Risk: housing instability; recent missed medications; community MH follow-up needed." if mod == 1 else
            "Risk: recent medication change (sertraline started); monitor adherence and side effects."
        )
    pre = preprocess_for_prompt({
        "bundle": ctx.get("patient_bundle"),
        "consent": load_fixture(os.path.join(FIX_DIR, "consent_policy_snippets.json")),
        "handover": {"note": note_text, "risk_summary": risk_summary},
        "extra": (extra_context or {})
    })
    # Prepare a focused referral instruction for the LLM
    system = (
        "You are a care orchestration planner. Output a JSON object with two arrays: \n"
        "tasks: [{owner_ref, description, due_ts, purpose_of_use}], \n"
        "messages: [{channel, to_ref, purpose_of_use, content}]. \n"
        "Use Australia/Sydney timezone. Keep minimal safe actions. \n"
        "If the context includes a ServiceRequest referral or follow-up need, you MUST include at least one task and one message. \n"
        "Prefer due_ts within 7 days; keep descriptions concise and compliant."
    )
    user = json.dumps({
        "goal": "Complete referral follow-up tasks and notifications",
        "patient_ref": f"Patient/{patient_id}",
        "context": pre,
        "examples": []
    })
    llm = LLMClient()
    llm_out = llm.complete(system, user, schema={
        "type": "object",
        "properties": {
            "tasks": {"type": "array", "items": {"type": "object", "properties": {
                "owner_ref": {"type": "string"},
                "description": {"type": "string"},
                "due_ts": {"type": "string"},
                "purpose_of_use": {"type": "string"}
            }, "required": ["owner_ref", "description", "due_ts", "purpose_of_use"]}},
            "messages": {"type": "array", "items": {"type": "object", "properties": {
                "channel": {"type": "string"},
                "to_ref": {"type": "string"},
                "purpose_of_use": {"type": "string"},
                "content": {"type": "string"}
            }, "required": ["channel", "to_ref", "purpose_of_use", "content"]}}
        },
        "required": ["tasks", "messages"]
    })
    proposed = llm_out.get("json") if isinstance(llm_out.get("json"), dict) else {}
    tasks = proposed.get("tasks", []) if isinstance(proposed, dict) else []
    messages = proposed.get("messages", []) if isinstance(proposed, dict) else []

    # Fallback: if LLM produced no actions, synthesize reasonable actions for demo
    if (not tasks and not messages):
        # Choose community MH centre performer; patient 1 uses org-002 per fixtures
        org_ref = "Organization/org-002" if str(patient_id) == "1" else "Organization/org-001"
        # Due within 7 days in ISO 8601 UTC
        due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        tasks = [
            {
                "owner_ref": "Practitioner/prov-002",  # Case Manager Kim
                "description": "Book community mental health follow-up appointment",
                "due_ts": due,
                "purpose_of_use": "care-coordination",
            }
        ]
        messages = [
            {
                "channel": "email",
                "to_ref": "Practitioner/prov-001",  # default GP; may be remapped below for even-numbered patients
                "purpose_of_use": "treatment",
                "content": (
                    "Sharing discharge summary with risk details and notifying the community mental health appointment. "
                    + risk_summary
                ),
            }
        ]

    # For even-numbered patients, route allowed practitioner notifications to Hospital Practitioner (prov-004)
    try:
        n_pid = int(patient_id)
        if n_pid % 2 == 0:
            for m in messages:
                to_ref = m.get("to_ref", "")
                # Keep social worker messages as-is (prov-002) to demonstrate denial; remap other Practitioner/* to prov-004
                if to_ref.startswith("Practitioner/") and to_ref != "Practitioner/prov-002":
                    m["to_ref"] = "Practitioner/prov-004"
    except Exception:
        pass

    exec_results = {"tasks": [], "messages": []}
    patient_ref = f"Patient/{patient_id}"
    # Capture the intended practitioner message content (from LLM or fallback) for UI display
    gp_message_content = ""
    if messages:
        try:
            # Prefer Hospital Practitioner (prov-004), then GP (prov-001), else first message
            gp_message_content = (
                next((m.get("content", "") for m in messages if m.get("to_ref") == "Practitioner/prov-004"), None)
                or next((m.get("content", "") for m in messages if m.get("to_ref") == "Practitioner/prov-001"), None)
                or messages[0].get("content", "")
            )
        except Exception:
            gp_message_content = messages[0].get("content", "")
    # Execute tasks with consent enforcement in adapter
    for t in tasks:
        res = create_task(
            owner_ref=t.get("owner_ref", ""),
            description=t.get("description", ""),
            due_ts=t.get("due_ts", ""),
            patient_ref=patient_ref,
            purpose_of_use=t.get("purpose_of_use", "treatment"),
        )
        exec_results["tasks"].append({"input": t, "result": res})
    # Execute messages with consent enforcement
    for m in messages:
        res = send_message(
            channel=m.get("channel", "clinician"),
            to_ref=m.get("to_ref", ""),
            purpose_of_use=m.get("purpose_of_use", "care-coordination"),
            content=m.get("content", ""),
            patient_ref=patient_ref,
        )
        exec_results["messages"].append({"input": m, "result": res})

    # Build a share_result summary indicating which components were allowed vs denied
    share_allowed: List[Dict[str, Any]] = []
    share_denied: List[Dict[str, Any]] = []
    # Messages (sharing)
    for em in exec_results["messages"]:
        status = (em.get("result") or {}).get("status")
        item = {
            "type": "message",
            "to_ref": (em.get("input") or {}).get("to_ref", ""),
            "purpose_of_use": (em.get("input") or {}).get("purpose_of_use", ""),
            "content": (em.get("input") or {}).get("content", ""),
            "status": status,
        }
        if status == "queued":
            share_allowed.append(item)
        else:
            share_denied.append({**item, "reason": (em.get("result") or {}).get("reason", "")})
    # Tasks (assignment)
    for et in exec_results["tasks"]:
        status = (et.get("result") or {}).get("status")
        item = {
            "type": "task",
            "owner_ref": (et.get("input") or {}).get("owner_ref", ""),
            "description": (et.get("input") or {}).get("description", ""),
            "due_ts": (et.get("input") or {}).get("due_ts", ""),
            "status": status,
        }
        if status == "created":
            share_allowed.append(item)
        else:
            share_denied.append({**item, "reason": (et.get("result") or {}).get("reason", "")})

    return {
        "prompt": {"system": system, "user": user},
        "llm_output": llm_out,
        "executed": exec_results,
        "handover": {"note": note_text, "risk_summary": risk_summary},
        "gp_message": gp_message_content,
        "share_result": {"allowed": share_allowed, "denied": share_denied},
    }


if __name__ == "__main__":
    result = run_demo("123")
    print(json.dumps(result, indent=2))
