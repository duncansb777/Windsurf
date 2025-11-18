# Billing Exception Rules

- **No open blockers** (ID: BR-001)
  Description: Change of Ownership must not proceed if any open exception exists for the account.
  Check: exceptions.status in {open, investigation} → block

- **Debt arrangement in place** (ID: BR-002)
  Description: If payment arrangement active, prevent wrongful disconnections.
  Check: arrangement.active = true → escalate human review

- **High variance estimated read** (ID: BR-003)
  Description: If estimated read variance > threshold, require special read before CoO finalization.
  Check: var_pct > 0.15 → create special read order
