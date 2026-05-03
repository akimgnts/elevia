# Explain Layer — User-Friendly Explanations

Transform technical `ExplainBlock` payloads into narratives for end users.

## Purpose

The matching engine returns rich technical data (`ExplainBlock`) with:
- Matched/missing skills (categorized by importance)
- Score breakdown (skills/language/education/country)
- Near-match signals

This layer converts that data into simple, actionable narratives:
- **Summary reason**: Why is this a match?
- **Strengths**: Top matching points
- **Gaps**: Missing skills
- **Blockers**: Critical missing skills
- **Next actions**: What to learn to improve fit

## Usage

### Basic

```python
from explain import build_offer_explanation

explanation = build_offer_explanation(
    score=75,
    skill_overlap=3,
    title="Senior Python Developer",
    explain_block=match_result.explain,
    domain_affinity="aligned"
)

# Output:
# OfferExplanation(
#   score=75,
#   fit_label="Strong Match",
#   summary_reason="You have 3 of 5 core skills (60%)...",
#   strengths=["Strong Python background", "SQL & database experience"],
#   gaps=["Need Docker", "Need Kubernetes"],
#   blockers=[],
#   next_actions=["Learn Docker fundamentals"]
# )
```

### Format for JSON Response

```python
from explain import format_explanation_for_display

formatted = format_explanation_for_display(explanation)

# Output (clean JSON):
# {
#   "score": 75,
#   "fit_label": "Strong Match",
#   "summary_reason": "You have 3 of 5 core skills (60%) — strong match...",
#   "strengths": ["Strong Python background", ...],
#   "gaps": ["Need docker", "Need kubernetes"],
#   "blockers": [],
#   "next_actions": ["Learn docker fundamentals", ...]
# }
```

## Integration Points

### In /inbox Endpoint

Add to response transformation:

```python
# apps/api/src/api/routes/inbox.py

from explain import build_offer_explanation, format_explanation_for_display

for item in items:
    if req.explain:
        explanation = build_offer_explanation(
            score=item.score,
            skill_overlap=item.skill_overlap,
            title=item.title,
            explain_block=item.explain,
            domain_affinity=item.domain_affinity
        )
        item.explanation = format_explanation_for_display(explanation)
```

### Schema Change

Update `InboxItem` to include `explanation` field:

```python
# apps/api/src/api/schemas/inbox.py

class InboxItem(BaseModel):
    # ... existing fields ...
    explain: ExplainBlock  # Detailed technical (optional)
    explanation: Optional[Dict[str, Any]]  # Simple narrative (new)
```

## What It Does (NOT)

✗ Does NOT modify scoring  
✗ Does NOT modify matching  
✗ Does NOT use AI/LLM  
✗ Does NOT create new data sources  
✗ Does NOT change ExplainBlock structure  

## What It Does

✓ Reads existing `ExplainBlock` fields  
✓ Generates human-readable narratives  
✓ Categorizes skills by importance  
✓ Creates actionable next steps  
✓ Adds domain context  

## Quality Standards

All text generation is **deterministic**:

- Score label: based on 0-100 threshold
- Summary reason: based on core skill count/percentage
- Strengths: top 3-5 matched skills, converted to statements
- Gaps: missing secondary skills
- Blockers: critical missing core skills
- Next actions: top 2 core + top 1 secondary + generic

No randomness, no AI, reproducible output.

## Testing

Run unit tests:

```bash
python3 -m pytest apps/api/tests/test_offer_explanation_builder.py -v
```

Tests verify:
- Score label conversion (80+, 60+, 40+, 20+, 0)
- Developer profile (high overlap)
- Data Analyst profile (moderate overlap)
- Sales profile (low overlap)
- Blocker detection (multiple missing core)
- JSON formatting
- Fallback when no ExplainBlock

## Examples

### Developer Profile → Offer

Input:
- Score: 75
- Matched core: Python, SQL, JavaScript
- Missing core: Docker, Kubernetes
- Domain: aligned

Output:
```
You have 3 of 5 core skills (60%) — strong match.
Matched: Python, SQL, JavaScript.
Your background aligns with the Senior Python Developer domain.

Strengths:
• Strong Python background
• SQL & database experience

Gaps:
• Need docker
• Need kubernetes

Next Actions:
• Learn docker fundamentals
• Get kubernetes experience
```

### Sales Profile → Data Role

Input:
- Score: 40
- Matched core: Communication
- Missing core: Sales, CRM, Negotiation, Account Management
- Domain: out

Output:
```
You have 1 of 5 core skills (20%) — good potential.

Strengths:
• Communication skills

Gaps:
• Need sales
• Need crm

Blockers:
• Missing 4 core skills: Sales, CRM, Negotiation, Account Management

Next Actions:
• Learn sales fundamentals
• Get crm experience
```

## Maintenance

When adding new fields to `ExplainBlock`:
1. Update `build_offer_explanation()` to use new field
2. Add tests for new logic
3. Update this README

When changing skill-to-strength mapping:
- Edit `_extract_strengths()` function
- Add test cases for new skill types

## Performance

- Single offer: <1ms
- 20 offers (inbox page): <20ms
- Zero API calls
- Zero database queries
- Pure computation

## Future Enhancements

Potential improvements (NOT planned):
- Personalized next actions based on profile skills
- Industry-specific language ("junior vs senior", etc.)
- Learning resources recommendations
- Time estimates for skill acquisition

Current scope: deterministic, user-facing narratives from existing data.
